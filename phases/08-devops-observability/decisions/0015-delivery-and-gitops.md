# ADR-0015: CI/CD、GitOps、Secret、監視の構成

> **読む順番:** この ADR には Lab 08 の設計課題の答えにあたる内容が含まれます。先に [Phase 8 のラボ](../README.md) の設計課題に自分で答えてから読み、自分の考えと比べてください。

## Status

提案（2026-11-10）。Phase 8 に適用。学習者が Lab 08 の設計課題に回答し、内容を確認したうえで「採用」に変更する。

## Context

Phase 7 までは、手元から `kubectl apply` とスクリプトでデプロイしていた。変更の検証（テスト・ビルド・マニフェストの生成）は人の記憶に頼り、承認の記録も、デプロイ後の状態の観察も仕組みになっていない。Phase 8 では次の点を、費用をかけずに（AWS の操作を伴うものは承認後に学習者が行う形で）確認できる構成にしたい。

- push ごとに、コード・イメージ・マニフェスト・Terraform が壊れていないことを自動で確認する。
- AWS へのデプロイは、人の承認を挟み、長期の認証情報を置かない。
- Git を正とした同期（GitOps）と、手元の変更（drift）の検出を、kind で観察する。
- 利用者に見える遅延とエラーを、メトリクスで測る。

制約として、AWS の有料リソースは承認なしに作らない（この ADR の作成時点で CD は実行していない）。kind で試す GitOps は、リポジトリが GitHub に push されるまで、実際のリポジトリを同期できない。

## Decision

### 1. CI は GitHub Actions の 7 ジョブで、AWS の認証情報を使わない

`.github/workflows/ci.yaml` が push と pull request で動く。ジョブは API テスト（PostgreSQL のサービスコンテナ）、Web の型検査とビルド、学習ポータルのテストとビルド、Docker イメージのビルド（push しない）、Kustomize の生成確認、Terraform の整形・検証、シェルスクリプトの構文確認。

- `permissions: contents: read` だけにし、`pull_request` からも書き込み権限や Secrets に触れない。
- サードパーティのアクションは、改ざんされにくいようにコミット SHA で固定し、コメントに版を書く。ツール（Node 24.22.2、Python 3.11、Terraform 1.17.1、kubectl v1.34.1）はローカル・Dockerfile と同じ版にそろえる。
- Kustomize の生成確認は、`phases/*/kustomize/` の `base`・`components` 以外の kustomization をすべて対象にする。Git 管理外の `secrets/*.env` は、同じ場所の `*.env.example`（ダミー値）をコピーして用意する。
- lint は追加しない。既存のコードが通る設定を新たに決める作業が、この Phase の目的（配信と観測）から外れるため。
- 手順の大半はローカルで再現できる（README の 7）。GitHub 上の実行は未検証。

### 2. CD は手動実行と environment の承認を挟み、OIDC の一時認証で接続する

`cd.yaml` は `workflow_dispatch` だけで、`environment: lab` の承認（required reviewers）を待ってから動く。

- **認証:** `aws-actions/configure-aws-credentials` が GitHub の OIDC トークンで IAM ロールを引き受ける。Secrets にアクセスキーは置かない。
- **信頼条件:** ロールの信頼ポリシーは、`aud = sts.amazonaws.com` と `sub = repo:<owner>/<repo>:environment:lab` の完全一致だけを許す。別のリポジトリ、別の environment、承認を経ないジョブのトークンは引き受けられない。
- **権限:** ECR は 2 つのリポジトリ（`workboard-api`・`workboard-web`）への push、`eks:DescribeCluster` はこのクラスターだけ、Secrets Manager は RDS の管理パスワードの 1 件だけの読み取り。Kubernetes 側は EKS の access entry に `AmazonEKSEditPolicy` を `workboard` namespace に限定して関連付ける。クラスター管理者権限は与えない。
- **適用:** イメージはコミット SHA のタグで push し、Phase 7 の `eks` overlay を描画したうえで実際の値（レジストリ、RDS エンドポイント、許可 CIDR、タグ）に置換して `kubectl apply` する。Namespace は CD のロールの権限外なので、描画結果から除き、Phase 7 で作成済みであることを前提にする。
- **設定の不足:** 必須の repository variables が未設定なら、最初のステップが変数名を挙げて失敗する。
- **Terraform:** `phases/08-devops-observability/terraform/` が OIDC プロバイダー、ロール、access entry を作る。community module は使わず、IAM と EKS の関係を読めるようにする。state はローカル（Phase 6・7 と同じ方針）。

### 3. GitOps は kind で Argo CD v3.6.1 を使い、同期は手動を既定にする

- 導入は、公式の `install.yaml`（非 HA）を、**コミット SHA で固定した URL** から `kubectl apply --server-side` する。ファイル（約 2 MB）を取り込まない（vendoring しない）。Argo CD の CRD は大きく、client-side apply の annotation の上限を超えるため server-side を使う。
- Application は `kustomize/overlays/kind` を同期対象にする。`repoURL` と `targetRevision` は特定の作成者のリポジトリに固定しない。マニフェストはプレースホルダーにし、`up` が環境変数（`GITOPS_REPO_URL` / `GITOPS_REVISION`）、無ければ学習者の clone の `origin` と今のブランチから決めて書き換える。誰が clone しても、自分の fork を同期対象にできる。SSH 形式の URL は HTTPS に直し（公開リポジトリを鍵なしで読むため）、URL に含まれる認証情報はクラスターに保存しないよう取り除く。
- `syncPolicy` は付けない（手動同期）。変更が自動で反映される前に、`OutOfSync` と Diff を観察するため。自動修復（`selfHeal`）は故障実験で一時的に有効にする。
- 移行 Job は、完了済みの Job の spec が変更できないため、Argo CD の `Sync` hook にして、同期のたびに作り直す（`BeforeHookCreation`）。
- Phase 4 の HPA と metrics-server は持ち込まない。HPA が `replicas` を書き換えると、Git との差分が常に出る別の問題が混ざるため。手動の `kubectl scale` を drift の題材にする。

### 4. Secret は Git に置かず、クラスターへ別経路で作る

`overlays/kind` は `secretGenerator` を持たず、Deployment は固定名の Secret `workboard-db` を参照する。この Secret は `scripts/up` が Git 管理外の `db.env` から作る。Argo CD の管理対象に含めないため、同期（prune を含む）で消されない。

- 代償として、Secret の中身は Git から再現できない。ローテーションも手動になり、Secret の drift は検出されない。
- EKS では、Secrets Manager の値を CD が実行時に読み取り、`db.env` に書いて `secretGenerator` に渡している（直接 apply のため）。GitOps に移す場合は External Secrets Operator と Secrets Manager の組み合わせが自然だが、このリポジトリでは導入しない。

### 5. Prometheus は公式イメージ 1 つの最小構成にする

Deployment（`quay.io/prometheus/prometheus:v3.15.1`）、ConfigMap、Service、`workboard` namespace に限定した Role と RoleBinding だけ。`kubernetes_sd`（Pod）で `app=workboard-api` のコンテナポート 8000 だけを 15 秒間隔で収集する。保存は `emptyDir`（保持 2 日）で、Pod を作り直すと消える。設定は ConfigMap の生成ハッシュで、変更時に Pod が自動で更新される。

- 画面は Prometheus 標準のものだけ。Grafana、Alertmanager、アラートルール、kube-state-metrics は入れない。
- API の `process_*` から、メモリ、CPU、起動時刻（Pod の再起動の検出）を読める。Web（Nginx）、ノード、DB のメトリクスは持たない。
- SLI は API が数えた値であり、Nginx が返した 502/504 や接続できなかった要求は含まれない（利用者が見たエラーより少なく見える）。

### 6. SLI/SLO は学習用に定義し、測定前に達成を断言しない

定義は [slo.md](../slo.md) にある。

## Alternatives

- **CI からの直接 `kubectl apply` だけ:** 最も単純。しかしクラスターへの認証情報を CI に渡す必要があり、手元の変更（drift）を検出できない。→ CD として残し、GitOps は kind で別に比較する。
- **CD で長期のアクセスキーを使う:** 設定は簡単だが、漏えい時の影響が大きく、ローテーションの運用が増える。→ OIDC を採用。
- **ロールの `sub` をリポジトリ全体（`repo:<owner>/<repo>:*`）にする:** 承認を経ないジョブ（push、pull request）からも引き受けられてしまう。→ environment まで限定する。
- **CD のロールに管理者権限を与える:** Namespace の適用が簡単になる。しかし CD の侵害がクラスター全体の侵害になる。→ namespace 限定の編集権限と、Namespace の除外を選んだ。
- **Argo CD を EKS に入れる:** 本番に近い。しかし AWS の費用と、学習要素（EKS、IAM、GitOps）の同時増加がある。ADR-0005 のとおり、まず kind で挙動を理解する。EKS への導入は別途判断する。
- **Argo CD の install.yaml を vendoring する:** オフラインで再現でき、差分をレビューできる。しかし約 2 MB が repo に入り、更新のたびに巨大な差分になる。コミット SHA で固定した URL なら内容は変わらない。GitHub に接続できないと構築できないのが代償。
- **Argo CD の Helm chart で導入する:** 公式 chart もある。ただし Phase 7 で chart を利用者として学んだ範囲を超えて values の設計が増える。公式 manifest が最も素直。
- **Secret の扱い（GitOps）:**
  - Sealed Secrets: 暗号化した Secret を Git に置ける。コントローラーと、その秘密鍵の保管・バックアップが新たに必要になる。
  - External Secrets Operator + Secrets Manager: 値は AWS に残り Git には参照だけを置く。EKS では自然だが、kind では外部のストアがない。
  - SOPS + KSOPS など: 暗号化した値を Git に置ける。鍵の管理と、Argo CD への plugin の導入が必要。
  - 平文の Secret を Git に置く: 採らない。
  - この教材では、鍵管理の仕組みを持ち込まず、課題（Git に置けない値）を見えるまま残すことを優先した。
- **kube-prometheus-stack などの大型 chart:** Operator、CRD（ServiceMonitor 等）、Grafana、Alertmanager、node-exporter、kube-state-metrics が一度に入る。実務では標準的だが、数十の資源と CRD が入り、「Prometheus が Pod を見つけて数える」という中心の仕組みが見えなくなる。→ 最小構成で `relabel_configs` と PromQL を理解し、必要になった時点で chart を検討する。
- **マネージドサービス（Amazon Managed Service for Prometheus、CloudWatch など）:** 運用は軽くなるが AWS の費用が発生する。kind では使えない。

## Consequences

- CI が通ることと、デプロイされることは別。CD は CI の成功を確認しないため、実行前に人が確認する。
- push していない Phase 8 の資材は Argo CD で同期できない。学習者が自分の判断で fork に push してから体験する。
- 手動承認と OIDC の信頼条件は、設定を間違えると「承認なしに動く」か「誰も動かせない」のどちらかになる。environment 名の不一致は `AssumeRoleWithWebIdentity` の失敗として現れる。
- Prometheus の履歴は Pod とともに消える。長期の傾向を見るには永続化が必要。
- Secret を別経路にしたため、`kubectl apply -k overlays/kind` だけでは起動しない。必ず `up`（または同等の手順）で Secret を先に作る。
- Helm と Kustomize の併用は避ける（[ADR-0016](0016-helm-vs-kustomize-for-workboard.md)）。

## Evidence

2026-11-10 に確認した。kind 上の検証は Lab 08 の「実装時の検証記録」にある。

- Argo CD v3.6.1（2026-11-04 公開、安定版）。公式ドキュメントの `stable` が指すタグ。install.yaml の SHA 固定先は `94037c4d4e1af4bd0651d37a179fbd9e347e668c`（`v3.6.1` と同一）。含まれるイメージ: `quay.io/argoproj/argocd:v3.6.1`、`ghcr.io/dexidp/dex:v2.46.0`、`public.ecr.aws/docker/library/redis:8.10.1-alpine`。
  - [リリース](https://github.com/argoproj/argo-cd/releases/tag/v3.6.1)、[インストール](https://argo-cd.readthedocs.io/en/stable/operator-manual/installation/)、[自動同期](https://argo-cd.readthedocs.io/en/stable/user-guide/auto_sync/)、[リソース hook](https://argo-cd.readthedocs.io/en/stable/user-guide/resource_hooks/)、[Secret 管理](https://argo-cd.readthedocs.io/en/stable/operator-manual/secret-management/)
- Prometheus v3.15.1（2026-10-21 公開。公開から 2 週間以上経った最新の安定版を選んだ。最新は v3.16.0）: [リリース](https://github.com/prometheus/prometheus/releases/tag/v3.15.1)、[設定（kubernetes_sd_config、relabel_config）](https://prometheus.io/docs/prometheus/latest/configuration/configuration/)
- GitHub Actions のアクション（コミット SHA で固定。確認元は各リポジトリのタグ）: `actions/checkout` v7.0.1、`actions/setup-python` v7.1.0、`actions/setup-node` v7.1.0、`hashicorp/setup-terraform` v4.0.1、`azure/setup-kubectl` v5.2.0、`aws-actions/configure-aws-credentials` v6.3.0。[GitHub Actions のセキュリティ（SHA 固定）](https://docs.github.com/en/actions/reference/security/secure-use)、[AWS での OIDC](https://docs.github.com/en/actions/how-tos/secure-your-work/security-harden-deployments/oidc-in-aws)、[environment の承認](https://docs.github.com/en/actions/how-tos/deploy/configure-and-manage-deployments/review-deployments)
- Terraform 1.17.1、AWS provider 6.72.0（Phase 6 と同じ制約と lock）: [aws_iam_openid_connect_provider](https://registry.terraform.io/providers/hashicorp/aws/6.72.0/docs/resources/iam_openid_connect_provider)、[EKS のアクセスポリシー](https://docs.aws.amazon.com/eks/latest/userguide/access-policies.html)
- Cost Explorer・Budgets: [Cost Explorer](https://docs.aws.amazon.com/cost-management/latest/userguide/ce-what-is.html)、[Budgets](https://docs.aws.amazon.com/cost-management/latest/userguide/budgets-managing-costs.html)

kind での観察（`workboard-phase8`）:

- Application の `repoURL` が、Phase 8 の資材がまだ push されていない GitHub のリポジトリを指していると、`ComparisonError`（`authentication required: Repository not found`）になった。
- クラスター内の Git サーバー（`git daemon`）に、Phase 8 のコピーを置いたリポジトリで検証した。最初の同期の前は、`kubectl apply` で作ったリソースがすべて `OutOfSync` で、同期後に `Synced` / `Healthy` になった。
- 手動の `scale` は `OutOfSync` として検出され、`selfHeal` を有効にすると元の値に戻った。
- 存在しないイメージタグのコミットを同期すると、`Synced` のまま `Progressing`、旧 Pod は残り、新しい Pod は `ErrImageNeverPull`。`git revert` したコミットを同期すると `Healthy` に戻った。
- Prometheus は API の 3 Pod を対象にし、リクエスト率・エラー率・p95 を PromQL で取得できた。

未検証: GitHub Actions 上での CI/CD の実行、OIDC による AWS への接続、`AmazonEKSEditPolicy` を namespace に限定した状態で Phase 7 の overlay（Ingress、PDB、Job、Secret）がすべて適用できること、Terraform の `plan`/`apply`、Argo CD の EKS への導入、Secret の暗号化方式の実装。

参考資料:

- [Kustomize のリファレンス](https://kubectl.docs.kubernetes.io/references/kustomize/)
- [Google SRE Workbook: Implementing SLOs](https://sre.google/workbook/implementing-slos/)
