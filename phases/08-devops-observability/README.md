# Lab 08: DevOps、可観測性、運用改善

## 学習目標

- GitHub Actions の CI（テスト・ビルド・マニフェスト検証）と、手動承認つきの CD の構成を読み、どの段階で何を止められるかを説明する。
- GitHub OIDC による一時認証で、長期のアクセスキーを置かずに AWS へ接続する仕組みと、ロールを引き受けられる条件を説明する。
- kind 上の Argo CD で、Git を正とした同期、手動変更（drift）の検出と自動修復、不正なコミットの revert による復旧を観察する。
- Git に置けない値（Secret）が GitOps で問題になる理由と、この教材での扱いを説明する。
- Prometheus で API のメトリクスを集め、リクエスト率・エラー率・p95 応答時間を PromQL で求める。
- SLI/SLO を学習用に定義し、故障実験の前後でメトリクスがどう動くかを観察する。
- Helm と Kustomize の違いを踏まえ、自アプリのマニフェスト管理の方式を比較して判断する。
- AWS の費用を Cost Explorer・Budgets で確認し、不要な環境を削除する流れを組み立てる。

## 前提条件

Phase 4（Probe、Rolling Update、`/metrics`）と Phase 6・7（ECR、EKS、`eks` overlay、Terraform）の内容を理解していること。Linux コンテナエンジンが動く Docker（Windows / macOS は Docker Desktop、Linux は Docker Engine または Docker Desktop）、kubectl 1.34〜1.36、kind v0.33.0（導入は Phase 2 と共通の `tools/kind-install.ps1`。Bash は `tools/kind-install.sh`）が必要です。ノードは Kubernetes v1.35.8、DB は `postgres:17.11-bookworm`、Argo CD は v3.6.1、Prometheus は v3.15.1 です。インターネットに接続できる環境が必要です（Argo CD の install マニフェストを GitHub から、Prometheus のイメージを quay.io から取得します）。

この Lab の kind 部分（GitOps と可観測性）は **AWS 費用がかかりません。** 新しい kind クラスター **`workboard-phase8`**（control-plane 1 台と worker 2 台）を作り、Phase 2 の `workboard-lab`、Phase 3 の `workboard-phase3` などの既存クラスターと kubeconfig は変更しません。ノードが 3 台、Argo CD と Prometheus が加わるため、Docker のメモリ（目安として 6 GiB 以上の空き）と CPU が必要です。他の Lab のクラスターは止めてから始めてください。

ポートは WorkBoard が **8084**、Argo CD の画面が **8085**、Prometheus の画面が **8087** です（8080〜8083 は他の Phase が使います）。DB はダミーデータ専用です。

**CI/CD の節の AWS 操作（Terraform の apply、ECR への push、EKS への適用、Cost Explorer・Budgets の設定）は、AWS の有料リソースを使う Phase 6・7 のクラスターが稼働していることと、利用の明示承認が前提です。** この教材の作成者（AI を含む）は AWS を操作せず、CD も実行していません。手順は学習者が承認後に自分の手で行います。

Argo CD が同期するのは **自分が push できる公開リポジトリ** です。このリポジトリを GitHub で fork（または自分のアカウントへ複製）して clone しておきます。同期先は特定の作成者のリポジトリに固定されておらず、構築スクリプトが次の順で決めます。

- リポジトリの URL: 環境変数 `GITOPS_REPO_URL`。無ければ、この clone の `origin`（`git remote get-url origin`）。SSH 形式（`git@github.com:…`）は HTTPS に直し、URL に含まれる認証情報は取り除きます。
- リビジョン: 環境変数 `GITOPS_REVISION`。無ければ、今いるブランチ。

`origin` を読めない場合（Git 未導入、`origin` が無い、所有者の違いによる `dubious ownership` など）は、git のメッセージを表示して止まります。そのときは `GITOPS_REPO_URL` と `GITOPS_REVISION` を設定してください。

この Phase のファイルは `phases/08-devops-observability/` だけで完結します。Web/API の定義は Phase 4 と重複しています（Phase を独立させるための意図的な重複です。[ADR-0007](../../docs/adr/0007-phase-directory-layout.md)）。例外はリポジトリ直下の `.github/workflows/`（GitHub が読む場所のため）です。

## 設計課題（実装前に考える）

1. GitOps（Argo CD）と、CI からの直接 `kubectl apply` は、変更の経路・クラスターへの認証情報の置き場所・手元で変更されたときの扱いがどう違うか？ 管理するクラスターやアプリが増えたら、どちらが有利か？
2. Helm と Kustomize は、それぞれどんな変更・配布に向くか？ 両方を同じアプリに使うと何が複雑になるか？ WorkBoard を Helm chart にするかどうかは、何を基準に決めるか？
3. Git に置けない値（DB のパスワードなど）がある場合、GitOps ではどう扱うか？ 選択肢ごとに、守れるものと残る課題は何か？
4. SLI/SLO を決めるとき、何を分子・分母にするか？ どのリクエストを除外するか？ 期間と目標値はどう決めるか？ 測定する前に、達成していると言えるか？
5. CD の手動承認は、どの時点に置くか？ 承認者は何を見て判断するか？ GitHub OIDC で長期キーを置かないとき、AWS のロールを引き受けられる条件は何で絞るか？
6. API が遅くなった、またはエラーが増えたとき、Prometheus のメトリクスだけで原因を特定できるか？ 特定できないとき、追加で何を見るか？
7. AWS の費用が想定を超えないようにするために、確認する仕組みと、不要な環境を確実に消す仕組みをどう組み合わせるか？ それでも防げないことは何か？

## 実装タスク

1. [構成図](architecture.md)を読み、GitOps の経路（Git → Argo CD → クラスター）と、Prometheus が API を見つける経路を書き出す。
2. `.github/workflows/ci.yaml` と `cd.yaml`、`terraform/github-oidc.tf` を読み、各ジョブが何を止められるか、CD のロールがどの権限を持つかを対応づける。
3. `kustomize/overlays/kind/`（Argo CD の同期対象）、`kustomize/monitoring/`、`argocd/application.yaml`、`scripts/up.*` を読み、Secret がどこで作られ、どのファイルが Git に入るかを確認する。
4. [slo.md](slo.md) の SLI/SLO を読み、自分の考えと比べる。
5. 専用クラスターを構築し、メトリクスと Argo CD の画面を確認する。
6. 故障実験で、メトリクスと Argo CD の状態の変化を記録する。
7. CI をローカルで再現する。
8. （AWS 承認後）CD の設定を確認する。AWS のコスト確認と削除の流れを計画する。
9. 結果を **学習ポータルの学習メモ**（項目は「学習メモ」節）に記録する。

## 検証コマンド・期待結果

すべてリポジトリ直下で実行します。この Lab の Kubernetes 操作は `--context kind-workboard-phase8` を指定します。他の Lab のクラスターを操作しないよう、毎回 context を確認してください。

### 1. 適用前に生成結果を読む

新しいターミナルごとに最初の行を実行します。`env.ps1`（Bash は `env.sh`。実行ではなく `source` で読み込みます）はこのシェルだけで Phase 8 用の kubeconfig（`.kube/workboard-phase8.yaml`）を使う設定です。

**Windows (PowerShell):**

```powershell
. .\phases\08-devops-observability\scripts\env.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
source phases/08-devops-observability/scripts/env.sh
```

```text
kubectl kustomize phases/08-devops-observability/kustomize/overlays/kind
kubectl kustomize phases/08-devops-observability/kustomize/monitoring
```

Secret の入力は Git 管理外の `phases/08-devops-observability/kustomize/overlays/kind/secrets/db.env` です。まだ無い場合、次の「2. 構築」のスクリプトがローカル専用のランダムな値で作成します。自分で用意する場合は、例ファイル（ダミー値のみ）をコピーして値を変えます。

**Windows (PowerShell):**

```powershell
Copy-Item phases/08-devops-observability/kustomize/overlays/kind/secrets/db.env.example phases/08-devops-observability/kustomize/overlays/kind/secrets/db.env
```

**Linux / macOS / WSL (Bash):**

```bash
cp phases/08-devops-observability/kustomize/overlays/kind/secrets/db.env.example phases/08-devops-observability/kustomize/overlays/kind/secrets/db.env
```

観察する点は以下です。

- `overlays/kind` の出力に Secret が含まれず、Deployment が `workboard-db` という名前の Secret を参照していること。Phase 4 の `overlays/kind` との違い。
- 移行用 Job に Argo CD 用の annotation（`argocd.argoproj.io/hook`）が付いていること。
- Prometheus の Role と RoleBinding が `workboard` namespace に置かれ、`monitoring` の ServiceAccount に結び付いていること。ClusterRole が無いこと。
- `prometheus.yml` の `relabel_configs` が、どの Pod のどのポートだけを残すか。

### 2. 構築

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File tools/kind-install.ps1
powershell -NoProfile -File phases/08-devops-observability/scripts/up.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash tools/kind-install.sh
bash phases/08-devops-observability/scripts/up.sh
```

`kind-install` は導入済みなら何もしません。構築スクリプトは次の順で、固定秒数の sleep ではなく実際の状態を待ちます。

1. `workboard-phase8` クラスターの作成（存在しなければ）。同名クラスターのみ・kubeconfig のみ残っている場合は確認のため停止します。他のクラスターには何も適用しません。
2. API/Web イメージのビルドと `kind load docker-image`（`imagePullPolicy: Never`）。
3. `db.env` が無ければランダムなパスワードを生成して作成（値は表示しません）。既にあれば変更しません。
4. `workboard` namespace と Secret `workboard-db` を作成し、`overlays/kind` を `kubectl apply -k` で適用（移行 Job は毎回削除してから）。
5. `argocd` namespace に Argo CD v3.6.1 の公式 `install.yaml` を server-side apply。`monitoring` に Prometheus を適用。
6. PostgreSQL・migration Job・Web/API・Prometheus・Argo CD の準備完了と、Application の CRD が使えることを待機。
7. `argocd/application.yaml` を適用し、`repoURL` / `targetRevision` を「前提条件」の順で決めた値に書き換えます（ファイルの値はプレースホルダーです）。使った値は「Argo CD の同期対象: …」として表示されます。

期待結果は、Node が 3 台とも Ready、API が 3/3、Web が 2/2、StatefulSet が 1/1、migration Job が Completed、`monitoring` の Prometheus が 1/1、`argocd` の 7 つの Pod が Running です。Application `workboard` は、Git に Phase 8 の資材が **push されるまで** `ComparisonError` で `Unknown` になります（次の節の 5 で確認します）。

### 3. WorkBoard とメトリクスを確認する

3 つの `port-forward` を、それぞれ別のターミナルで実行したままにします。8084・8085・8087 番が使われていないことを先に確認します。

```text
kubectl --context kind-workboard-phase8 -n workboard port-forward --address 127.0.0.1 svc/workboard-web 8084:80
kubectl --context kind-workboard-phase8 -n monitoring port-forward --address 127.0.0.1 svc/prometheus 8087:9090
kubectl --context kind-workboard-phase8 -n argocd port-forward --address 127.0.0.1 svc/argocd-server 8085:443
```

[http://localhost:8084](http://localhost:8084) でダミータスクを作ります。次に、リクエストを一定間隔で送り続けます（別のターミナル）。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/08-devops-observability/scripts/watch-http.ps1 http://localhost:8084/api/v1/tasks 0.5
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/08-devops-observability/scripts/watch-http.sh http://localhost:8084/api/v1/tasks 0.5
```

`port-forward` は起動時に選ばれた 1 つの Web Pod にだけつながります。その Pod が削除されると接続が切れるので、切れたらコマンドを再実行します。

Prometheus の接続確認と、収集対象の確認です。

**Windows (PowerShell):**

```powershell
curl.exe -s http://localhost:8087/-/ready
curl.exe -s "http://localhost:8087/api/v1/query?query=up"
```

**Linux / macOS / WSL (Bash):**

```bash
curl -s http://localhost:8087/-/ready
curl -s "http://localhost:8087/api/v1/query?query=up"
```

[http://localhost:8087/targets](http://localhost:8087/targets) で `workboard-api` の対象が API Pod の数だけ `UP` になっていることを確認します。Pod の名前と IP がどのラベルから来ているかも見ます。

### 4. PromQL でリクエスト率・エラー率・p95 を求める

[http://localhost:8087/graph](http://localhost:8087/graph) の入力欄に貼り付けて、それぞれ Table と Graph で見ます（`watch-http` を流したままにします）。ヘルスチェック（`/health/*`）は kubelet が呼ぶため、利用者のリクエストと分けて除外しています。

```text
sum(rate(workboard_http_requests_total{route!~"/health/.*"}[1m]))
```

```text
sum(rate(workboard_http_requests_total{route!~"/health/.*",status=~"5.."}[5m])) / sum(rate(workboard_http_requests_total{route!~"/health/.*"}[5m]))
```

```text
histogram_quantile(0.95, sum by (le) (rate(workboard_http_request_duration_seconds_bucket{route!~"/health/.*"}[5m])))
```

```text
sum by (route, status) (increase(workboard_http_requests_total{route!~"/health/.*"}[5m]))
```

```text
process_resident_memory_bytes{job="workboard-api"}
```

```text
changes(process_start_time_seconds{job="workboard-api"}[1h])
```

観察する点は以下です。

- リクエスト率が `watch-http` の間隔（0.5 秒なら毎秒約 2）と合うか。
- 4xx（存在しない ID など）がエラー率に入るか入らないか。入れるかどうかは、SLI の定義で決めること。
- ヒストグラムの p95 が、バケットの境界の値になる理由。
- `process_*` から読めるもの（API Pod の再起動、メモリ）と、読めないもの（Web Pod、ノード、DB の状態）。

エラー率の式の分母が 0 のときの表示（`NaN` や空）と、新しく現れた系列に対する `increase` の値も観察します。

### 5. Argo CD を開き、push 前の状態を確認する

初期の管理者パスワードは、ローカルの Secret から取り出します（この kind クラスターだけの値です。共有や記録をしないでください）。ユーザー名は `admin` です。

**Windows (PowerShell):**

```powershell
kubectl --context kind-workboard-phase8 -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | ForEach-Object { [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($_)) }
```

**Linux / macOS / WSL (Bash):**

```bash
kubectl --context kind-workboard-phase8 -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
```

[https://localhost:8085](https://localhost:8085) を開きます（自己署名証明書の警告が出ます。この `port-forward` 経由の localhost だけで使います）。

```text
kubectl --context kind-workboard-phase8 -n argocd get application workboard
kubectl --context kind-workboard-phase8 -n argocd get application workboard -o jsonpath='{.spec.source.repoURL}{"\n"}{.spec.source.targetRevision}{"\n"}{.status.conditions[*].message}{"\n"}'
```

Application が参照する `repoURL`・`targetRevision`・`path` と、同期の状態を確認します。**Git に push されていないリビジョンは同期できません。** clone した直後や、Phase 8 の変更を自分のリポジトリにまだ push していない場合は `ComparisonError` になります。

同期できるようにする手順は 2 通りです。どちらも、自分でコミットし push する操作を伴います（push は学習者が自分の判断で行います）。

- 自分の fork に Phase 8 の資材を push し、`up` を再実行する。`origin` が自分の fork で、push したブランチにいれば、環境変数は要りません。別のリポジトリやブランチを同期したいときは、下のように環境変数を付けて再実行します。
- リポジトリが非公開の場合、Argo CD にリポジトリの認証情報の登録が必要です。この Lab は公開リポジトリだけを前提にします（非公開リポジトリの認証情報の扱いは対象外）。

**Windows (PowerShell):**

```powershell
$env:GITOPS_REPO_URL = 'https://github.com/<自分のユーザー>/<リポジトリ>.git'
$env:GITOPS_REVISION = '<ブランチ>'
powershell -NoProfile -File phases/08-devops-observability/scripts/up.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
GITOPS_REPO_URL='https://github.com/<自分のユーザー>/<リポジトリ>.git' GITOPS_REVISION='<ブランチ>' bash phases/08-devops-observability/scripts/up.sh
```

### 6. 同期、drift、revert を観察する

Git に push 済みのリビジョンを参照できるようになってからの手順です。Application は既定で手動同期です（`syncPolicy` が無い）。

画面の「Refresh」と「Sync」を使うか、次のコマンドを使います。

**Windows (PowerShell):**

```powershell
kubectl --context kind-workboard-phase8 -n argocd annotate application workboard argocd.argoproj.io/refresh=hard --overwrite
kubectl --context kind-workboard-phase8 -n argocd patch application workboard --type merge -p '{\"operation\":{\"sync\":{}}}'
kubectl --context kind-workboard-phase8 -n argocd get application workboard
```

**Linux / macOS / WSL (Bash):**

```bash
kubectl --context kind-workboard-phase8 -n argocd annotate application workboard argocd.argoproj.io/refresh=hard --overwrite
kubectl --context kind-workboard-phase8 -n argocd patch application workboard --type merge -p '{"operation":{"sync":{}}}'
kubectl --context kind-workboard-phase8 -n argocd get application workboard
```

期待結果は `SYNC STATUS` が `Synced`、`HEALTH STATUS` が `Healthy` です。最初の同期の前は、`kubectl apply` で作った既存のリソースも `OutOfSync` と表示されることがあります。何が違うのか、画面の Diff で確認します。移行 Job が同期のたびに作り直されることも確認します。

```text
kubectl --context kind-workboard-phase8 -n argocd get application workboard -o jsonpath='{.status.sync.revision}{"\n"}'
kubectl --context kind-workboard-phase8 -n workboard get job,pods
```

### 7. CI をローカルで再現する

`.github/workflows/ci.yaml` の各ジョブと同じ内容を、手元で確認できます。GitHub 上の実行結果は、push した後に Actions の画面で確認します。

| ジョブ | ローカルでの確認（リポジトリ直下） |
| --- | --- |
| `api` | `docker build --target test` したイメージを、一時的な PostgreSQL（`workboard_test`）につないで `alembic upgrade head` と `pytest`。終わったら一時コンテナとネットワークを削除する |
| `web` | `app/web` で `npm ci` と `npm run build` |
| `portal` | `python -m unittest discover -s learning-portal/tests`、`learning-portal` で `npm ci` と `npm run build` |
| `images` | `docker build --target runtime app/api`、`docker build app/web` |
| `manifests` | `kubectl kustomize` を、overlay ごとに実行する（Git 管理外の `secrets/*.env` は、`*.env.example` のコピーで足りる） |
| `terraform` | `terraform fmt -check -recursive phases`、`phases/*/terraform` ごとに `init -backend=false` と `validate` |
| `scripts` | `bash -n`、PowerShell の構文解析 |

**Windows (PowerShell):**

```powershell
python -m unittest discover -s learning-portal/tests
kubectl kustomize phases/08-devops-observability/kustomize/overlays/kind | Out-Null; $LASTEXITCODE
terraform -chdir=phases/08-devops-observability/terraform init -backend=false
terraform -chdir=phases/08-devops-observability/terraform validate
```

**Linux / macOS / WSL (Bash):**

```bash
python3 -m unittest discover -s learning-portal/tests
kubectl kustomize phases/08-devops-observability/kustomize/overlays/kind > /dev/null; echo $?
terraform -chdir=phases/08-devops-observability/terraform init -backend=false
terraform -chdir=phases/08-devops-observability/terraform validate
```

`terraform init` は `.terraform/` を作ります（Git の対象外）。ジョブ内で `uses:` のアクションがコミット SHA で固定されている理由と、`permissions` が `contents: read` だけである理由を確認します。

## CI/CD（AWS 承認後に学習者が行う）

CI（`ci.yaml`）は push と pull request ごとに動き、AWS の認証情報を使いません。CD（`cd.yaml`）は `workflow_dispatch`（手動実行）だけで、GitHub の environment **`lab`** の承認を待ってから動きます。

### AWS 側（Terraform）

Phase 6 の EKS クラスターと Phase 7 の RDS が稼働している状態で、GitHub の OIDC プロバイダーと CD 用 IAM ロールを作ります。**`terraform apply` は AWS の利用を承認した後に、学習者が自分で実行します。**

```text
terraform -chdir=phases/08-devops-observability/terraform init
terraform -chdir=phases/08-devops-observability/terraform plan
terraform -chdir=phases/08-devops-observability/terraform apply
```

変数は `terraform.tfvars.example` をコピーした `terraform.tfvars`（Git 管理外）に書きます。`github_repository` は CD を動かす GitHub リポジトリ（`owner/name`）です。`plan` の出力で、作られるリソース（OIDC プロバイダー、IAM ロール、ロールのインラインポリシー、EKS の access entry と access policy association）と、信頼ポリシーの条件（`aud` と `sub`）、ロールの権限（ECR の push 先、`eks:DescribeCluster` の対象、Secrets Manager の対象）を読んでから承認します。同じ URL の OIDC プロバイダーが既にあるアカウントでは、`create_github_oidc_provider = false` にします。

### GitHub 側

1. リポジトリの Settings > Environments で `lab` を作り、Required reviewers に承認者を設定する。Deployment branches を `main` だけに制限するかを判断する。
2. Settings > Secrets and variables > Actions > **Variables**（Secrets ではありません）に、次を設定する。長期のアクセスキーは設定しません。

| 変数 | 値の出どころ |
| --- | --- |
| `AWS_REGION` | クラスターのリージョン（例 `ap-northeast-1`） |
| `AWS_ROLE_ARN` | Phase 8 の `terraform output cd_role_arn` |
| `EKS_CLUSTER_NAME` | Phase 6 のクラスター名（既定 `workboard-learning`） |
| `RDS_ENDPOINT` | Phase 7 の `terraform output db_endpoint_address` |
| `ALLOWED_CIDR` | ALB を公開する自分の IP の `/32`（`0.0.0.0/0` は不可） |
| `DB_SECRET_ARN` | Phase 7 の `terraform output db_master_secret_arn` |

3. Actions の画面から `cd` を手動実行する。承認者が承認するまでジョブは開始されない。未設定の変数があれば、最初のステップが変数名を挙げて失敗する。

CD は、イメージをコミット SHA のタグで ECR に push し、Phase 7 の `eks` overlay のイメージとエンドポイントなどを実際の値に置き換えて `kubectl apply` します。Namespace（`workboard`）は Phase 7 で作成済みであることが前提です。DB のパスワードは、実行時に Secrets Manager から取り出して `db.env` に書きます（ログではマスクされます）。

CD は、このリポジトリの CI が成功していることを確認しません。実行する前に、対象のコミットで `ci` が成功していることを自分で確認します。

### AWS のコストを確認し、不要な環境を削除する

**AWS を操作する前に、見積もりと承認を確認します。** [Phase 6 の見積もり](../06-eks-foundation/cost-estimate.md)と[削除手順](../06-eks-foundation/aws-cleanup.md)、[Phase 7 の見積もり](../07-aws-integration/cost-estimate.md)と[削除手順](../07-aws-integration/aws-cleanup.md)を読みます。

1. **AWS Budgets:** 月額の予算を作り、実績と予測の通知先（メール）を設定する。**通知は課金の停止を保証せず、遅れもあります。**
2. **Cost Explorer:** 日次の粒度で、サービス別・タグ別（`Project=workboard-learning`、`Phase`）に費用を見る。有料リソースを作った日の翌日以降に、増えた費用が EKS・EC2・NAT・RDS・ELB・パブリック IPv4 のどれかを確認する。コスト配分タグは、有効化してから反映されるまで時間がかかります。API（`aws ce get-cost-and-usage`）は 1 回ごとに課金されるため、画面で見ることを勧めます。
3. **削除の仕組みを検討する:** 学習が終わった日時と削除担当を決め、削除手順の順序（CD 用ロールの Terraform → Phase 7 → Phase 6）をカレンダー等に残す。EventBridge Scheduler などで通知を出す案、タグで残存リソースを棚卸しする案を比較し、自動削除を採る場合の危険（誤削除）を考える。
4. **Phase 8 の Terraform を先に削除する:** CD 用ロールの access entry がクラスターに依存するため、`terraform destroy`（Phase 8）を Phase 6 より先に行う。ECR には CD が push した SHA タグのイメージが残るので、削除前に確認する。

## 故障実験

**ダミーデータを失ってよいと確認できた場合だけ実行してください。** 対象は `workboard-phase8` だけです。各実験の前に、3 の `watch-http` と 4 の PromQL（Graph）を流し、実験を始めた時刻、メトリクスが変化した時刻、元に戻った時刻を記録します。

### A. 手動の変更（drift）を検出し、直す

6 の同期が済んで `Synced` の状態から始めます（push できない場合は、実験 A・B を省略し、その理由を記録します）。

```text
kubectl --context kind-workboard-phase8 -n workboard scale deployment/workboard-web --replicas=5
kubectl --context kind-workboard-phase8 -n argocd get application workboard
kubectl --context kind-workboard-phase8 -n workboard get deployment workboard-web
```

Argo CD が `OutOfSync` と表示するまでの時間、Diff に出る項目、Web の Pod 数を記録します。次に、手動同期で Git の値に戻し、さらに自動修復を一時的に有効にして、同じ手動変更が戻るまでの時間を記録します。

**Windows (PowerShell):**

```powershell
kubectl --context kind-workboard-phase8 -n argocd patch application workboard --type merge -p '{\"spec\":{\"syncPolicy\":{\"automated\":{\"selfHeal\":true}}}}'
kubectl --context kind-workboard-phase8 -n workboard scale deployment/workboard-web --replicas=4
kubectl --context kind-workboard-phase8 -n workboard get deployment workboard-web
kubectl --context kind-workboard-phase8 -n argocd patch application workboard --type json -p '[{\"op\":\"remove\",\"path\":\"/spec/syncPolicy\"}]'
```

**Linux / macOS / WSL (Bash):**

```bash
kubectl --context kind-workboard-phase8 -n argocd patch application workboard --type merge -p '{"spec":{"syncPolicy":{"automated":{"selfHeal":true}}}}'
kubectl --context kind-workboard-phase8 -n workboard scale deployment/workboard-web --replicas=4
kubectl --context kind-workboard-phase8 -n workboard get deployment workboard-web
kubectl --context kind-workboard-phase8 -n argocd patch application workboard --type json -p '[{"op":"remove","path":"/spec/syncPolicy"}]'
```

最後の `patch` で、自動修復を無効に戻します。

### B. 不正なコミットを同期し、revert で戻す

`kustomize/overlays/kind/kustomization.yaml` の `workboard-web` の `newTag` を、存在しないタグに書き換えてコミットし、push します。Argo CD で更新を取り込み、同期します。

```text
kubectl --context kind-workboard-phase8 -n workboard get pods -l app=workboard-web
kubectl --context kind-workboard-phase8 -n workboard get deployment workboard-web
kubectl --context kind-workboard-phase8 -n argocd get application workboard
```

Argo CD の同期状態（`SYNC STATUS`）と健全性（`HEALTH STATUS`）がそれぞれどう変わるか、旧 Pod が残るか、`watch-http` の応答が変わるかを記録します。次に、そのコミットを `git revert` で打ち消して push し、同期して、状態が戻るまでを記録します。`kubectl rollout undo` と何が違うか（何が元の状態を決めるか）も考えます。

### C. DB のロックで遅延を作り、p95 の変化を観察する

テーブルに排他ロックを 20 秒間保持するセッションを、別のターミナルで実行します。DB は動き続け、Readiness は成功したままです。ロック中も `watch-http` を流します。

```text
kubectl --context kind-workboard-phase8 -n workboard exec workboard-postgres-0 -- sh -c "psql -U workboard -d workboard -c 'BEGIN; LOCK TABLE tasks IN ACCESS EXCLUSIVE MODE; SELECT pg_sleep(20); COMMIT;'"
```

`watch-http` の応答時間とステータス、Prometheus の p95 とリクエスト率、`/api/v1/tasks` の `route` ごとの値を記録します。Web（Nginx）が返したエラーが API のメトリクスに現れるか、現れないかも確認します。

### D. DB を止めてエラー率を上げる

```text
kubectl --context kind-workboard-phase8 -n workboard scale statefulset/workboard-postgres --replicas=0
kubectl --context kind-workboard-phase8 -n workboard get pods -l app=workboard-api
kubectl --context kind-workboard-phase8 -n workboard scale statefulset/workboard-postgres --replicas=1
kubectl --context kind-workboard-phase8 -n workboard rollout status statefulset/workboard-postgres --timeout=120s
```

`watch-http` のステータスの順序、Prometheus のエラー率、`status` ごとの件数を記録します。メトリクスに現れる 5xx と、利用者が見た 5xx が一致するか確認します。Pod 数や Readiness の変化は、`kubectl` の出力とメトリクスのどちらで分かるかも比べます。

## 失敗時に確認すること

- 接続先が違う: `. .\phases\08-devops-observability\scripts\env.ps1`（Bash は `source phases/08-devops-observability/scripts/env.sh`）を読み込んだか。context が `kind-workboard-phase8` か。
- `up` が Argo CD の取得で失敗する: GitHub（`raw.githubusercontent.com`）に接続できるか。プロキシ等の設定を確認する。
- Argo CD の CRD の適用が `annotation too long` で失敗する: `--server-side` で適用しているか。
- Application が `ComparisonError`: メッセージを読む。`Repository not found` や `authentication required` は、`repoURL` が存在しない、または非公開。`revision ... not found` は `targetRevision` が push されていない。`app path does not exist` は `path` がそのリビジョンに無い。
- Application が `OutOfSync` のまま戻らない: 画面の Diff を読む。手動変更か、Git 側の変更か。移行 Job や Secret は同期の対象外（Job は hook、Secret は Git に無い）であることを思い出す。
- Prometheus の対象が 0 件、または `DOWN`: `/targets` のエラーを読む。`pods is forbidden` は RBAC（`prometheus-discovery` Role と RoleBinding）。`connection refused` は API Pod の起動前、またはポート違い。
- PromQL が空: `watch-http` で実際にリクエストを送っているか。`[1m]` や `[5m]` の窓より長い間、系列が存在しているか。スクレイプ間隔（15 秒）より短い窓では値が出ない。
- Prometheus の過去のデータが消えた: データは `emptyDir` で、Pod の作り直しで消える。
- API が Ready にならない: `logs deployment/workboard-api` の認証エラー。`db.env` と Secret `workboard-db` が、DB を初期化した値と一致しているか。
- `ErrImageNeverPull`: `kind load docker-image ... --name workboard-phase8` が成功したか（`up` を再実行する）。実験 B では意図した動作。
- 8084 / 8085 / 8087 が使えない: 他のプロセスが使用中でないか確認し、解放できる場合だけ解放する。
- CD が最初のステップで失敗する: 表示された変数名を repository variables に設定する。
- CD の `Configure AWS credentials` が `Not authorized to perform sts:AssumeRoleWithWebIdentity`: 信頼ポリシーの `sub`（リポジトリ名と environment 名）と、ジョブの environment が一致しているか。environment の承認が済んでいるか。
- CD の `kubectl` が `Forbidden`: access entry とポリシーの関連付けが作られているか。許可は `workboard` namespace だけで、他の namespace やクラスター単位のリソースには届かない。

## Linux / macOS / WSL での前提

スクリプトは PowerShell 版と同じ処理の Bash 版（`phases/08-devops-observability/scripts/` の `env.sh`・`up.sh`・`watch-http.sh`、導入は Phase 2 と共通の `tools/kind-install.sh`）があり、上の手順の「Linux / macOS / WSL (Bash)」に従います。Bash 4 以降、Docker（WSL は Docker Desktop の WSL 統合）、kubectl 1.34〜1.36、`curl` が必要です。その他の条件は Phase 2 の「Linux / macOS / WSL での前提」と同じです。

## 後片付け・再構築

`port-forward` を実行しているターミナルで `Ctrl+C` を押すと入口だけが閉じます。クラスターとアプリは動き続けます。実験 A で `selfHeal` を有効にしたままなら、無効に戻します。

`workboard-phase8` を削除すると、PVC/PV に保存した DB のデータ、Prometheus のデータ、Argo CD の状態も失われます。クラスター名と消えるデータを確認し、削除してよいと明示的に判断した場合だけ以下を使います。他のクラスターは対象外です。

```text
kind delete cluster --name workboard-phase8
```

削除後、専用 kubeconfig `.kube/workboard-phase8.yaml` が残っていれば対象を確認してそのファイルだけ削除します。`db.env` は残して再利用できます。**クラスター（PVC）を残したまま `db.env` を消さないでください。** 構築スクリプトが別のパスワードを生成し、初期化済みの DB と一致しなくなります。

AWS 側に作った資源（CD 用ロール、OIDC プロバイダー、ECR のイメージ）の削除は、「AWS のコストを確認し、不要な環境を削除する」の順序に従い、対象と影響を確認してから学習者が行います。

## 完了条件

- [ ] `ci.yaml` の各ジョブがローカルで何に当たるかを説明し、ローカルで再現できる範囲を実行した。
- [ ] `cd.yaml` と `github-oidc.tf` を読み、手動承認・OIDC の信頼条件・最小権限が、それぞれ何を防ぐかを説明できる。
- [ ] `workboard-phase8` で、API の 3 Pod が Prometheus の対象になり、リクエスト率・エラー率・p95 の PromQL が値を返すことを確認した。
- [ ] Argo CD の Application が参照する先と、push 前に同期できない理由を確認した。
- [ ] （push できる場合）同期、drift の検出と自動修復、不正なコミットの revert による復旧を観察した。できない場合は、省略した理由を記録した。
- [ ] 故障実験 C・D で、遅延とエラーがメトリクスにどう現れ、何が現れないかを記録した。
- [ ] Git に置けない値の扱い、Helm と Kustomize の選択、SLO の定義について、自分の判断を説明できる。
- [ ] AWS のコスト確認と削除の流れを、自分の手順として書き出した（AWS 操作は承認後）。
- [ ] 下記に結果・未実施の実験・設計課題への回答を記録した。
- [ ] 設計課題に答えた**後で** [ADR-0015（提案）](decisions/0015-delivery-and-gitops.md)と[ADR-0016（提案）](decisions/0016-helm-vs-kustomize-for-workboard.md)を読み、自分の回答と比べた。納得できたら ADR の Status を「採用」に変更し、異なる判断をした点は理由を学習ポータルの学習メモに残した。

## 学習メモ

学習ポータルの学習メモに、次の項目を記録します。

- CI の各ジョブがローカルで何に当たるか、再現できなかった範囲
- CD の手動承認・OIDC の信頼条件・ロールの権限について読み取れたこと
- Prometheus の対象の一覧と、PromQL の結果（リクエスト率・エラー率・p95）
- 4xx と 5xx の扱い、ヒストグラムの p95 の粒度についての気づき
- Argo CD の Application の状態（push 前の `ComparisonError` のメッセージ、同期後の状態）
- 故障実験 A（drift）の検出までの時間と、自動修復までの時間（実施した場合）
- 故障実験 B（不正なコミットと revert）の SYNC STATUS・HEALTH STATUS・Pod の状態・復旧までの時間（実施した場合）
- 故障実験 C（DB ロックによる遅延）の応答時間・p95・Web が返したエラーのメトリクスへの現れ方
- 故障実験 D（DB 停止）のステータスの順序・エラー率・利用者が見たエラーとメトリクスの差
- 設計課題 1〜7 への回答と、ADR-0015・ADR-0016 との違い
- AWS コスト確認と削除の流れ（実行した場合は結果、していない場合は計画）
- 後片付け・残したクラスター
- 疑問・未解決事項

## 実装時の検証記録

2026-11-10、Windows 11・PowerShell 5.1・Git Bash、Docker Desktop の Linux エンジン、kubectl v1.34.1（Kustomize v5.7.1）、kind v0.33.0、Kubernetes v1.35.8、Terraform 1.17.1、Argo CD v3.6.1、Prometheus v3.15.1 で実装担当が確認しました。学習者自身の記録は README ではなく学習ポータルに残します。時刻・秒数は目安です。

| 確認・コマンド | 結果 |
| --- | --- |
| PowerShell スクリプト 3 本の構文解析（全 `.ps1` 対象）、`bash -n`（全 `.sh` 対象） | エラーなし。`.ps1` は UTF-8 BOM 付き、`.sh` は LF・BOM なしで実行権限あり |
| `python -m unittest discover -s learning-portal/tests` | 29 件が成功 |
| API: `docker build --target test` のイメージを一時 PostgreSQL（`workboard_test`）につなぎ `alembic upgrade head` と `pytest` | 18 件が成功。一時コンテナとネットワークは削除。CI の `api` ジョブそのものは実行していない（Windows のアプリ制御で、一時 venv の DLL が読み込めなかったため Docker で代替） |
| Web・学習ポータル: リポジトリのコピー上で `npm ci` と `npm run build` | どちらも成功 |
| `kubectl kustomize`（`ci.yaml` の `manifests` ジョブと同じ検索条件、`*.env.example` のコピーで Secret を用意） | 8 件（Phase 3〜8 の overlay と Phase 4 の metrics-server、Phase 8 の monitoring）がすべて成功 |
| `terraform fmt -check -recursive phases` | 差分なし |
| `terraform init -backend=false` と `validate`（Phase 6・7・8 の各 `terraform`） | 3 件とも成功。Phase 8 の lock は Phase 6 のコピーで、`init` 後も変わらなかった |
| `.github/workflows/ci.yaml`・`cd.yaml` の YAML 構文（PyYAML で読み込み） | 成功。`actionlint` と GitHub 上の実行は未実施 |
| `cd.yaml` の置換処理（`sed -E`）を Phase 7 の描画結果に適用 | レジストリ・RDS エンドポイント・CIDR・コミット SHA のタグに置き換わることを確認（初版の `\|` を使う書き方はタグが置換されず、`-E` と `#` 区切りに修正）。`yq` の Namespace 除外と、必須変数の確認ステップは、GitHub 上では未実行（変数の確認ロジックはシェル単体で確認） |
| `up.ps1` で `workboard-phase8` を新規作成 | 終了コード 0（イメージのビルドを含め約 8 分）。Node 3 台 Ready、API 3/3、Web 2/2、StatefulSet 1/1、migration Job Completed、Prometheus 1/1、Argo CD の 7 Pod が Running。`db.env` はランダム値を自動生成（値は出力しない） |
| Application `workboard`（既定の `repoURL`、リポジトリを push していない状態） | `Unknown`、`ComparisonError`: `failed to list refs: authentication required: Repository not found.` |
| `up.ps1` の再実行（`GITOPS_REPO_URL`・`GITOPS_REVISION` を設定） | 終了コード 0。Application の `repoURL`・`targetRevision` が指定値に書き換わった |
| WSL2 上の `up.sh` の再実行（同じ環境変数） | 終了コード 0、同じ完了メッセージ。Git Bash（WSL なし）では `.tools` の Linux 版 `kind` を実行できず、`up.sh` は途中で停止した（Phase 2 から続く既存の制約） |
| 同期先の決め方の変更後（`GITOPS_REPO_URL` → clone の `origin`、`GITOPS_REVISION` → 今のブランチ）の、URL・ブランチを決める関数だけを PowerShell と Bash で単体実行 | SSH 形式（`git@…`、`ssh://git@…`）は HTTPS に、`https://user:token@…` は認証情報を除いた URL になった。環境変数が無いときは `origin` とブランチ（`main`）が使われた。`origin` を読めないとき（`dubious ownership`）は git のメッセージの後に案内を出して停止した。変更後の `up` 全体をクラスターで再実行してはいない |
| Prometheus の対象 | `up{job="workboard-api"}` が 3 件とも 1（`pod`・`node` のラベル付き）。`/targets` は未確認、API で確認 |
| PromQL（`watch-http` 相当のリクエストを送った後） | リクエスト率、`status` ごとの `increase`（200・404・201 など）、p95、`process_resident_memory_bytes`（各 Pod 約 87 MB）、`changes(process_start_time_seconds)`（0）が値を返した |
| 故障実験 C: `tasks` に 20 秒の排他ロック | ロック中の 5 回の `curl`: 504（約 10.0 秒）、200（約 8.0 秒）、以降は約 0.01 秒の 200。`/api/v1/tasks` の p95 は 10（最大バケットの境界）。504 は Nginx が返したもので、API は処理が終わってから記録する |
| 故障実験 D: PostgreSQL を `scale 0`（約 14 秒間、毎秒 1 回の `curl`） | 500 が 3 回、その後 502。`workboard_http_requests_total` には `/api/v1/tasks` の 500 が各 Pod に 1 件、`/health/ready` の 503 が各 Pod に 34 件（kubelet の Probe）。502 は API に届かず記録されない。復帰の約 40 秒後に 200 |
| 同上、エラー率の式（ヘルスチェックの除外なし、窓 5 分） | 約 0.049。ヘルスチェックの 503 が大半を占めたため、`route!~"/health/.*"` を付けた式に直した。初めて現れた `status="500"` の系列は `increase` が 0 のまま |
| Argo CD と Git: 外部のリポジトリは使わず、このリポジトリの Phase 8 のコピーを置いたクラスター内の Git で検証 | 下の 4 行 |
| HTTP の Git（`python -m http.server` による dumb HTTP）を `repoURL` に指定 | `failed to list refs: unexpected EOF` で失敗。Argo CD は smart HTTP を必要とする。そのため repo-server の Pod 内で `git daemon` を起動し、`git://127.0.0.1/repo.git` を `repoURL` にした（この方法は検証用で、教材の手順には含めない） |
| 初回の比較と同期 | `kubectl apply` で作ったリソースがすべて `OutOfSync`（Namespace、ConfigMap、Service 3、Deployment 2、StatefulSet、PDB）。手動同期後は `Synced` / `Healthy`。移行 Job が hook として再実行され Completed |
| 実験 A: `scale deployment/workboard-web --replicas=5` | 約 8 秒後に `OutOfSync`（`Deployment workboard-web` のみ）。手動同期で 2/2 に戻った。`selfHeal` を有効にして `--replicas=4` にすると、15 秒後の確認で 2/2 に戻っていた（戻るまでの正確な時間は未計測）。`syncPolicy` は削除して手動同期に戻した |
| 実験 B: Web の `newTag` を存在しない値にしたコミットを同期 | `Synced` / `Progressing`。新 Pod は `ErrImageNeverPull`、旧 2 Pod は Ready のまま、Deployment は 2/2（UP-TO-DATE 1）。`git revert` したコミットを同期すると `Synced` / `Healthy`、Pod は旧 2 つだけになった。この間の HTTP 応答は測定していない |
| 後片付け | 検証用の Git の Pod と namespace、`workboard-phase8` クラスター、`.kube/workboard-phase8.yaml`、生成した `db.env`、自分の `port-forward` を削除・停止した。既存のクラスターと kubeconfig は触っていない |

未実施・未検証: GitHub Actions 上での CI/CD の実行と `actionlint`、`yq` による Namespace の除外、OIDC による AWS への接続、Terraform の `plan`/`apply`（`AmazonEKSEditPolicy` を namespace に限定した状態で Phase 7 の overlay が適用できるかを含む）、GitHub の公開リポジトリを使った Argo CD の同期（push していない）、Argo CD が非公開リポジトリを読む設定、Windows の Docker Desktop 以外・ネイティブ Linux・macOS での実行、実験 A の自動修復までの正確な時間、実験 B 中の HTTP 応答、実験 C・D 中の Prometheus の窓ごとの値の推移。AWS は使用していません。
