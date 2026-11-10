# ADR-0014: AWS Load Balancer Controller、Helm、Pod Identity、公開範囲

> **読む順番:** この ADR には Lab 07 の設計課題の答えにあたる内容が含まれます。先に [Phase 7 のラボ](../README.md) の設計課題に自分で答えてから読み、自分の考えと比べてください。

## Status

提案（2026-11-10）。Phase 7 に適用。学習者が Lab 07 の設計課題に回答し、内容を確認したうえで「採用」に変更する。AWS では未検証（plan/apply/helm install 未実施）。

## Context

Phase 7 では、WorkBoard を ALB 経由で短時間だけ外部から検証できるようにする。設計書 §2.1 は、認証なしの API を恒常的にインターネット公開することを禁止し、公開は短時間の検証用途とし、公開制限・セキュリティグループ・後片付けを必須とする。§9.3 は community ingress-nginx（2026-03-24 に引退）への依存を禁止している。ALB は AWS Load Balancer Controller（LBC）が Ingress から作る。LBC は AWS API を呼ぶため、IAM 権限を最小限に渡す方法が必要。導入は Helm chart で行い（[ADR-0005](../../../docs/adr/0005-kubernetes-ecosystem-tools.md)）、自アプリのマニフェストは Kustomize のままにする。

## Decision

### 1. AWS Load Balancer Controller を Helm chart で導入し、版と values を固定する

- chart は `eks/aws-load-balancer-controller` **3.6.2**（アプリ v3.6.2）。リポジトリ `https://aws.github.io/eks-charts`。固定値は `helm/aws-load-balancer-controller-values.yaml`（replica 2、ServiceAccount 名、IngressClass、使わない機能を無効化、リソース要求）。`clusterName`・`region`・`vpcId` は環境依存のため `scripts/install-lbc` が `--set` で渡す。
- 導入前に `helm show chart` / `helm show values` / `helm template` で、ServiceAccount、RBAC、Deployment、Webhook、Secret、CRD、IngressClass を読む（Lab 07 の手順）。`helm upgrade --install` を使う。初回だけ CRD が入り、upgrade では CRD は更新されない（公式手順も手動での CRD 適用を案内）ので、chart 更新時は CRD の差分を別に確認する。
- AWS 公式ドキュメントの手順の例は古い版（コントローラー v2.14.1、chart 1.14.0）だった。GitHub の最新リリース v3.6.2 と Helm リポジトリの chart 3.6.2 を確認し、**IAM ポリシーも同じ v3.6.2 のタグのもの**を使う。ドキュメントの版と最新版の差は、導入時に再確認する。
- 公式ドキュメントは、Gateway API の CRD を前提としている。この Phase では Gateway API 機能を使わない（Ingress のみ）ため、Gateway API の CRD は入れない。chart の既定でコントローラーが問題なく起動するかは AWS 上で未検証。起動に失敗する場合は feature gate の設定を調べる。
- chart のセキュリティ更新は自動では入らない（公式の注意）。更新は利用者の責任。

### 2. IAM は Pod Identity で渡し、ポリシーはリポジトリに版つきで置く

- EKS Pod Identity Agent アドオン（`eks-pod-identity-agent`）を入れ、IAM ロールの trust policy は `pods.eks.amazonaws.com`（`sts:AssumeRole`、`sts:TagSession`）。`aws_eks_pod_identity_association` で、`kube-system/aws-load-balancer-controller` の ServiceAccount にだけロールを結び付ける。ServiceAccount への annotation は不要。
- IRSA（OIDC プロバイダー）は使わない。クラスターごとの OIDC ARN を trust policy に書く手間がなく、ロールを複数クラスターで再利用しやすい。ただし Pod Identity Agent（DaemonSet）が必要で、対応する SDK の版が条件になる。
- IAM ポリシーは `terraform/policies/aws-load-balancer-controller-v3.6.2.json` に、LBC v3.6.2 の `docs/install/iam_policy.json` をそのまま置く。出典: `https://github.com/kubernetes-sigs/aws-load-balancer-controller/blob/v3.6.2/docs/install/iam_policy.json`（SHA-256: `16f232c9d9f79366fe949c4550ad517a202380058a9e48d45a4e215044a20a6a`）。手で編集しない。LBC の版を上げるときは、同じ版のポリシーを取得し直して差分を読む。ポリシーは広い（ELB、EC2 のセキュリティグループ等）。最小権限として十分か（リソース条件、タグ条件）を学習者が読んで評価する。

### 3. 公開範囲: internet-facing の ALB に `inbound-cidrs` を付ける

- Ingress は `ingressClassName: alb`、`scheme: internet-facing`、`target-type: ip`、HTTP:80 のみ。`alb.ingress.kubernetes.io/inbound-cidrs` に学習者のグローバル IP の /32 だけを指定する。LBC が ALB のセキュリティグループにこの CIDR だけを許可する。
- `deploy` スクリプトは環境変数 `WORKBOARD_ALLOWED_CIDR` を必須にし、`0.0.0.0/` で始まる値を拒否する。
- HTTP のみで TLS は使わない（ドメインと証明書がないため）。扱うのは非機密のダミーデータだけで、短時間の検証に限る。経路の平文は許可 IP の範囲に限られるが、恒常的な公開は不可。検証が終わったら Ingress を先に削除して ALB を消す（`aws-cleanup.md`）。
- WAF、認証（Cognito/OIDC）は導入しない。恒常運用が必要になった場合の課題。

### 4. ALB の health check は `/`（Web 自身）にする

ALB の対象は Web Pod（nginx）。`/health/ready` は nginx が API に中継し、API は DB に接続して確認する。DB（RDS）が落ちると全 Web Pod が unhealthy となり、ALB は静的画面も含めて 503 を返し、原因が見えにくくなる。`/` は nginx 自身が応答するかを見る。DB 障害は、API の Readiness 失敗（Service から外れる）と API の 503 としてアプリケーション層に現れ、ALB の health check には持ち込まない。`/health/live`（API の liveness を中継）は DB を確認しないが、API Pod がすべて停止した場合は unhealthy となる。どの層で何を検知するかの設計課題として、学習者が自分の判断と比べる。

### 5. community ingress-nginx は使わない

「Ingress API」「AWS Load Balancer Controller」「community ingress-nginx」を区別する。Ingress は API で、実際に処理するのはコントローラー。この Phase のコントローラーは LBC。Gateway API を使う場合も別のコントローラーが必要で、独立ラボの対象。

### 6. 発展課題（S3 CSV エクスポート、Redis + Worker）は設計の観点だけ

アプリ実装はしない。S3 への CSV 保存は、専用 ServiceAccount + Pod Identity のロール（特定バケット・プレフィックスへの `PutObject` のみ）を考える題材。Redis + Worker は、Job（一回きり）と Deployment（常駐）、非同期処理の適用先を比べる題材。

## Alternatives

- **Helm で自アプリも管理:** ADR-0005 のとおり、比較してから判断する。
- **chart を使わず LBC の manifest を直接適用:** 中身は読めるが、版の更新・rollback の単位を学べない。
- **IRSA:** 広く使われ情報も多いが、OIDC プロバイダーの設定が加わる。
- **IAM ポリシーを簡略化・自作:** 最小権限に近づけられるが、LBC の動作に必要な権限を見落としやすい。公式のポリシーを基準にして評価する。
- **NLB / Service type LoadBalancer:** L4 で、L7 のパスルーティングを学べない。
- **ALB を private（internal）にして踏み台やポートフォワードで確認:** 公開リスクがない。ALB の外部公開の制限（inbound-cidrs）を学べない。
- **health check を `/health/ready`:** DB 障害を ALB が検知できる反面、全体が 503 になる連鎖を起こす。
- **ACM 証明書 + Route 53 で HTTPS:** 本番に近いが、ドメインの取得と費用が必要。

## Consequences

- ALB は時間料金がかかり、Ingress を削除しないと残る。LBC が作った ALB・セキュリティグループ・ターゲットグループは Terraform の管理外。クラスターや LBC を先に消すと残る（削除順序に注意）。
- IAM ロールは Terraform で作るが、ServiceAccount は Helm が作る。association は ServiceAccount が存在する前でも作れる。名前と namespace の一致が条件で、一致しないとコントローラーは AWS API を呼べない。
- LBC は Webhook を持つ。コントローラーの Pod が不在・不健康だと、Service や Ingress の作成が Webhook で失敗し得る（`failurePolicy` を `helm template` で確認する）。
- 自分の IP が変わると ALB に接続できなくなる。更新は `deploy` の再実行。
- 検証は静的なもの（`helm template`、`terraform validate`）だけ。実機の動作は未確認。

## Evidence

2026-11-10 に確認した。

- [AWS Load Balancer Controller releases](https://github.com/kubernetes-sigs/aws-load-balancer-controller/releases): 最新 v3.6.2（2026-10-25）。
- [aws/eks-charts](https://github.com/aws/eks-charts): `helm search repo eks/aws-load-balancer-controller` で chart 3.6.2 / app v3.6.2。
- [Install AWS Load Balancer Controller with Helm](https://docs.aws.amazon.com/eks/latest/userguide/lbc-helm.html): 例は v2.14.1 / chart 1.14.0。IAM ポリシーの取得元、`helm install` の引数、chart の手動更新と CRD の注意。Gateway API CRD が前提と記載。
- `helm template` で chart 3.6.2 を描画し、ClusterRole/Role、Deployment（replicas 2）、Service、ServiceAccount、Secret、Mutating/ValidatingWebhookConfiguration、IngressClass、CRD 7 つが生成されることを確認した（AWS 接続なし）。
- [EKS Pod Identities](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)、[ALB Ingress](https://docs.aws.amazon.com/eks/latest/userguide/alb-ingress.html)、[Kubernetes: Ingress NGINX Retirement](https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/)。
