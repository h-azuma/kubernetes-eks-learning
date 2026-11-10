# Lab 07: EKS と AWS マネージドサービス連携

## 学習目標

- DB を Kubernetes の外（Amazon RDS）に置く理由を、責任分界・障害時の影響・費用から説明する。
- RDS を private subnet に置き、EKS のノードからだけ接続できるようにするネットワーク（セキュリティグループ）を説明する。
- AWS Load Balancer Controller を Helm chart で導入する前に、生成されるマニフェスト（ServiceAccount、RBAC、Deployment、Webhook、CRD）を読んで中身を把握する。
- Pod Identity で、特定の ServiceAccount だけに IAM ロールを渡す仕組みと、最小権限の考え方を説明する。
- Ingress（`alb`）で ALB を作り、許可した IP だけに公開して疎通を確認し、公開の制限と後片付けの順序を説明する。
- `helm list` / `helm history` / `helm rollback` で release の状態と rollback の単位を観察する。

## 前提条件

**この Lab は AWS の有料リソースを作ります（EKS に加えて RDS と ALB）。** 次の開始条件をすべて満たしてから、AWS を操作する手順に進みます。

1. **ユーザー（学習者本人）による AWS 利用の明示承認。** `terraform apply` と AWS を変更する操作は、承認した後に自分の手で実行します。この教材の作成者（AI を含む）は AWS を操作しません。
2. **見積もり金額の確認。** [cost-estimate.md](cost-estimate.md) の「要確認」の値を公式の料金ページで埋め、Phase 6 の見積もりと合算した合計を確認します。
3. **予算通知の設定。** AWS Budgets 等で通知を設定します。**予算通知は課金の停止を保証しません。**
4. **クリーンアップ手順のレビュー。** [aws-cleanup.md](aws-cleanup.md) を読み、削除の順序（Ingress → Helm → RDS → Terraform）と日時を決めます。

**稼働中の EKS クラスターが必要です。** Phase 6 で作ったクラスターを使います（EKS を 2 回作らないため）。この Phase の Terraform は Phase 6 のディレクトリや state を読まず、変数 `cluster_name`（既定 `workboard-learning`）と data source で、次の約束を前提に既存のクラスターを見つけます。

- クラスターが存在し、Managed Node Group のノードがクラスターのセキュリティグループを使っている。
- private subnet に `kubernetes.io/role/internal-elb=1`、public subnet に `kubernetes.io/role/elb=1` のタグがある（ALB の配置に必要）。
- ECR に `workboard-api` / `workboard-web` のリポジトリがある。
- 自分の IAM 主体が、クラスターの管理者（access entry）になっている。

別の方法で作ったクラスターを使う場合は、この約束を満たすか確認します。ツールは Terraform 1.17.x、AWS CLI v2、kubectl 1.34〜1.36、Helm 4.x（検証は 4.3.1）、Docker（Linux コンテナエンジン）です。Bash では `python3`（`write-db-secret` が JSON を読むために使用）も必要です。実際のアカウント ID、認証情報、`terraform.tfvars`、`terraform.tfstate`、`secrets/db.env` を Git に入れないでください（`.gitignore` の対象です）。

この Phase の資材は `phases/07-aws-integration/` だけで完結します。Web/API の定義は Phase 3・6 と重複しています（[ADR-0007](../../docs/adr/0007-phase-directory-layout.md) の意図的な重複）。community の ingress-nginx は使いません（2026-03-24 に引退済み）。

## 設計課題（実装前に考える）

1. なぜ PostgreSQL を Kubernetes の Pod ではなく RDS に置くのか？ 何が楽になり、何が増えるか？
2. RDS が停止・接続不能になったとき、API の Readiness はどう変わるか？ Service・ALB・ユーザーには何が見えるか？ ALB の health check はどこを見るべきか？
3. 第三者の Helm chart を導入するとき、何を確認すれば「中身を把握した」と言えるか？
4. RDS のネットワーク（subnet、セキュリティグループ）はどう設計するか？ 誰からのどの通信だけを許可するか？
5. DB のパスワードをどこで生成・保管し、Pod にどう渡すか？ ローテーションされたらどうなるか？
6. AWS Load Balancer Controller に、AWS API を呼ぶ権限をどう渡すか？ なぜ最小権限が必要か？ ノードのロールに付けるのと何が違うか？
7. ALB を公開する範囲をどう制限するか？ 検証後に何を、どの順序で片付けるか？
8. ローカルの DB のデータをどう RDS に移すか？ バックアップと復元（時点復元を含む）をどう設計するか？

## 実装タスク

1. [構成図](architecture.md)、[ADR-0005](../../docs/adr/0005-kubernetes-ecosystem-tools.md) の Helm の節を読む。
2. `terraform/`、`helm/`、`kustomize/` を読み、Phase 6 のクラスターとどう接続するかを書き出す。LBC の IAM ポリシー（`terraform/policies/`）を読み、許可される操作を整理する。
3. `helm template` で Controller の生成物を描画し、読む（AWS に接続しない）。
4. 開始条件（前提条件の 1〜4）を満たす。
5. （承認後）`terraform plan` の差分を記録してから `apply`。LBC を Helm で導入し、`helm list` / `history` / `rollback` を観察する。
6. イメージを push し、RDS のパスワードを取り出して Secret の入力を作り、`eks` overlay を適用する。
7. 許可 IP から ALB に疎通し、許可外から拒否されることを確認する。故障実験を行い、削除する。結果を **学習ポータルの学習メモ**（項目は「学習メモ」節）に記録する。

## 検証コマンド・期待結果

すべてリポジトリ直下で実行します。ステップ 1 は AWS に接続せず、いつでも実行できます。ステップ 2 以降は AWS を操作するため、開始条件を満たしてから実行します。AWS を操作するスクリプトは、アカウント・region・クラスター名を表示して `yes` の入力を求めます。

### 1. 適用前に読む（AWS に接続しない）

目的：Terraform ファイルの書式が整っているかを確認します（AWS には接続しません）。

```text
terraform -chdir=phases/07-aws-integration/terraform fmt -check -recursive
```

確認：出力が何もなければ書式は整っています。整っていないファイルがあると、そのファイル名が表示されます。

目的：provider を取得して、次の `validate` を実行できる状態にします。`-backend=false` を付けているので、state の保存先には接続しません。

```text
terraform -chdir=phases/07-aws-integration/terraform init -backend=false
```

確認：`Terraform has been successfully initialized!` が表示されれば成功です。provider を取得するだけで、AWS には接続しません。

目的：Terraform の文法と引数の整合を確認します。

```text
terraform -chdir=phases/07-aws-integration/terraform validate
```

確認：`Success! The configuration is valid.` が表示されれば成功です。`validate` は AWS 側で作成できるかは確認しません。

目的：`eks` overlay を読むため、Secret の入力ファイル `secrets/db.env` にダミー値だけの例ファイルをコピーします（Git に入れません）。実際の値は、後で `write-db-secret` が Secrets Manager から作ります。

**Windows (PowerShell):**

```powershell
Copy-Item phases/07-aws-integration/kustomize/overlays/eks/secrets/db.env.example phases/07-aws-integration/kustomize/overlays/eks/secrets/db.env
```

**Linux / macOS / WSL (Bash):**

```bash
cp phases/07-aws-integration/kustomize/overlays/eks/secrets/db.env.example phases/07-aws-integration/kustomize/overlays/eks/secrets/db.env
```

確認：エラーが出なければ `db.env` が作られています。ダミーのままでは RDS に接続できないため、「5. イメージ、Secret、アプリを用意する」で `write-db-secret` が実際のパスワードで上書きします。

目的：`eks` overlay を生成して、適用前の最終形を読みます。

```text
kubectl kustomize phases/07-aws-integration/kustomize/overlays/eks
```

確認：次の 3 点を見ます。(1) Postgres の Deployment/StatefulSet がなく、`POSTGRES_HOST` がダミーの RDS エンドポイント、`PGSSLMODE=require` が ConfigMap にあること。(2) Ingress の `ingressClassName: alb` と `inbound-cidrs`（ダミー `203.0.113.10/32`）、health check パス。(3) イメージ参照がダミーのアカウント ID であること（`deploy` が実際の値に置き換えます）。

### 2. Helm chart の中身を読む（AWS に接続しない）

Controller を入れる前に、固定した版（chart 3.6.2）の chart と values を確認し、生成されるマニフェストを `helm template` で書き出して読みます。`.tools/` は Git 管理外です。

目的：AWS が公開している Helm chart のリポジトリ `eks` を、Helm に登録します（AWS には接続しません。インターネット上のリポジトリを登録するだけです）。

```text
helm repo add eks https://aws.github.io/eks-charts
```

確認：`"eks" has been added to your repositories` のような表示が出るはずです。すでに登録済みなら、その旨が表示されます。

目的：登録したリポジトリ `eks` の chart 一覧を取得し直します。

```text
helm repo update eks
```

確認：`Successfully got an update from the "eks" chart repository` のような表示が出るはずです。

目的：固定した版（chart 3.6.2）の chart の情報（名前、版、出どころ）を読みます。

```text
helm show chart eks/aws-load-balancer-controller --version 3.6.2
```

確認：`version: 3.6.2` が表示されることを見ます。署名・出典・版（chart の取得元、`helm show chart` の情報、IAM ポリシーの出典。`ADR-0014` は課題の後で読む）を書き出す材料にします。

目的：chart の既定の values（設定できる値と既定値）を読みます。

```text
helm show values eks/aws-load-balancer-controller --version 3.6.2
```

確認：長い YAML が表示されます。イメージの出所とタグ、replica 数、`serviceAccount` などの設定項目を探します。この Phase で上書きする値は `helm/aws-load-balancer-controller-values.yaml` にあります。

目的：Controller の生成物（マニフェスト）を `helm template` で `.tools/lbc-rendered` に書き出して読みます。クラスターには何も適用しません。`.tools/` は Git 管理外です。

```text
helm template aws-load-balancer-controller eks/aws-load-balancer-controller --version 3.6.2 --namespace kube-system --values phases/07-aws-integration/helm/aws-load-balancer-controller-values.yaml --set clusterName=workboard-learning --set region=ap-northeast-1 --set vpcId=vpc-0123456789abcdef0 --include-crds --output-dir .tools/lbc-rendered
```

確認：エラーなく終了し、`.tools/lbc-rendered/` に生成物ができるはずです。生成物を読み、次の点を自分の言葉で書き出します。

- 生成されるリソースの種類と数（ServiceAccount、ClusterRole/Role と Binding、Deployment、Service、Secret、Mutating/ValidatingWebhookConfiguration、IngressClass、CRD）。
- RBAC: 何のリソースに、どの操作を許しているか（Secret の扱いも含む）。
- Deployment: イメージの出所とタグ、引数、`securityContext`、replicas、`serviceAccountName`。
- Webhook: どのリソースの作成・更新に介入し、`failurePolicy` が何か。Controller が止まるとクラスターの操作にどう影響するか。
- Secret: 何のために、どう生成されるか（`helm upgrade` のたびにどうなるか）。
- CRD: `helm install` と `helm upgrade` で CRD の扱いがどう違うか（公式手順の注意）。
- 署名・出典・版: chart の取得元、`helm show chart` の情報、IAM ポリシーの出典（`ADR-0014` は課題の後で読む）。

### 3. （承認後）`terraform plan` の差分を読む

`terraform.tfvars.example` をコピーして `terraform.tfvars` を作り、自分の値に置き換えます。`allowed_account_id` が必須です。`terraform.tfvars` は Git に入れません。

目的：`terraform.tfvars.example` をコピーして、自分の値を入れる `terraform.tfvars` を作ります（`terraform.tfvars` は Git に入れません）。

**Windows (PowerShell):**

```powershell
Copy-Item phases/07-aws-integration/terraform/terraform.tfvars.example phases/07-aws-integration/terraform/terraform.tfvars
```

**Linux / macOS / WSL (Bash):**

```bash
cp phases/07-aws-integration/terraform/terraform.tfvars.example phases/07-aws-integration/terraform/terraform.tfvars
```

確認：エラーが出なければ `terraform.tfvars` が作られています。エディターで `allowed_account_id` を自分の値に置き換えます。

目的：AWS に何が作られるか（差分）を読みます。AWS の認証情報が必要ですが、`plan` は何も作成しません。

```text
terraform -chdir=phases/07-aws-integration/terraform plan
```

確認：出力の末尾に `Plan: N to add, 0 to change, 0 to destroy.` のような件数が表示されるはずです（未検証）。作成されるリソース（RDS、DB subnet group、セキュリティグループ、パラメータグループ、IAM ロールとポリシー、Pod Identity Agent アドオン、association）の種類と数、料金が発生するもの（RDS）を記録します。RDS の `master_user_secret` は Terraform の state にパスワードを持たないこと、`plan` に値が出ないことを確認します。承認した後にだけ `apply` します。

目的：**費用が発生します（RDS）。** `plan` で読んだ差分を AWS に実際に作成します。開始条件を満たし、明示的に判断した後にだけ自分の手で実行します。

```text
terraform -chdir=phases/07-aws-integration/terraform apply
```

確認：RDS の作成には十数分かかります。成功すると `Apply complete! Resources: N added, 0 changed, 0 destroyed.` が表示されるはずです（未検証）。実行前に、`plan` の差分と見積もりの金額を記録し、削除する日時を決めておきます。作成した時点から課金が続くため、学習を終えたら [aws-cleanup.md](aws-cleanup.md) の順序で削除します。

### 4. kubeconfig を作り、Controller を導入する

目的：このシェルだけで Phase 7 用の kubeconfig と region を使う設定にして、以降の `kubectl`・`helm`・AWS CLI がこの Phase の設定を向くようにします。

**Windows (PowerShell):**

```powershell
. .\phases\07-aws-integration\scripts\env.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
source phases/07-aws-integration/scripts/env.sh
```

確認：画面に出力は想定していません。エラーが出なければ設定済みです。Bash で `source` を付けずに実行した場合は、`source` で読み込み直してください。

目的：EKS クラスターに接続するための kubeconfig を作ります。AWS を操作するスクリプトなので、対象のアカウント・region・クラスター名が表示され、`yes` の入力を求められます。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/07-aws-integration/scripts/update-kubeconfig.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/07-aws-integration/scripts/update-kubeconfig.sh
```

確認：表示された内容が承認した環境であることを確かめてから `yes` を入力します。エラーなく終了すれば kubeconfig が作られているはずです（未検証）。

目的：固定した chart の版と values で、AWS Load Balancer Controller を `helm upgrade --install` で導入します。AWS を操作するスクリプトなので、`yes` の入力を求められます。Controller は Ingress から ALB を作る仕組みで、ここでは ALB はまだ作られません。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/07-aws-integration/scripts/install-lbc.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/07-aws-integration/scripts/install-lbc.sh
```

確認：エラーなく終了するはずです（未検証）。導入後の状態は、次の `helm list` 以降で確認します。

目的：導入した release の一覧を確認します。

```text
helm list -n kube-system
```

確認：`aws-load-balancer-controller` の `STATUS` が `deployed` のはずです（未検証）。

目的：release の履歴（revision）を確認します。

```text
helm history aws-load-balancer-controller -n kube-system
```

確認：導入直後は revision 1 だけが表示されるはずです（未検証）。この後の `upgrade` と `rollback` で revision が増える様子と比べます。

目的：release に実際に使われている values を確認します。

```text
helm get values aws-load-balancer-controller -n kube-system
```

確認：`clusterName`、`region`、`vpcId` などが、`install-lbc` で渡した値になっているはずです（未検証）。

目的：release が実際にクラスターへ入れたマニフェストを確認します。

```text
helm get manifest aws-load-balancer-controller -n kube-system
```

確認：`helm template` の出力（「2. Helm chart の中身を読む」）と比べ、生成物が同じ構成であることを確かめます（未検証）。

目的：Controller の Deployment と Pod を確認します。

```text
kubectl -n kube-system get deployment,pods -l app.kubernetes.io/name=aws-load-balancer-controller
```

確認：Controller の Pod が `Ready` のはずです（未検証）。

目的：Pod Identity Agent（Controller に AWS の権限を渡す仕組み）が各ノードで動いているかを確認します。

```text
kubectl -n kube-system get daemonset eks-pod-identity-agent
```

確認：DaemonSet の `DESIRED` と `READY` がノード数と同じのはずです（未検証）。

目的：Controller が作った IngressClass を確認します。

```text
kubectl get ingressclass
```

確認：`alb` が表示されるはずです（未検証）。

目的：Controller のログを確認します。

```text
kubectl -n kube-system logs deployment/aws-load-balancer-controller --tail=20
```

確認：AWS の認可エラーが出ていないことを見ます（未検証）。認可エラーが出ている場合は、「失敗時に確認すること」を見ます。

目的：release の状態と rollback の単位を観察するため、Controller の replica 数を 1 に変えます（観察が終わったら rollback で戻します）。chart のリポジトリ `eks`（手順 2 で登録）が必要です。

```text
helm upgrade aws-load-balancer-controller eks/aws-load-balancer-controller --version 3.6.2 -n kube-system --reuse-values --set replicaCount=1
```

確認：`Release "aws-load-balancer-controller" has been upgraded.` のように表示されるはずです（未検証）。

目的：upgrade 後の履歴を確認します。

```text
helm history aws-load-balancer-controller -n kube-system
```

確認：revision が増えていることを見ます（未検証）。

目的：revision 1 に戻します。

```text
helm rollback aws-load-balancer-controller 1 -n kube-system
```

確認：`Rollback was a success!` のように表示されるはずです（未検証）。

目的：rollback 後の履歴を確認します。

```text
helm history aws-load-balancer-controller -n kube-system
```

確認：rollback も新しい revision になることを確認します（未検証）。rollback の対象が何か（Kubernetes のリソースか、Helm が管理する release の状態か、AWS 側のリソースは含まれるか）を書き出します。

### 5. イメージ、Secret、アプリを用意する

目的：API/Web のイメージをビルドして ECR に push します。AWS を操作するスクリプトなので、対象のアカウント・region が表示され、`yes` の入力を求められます。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/07-aws-integration/scripts/push-images.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/07-aws-integration/scripts/push-images.sh
```

確認：表示された内容を確かめてから `yes` を入力します。エラーなく終了し、ECR に `phase7` タグのイメージができるはずです（未検証）。

目的：Secrets Manager から RDS のパスワードを取り出し、Git 管理外の `secrets/db.env` に書き出します（値は表示しません）。AWS を操作するスクリプトなので、`yes` の入力を求められます。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/07-aws-integration/scripts/write-db-secret.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/07-aws-integration/scripts/write-db-secret.sh
```

確認：エラーなく終了し、`DB パスワードを書き出しました（値は表示しません）` のようなメッセージが出るはずです（未検証）。手順 1 で置いたダミーの `db.env` は、この実際の値で置き換わります。

目的：ALB に接続できる範囲（許可 CIDR）を、このシェルの環境変数に設定します。`198.51.100.7/32` はダミーなので、**自分のグローバル IP の /32** に置き換えます（`0.0.0.0/0` は `deploy` が拒否します）。

**Windows (PowerShell):**

```powershell
$env:WORKBOARD_ALLOWED_CIDR = '198.51.100.7/32'
```

**Linux / macOS / WSL (Bash):**

```bash
export WORKBOARD_ALLOWED_CIDR=198.51.100.7/32
```

確認：画面に出力は想定していません。エラーが出なければ設定済みです。ダミーの値のままにしないでください。

目的：**ALB が作られ、費用が発生します。** ECR のレジストリ、RDS のエンドポイント、許可 CIDR を実際の値に置き換えて EKS に適用し、migration Job の完了と API/Web の準備完了を待ちます。Ingress が適用されると Controller が ALB を作ります。開始条件を満たし、明示的に判断した後にだけ実行します。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/07-aws-integration/scripts/deploy.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/07-aws-integration/scripts/deploy.sh
```

確認：エラーなく終了するはずです（未検証）。ALB は検証が終わったらすぐに [aws-cleanup.md](aws-cleanup.md) の順序で削除します。恒常的な公開はしません。

目的：`workboard` namespace の Pod・Deployment・Service・Job・Ingress を確認します。

```text
kubectl -n workboard get pods,deploy,svc,job,ingress
```

確認：期待結果は、Postgres の Pod がなく、migration Job が `Completed`、API/Web が `Ready` で、Ingress が表示されていることです（未検証）。

目的：API が接続している DB の接続先と SSL モードを確認します。パスワードは表示しません。

```text
kubectl -n workboard exec deploy/workboard-api -- printenv POSTGRES_HOST PGSSLMODE
```

確認：`POSTGRES_HOST` が RDS のエンドポイント、`PGSSLMODE` が `require` のはずです（未検証）。

目的：migration Job のログを読み、RDS にスキーマが作られたことを確認します。

```text
kubectl -n workboard logs job/workboard-migrate -c migrate
```

確認：エラーなく終了したログが出るはずです（未検証）。パスワードの値は表示されません。

### 6. ALB と公開範囲を確認する

目的：Ingress の `ADDRESS`（ALB の DNS 名）を確認します。

```text
kubectl -n workboard get ingress
```

確認：`ADDRESS` に ALB の DNS 名が表示されるまで数分かかります。表示された DNS 名を、以降の `<ALB の DNS 名>` に使います（未検証）。

目的：Ingress の詳細とイベントを読みます。

```text
kubectl -n workboard describe ingress workboard
```

確認：`Events` に、ALB の作成成功が出ているはずです。エラーが出ている場合は「失敗時に確認すること」を見ます（未検証）。

目的：Controller のログで、ALB 作成の様子と認可エラーの有無を確認します。

```text
kubectl -n kube-system logs deployment/aws-load-balancer-controller --tail=20
```

確認：認可エラーが出ていないことを見ます（未検証）。

目的：許可した IP のネットワークから、ALB 経由で API の Readiness を確認します。`<ALB の DNS 名>` は上の `ADDRESS` に置き換えます。

**Windows (PowerShell):**

```powershell
curl.exe -i http://<ALB の DNS 名>/health/ready
```

**Linux / macOS / WSL (Bash):**

```bash
curl -i http://<ALB の DNS 名>/health/ready
```

確認：`HTTP/1.1 200` など成功のステータス行が表示されるはずです（未検証）。

目的：許可した IP のネットワークから、ALB 経由でタスクの一覧を読みます。

**Windows (PowerShell):**

```powershell
curl.exe -s http://<ALB の DNS 名>/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -s http://<ALB の DNS 名>/api/v1/tasks
```

確認：JSON が表示されるはずです（未検証）。ブラウザーで `http://<ALB の DNS 名>/` を開き、ダミータスクを作って再読み込みしても残ることを確認します。許可していない別のネットワーク（例: スマートフォンの回線）から同じ URL へ接続し、拒否される（接続できない、またはタイムアウト）ことを確認します。ALB のセキュリティグループに `inbound-cidrs` の CIDR だけが許可されていること、ターゲットグループが healthy であることを AWS のコンソールまたは CLI で確認します。検証が終わったら、すぐに [aws-cleanup.md](aws-cleanup.md) の順序で ALB を削除します。恒常的な公開はしません。

### 7. RDS を観察する

目的：RDS の状態を AWS CLI で読みます（読み取りだけで、何も変更しません）。

```text
aws rds describe-db-instances --db-instance-identifier workboard-learning-db --region ap-northeast-1 --query "DBInstances[0].[DBInstanceStatus,MultiAZ,StorageEncrypted,PubliclyAccessible,BackupRetentionPeriod,LatestRestorableTime]"
```

確認：`[DBInstanceStatus, MultiAZ, StorageEncrypted, PubliclyAccessible, BackupRetentionPeriod, LatestRestorableTime]` の順に 6 つの値が表示されるはずです（未検証）。private（`PubliclyAccessible` が false）、暗号化、バックアップ保持、最新の復元可能時刻（PITR の目安）を確認します。RDS のセキュリティグループが、クラスターのセキュリティグループからの 5432 だけを許可していることも確認します。パスワードの値は表示も記録もしません。

目的：Terraform の出力値（RDS のエンドポイントなど）を読みます。

```text
terraform -chdir=phases/07-aws-integration/terraform output
```

確認：`db_endpoint_address` や `db_master_secret_arn` などの出力が表示されるはずです（未検証）。パスワードの値そのものは出力に含まれません。

### 8. データ移行・バックアップ・復元の設計

[data-migration.md](data-migration.md) の手順に沿って、ローカルの DB（Phase 3 の kind のダミーデータ）を RDS に移す手順と、バックアップ・PITR・復元の設計を確認します。実機の移行・復元は、費用と影響を確認した場合だけ行います。

## 故障実験

**ダミーデータだけであることを確認でき、費用と影響を理解できた場合のみ実行してください。**

### A. RDS を再起動して、API の Readiness への影響を観察する

承認した AWS 環境で、この Phase の RDS だけを対象にします。再起動中は DB に接続できません（Single-AZ のため、数分間）。

目的：**RDS が再起動し、数分間 DB に接続できなくなります（Single-AZ のため）。** 承認した AWS 環境で、この Phase の RDS だけを対象にします。

```text
aws rds reboot-db-instance --db-instance-identifier workboard-learning-db --region ap-northeast-1
```

確認：再起動の開始を示す内容が表示されるはずです（未検証）。復旧までの時間は、次の `get pods -w` と、別のターミナルでの確認で記録します。

目的：API の Pod の状態の変化を見続けます。**別のターミナルで実行したままにします**（再起動の前から始めておくと変化を逃しません）。観察が終わったら `Ctrl+C` で止めます。

```text
kubectl -n workboard get pods -w
```

確認：API の Pod の Ready が変わる様子を観察します（未検証）。別のターミナルで、`kubectl -n workboard get endpoints workboard-api` と、ALB の URL への `curl`（`/`、`/health/ready`、`/api/v1/tasks`）を繰り返し、API の Pod の Ready、Service のエンドポイント、ALB の応答がどう変わるか、復旧までの時間を記録します。ALB の health check が `/`（Web 自身）である理由を、この結果から説明します。

### B. Pod Identity の association を外して、Controller の権限を観察する

association を AWS CLI または Terraform で外すと、Controller が AWS API を呼べなくなります。既存の ALB は残りますが、新しい Ingress の変更は反映されません。ログの認可エラーを観察し、元に戻します（`terraform apply` で association を再作成）。最小権限と、権限の欠落時の症状を整理します。

### C. 許可 CIDR を変えて、自分が拒否されることを観察する

Ingress の `inbound-cidrs` を別の値に変えて `apply` し、ALB に接続できなくなること、ALB のセキュリティグループが更新されることを確認します。`WORKBOARD_ALLOWED_CIDR` を元の値に戻して `deploy` します。

### D. Ingress を削除して、ALB が消えることを確認する

目的：**ALB が削除されます。** Ingress を削除して、Controller が ALB を片付けるかを観察します。実行前に、削除する Ingress が `workboard` namespace のものであることを確かめます。

```text
kubectl -n workboard delete ingress workboard
```

確認：`ingress.networking.k8s.io "workboard" deleted` と表示されるはずです（未検証）。Ingress を再作成すれば ALB は再び作られ、その分の費用がかかります。

目的：リージョン内の ALB を一覧して、削除した Ingress の ALB が消えたかを確認します（読み取りだけです）。

```text
aws elbv2 describe-load-balancers --region ap-northeast-1
```

確認：しばらく待つと、この Phase の ALB が一覧から消えているはずです（未検証）。Controller が動いている間に Ingress を消すと ALB も消えること、Controller を先に消すと ALB が残ることを、削除の順序の根拠として整理します（Controller を先に消す実験は、残存資産と課金が発生するため行いません）。

## 発展課題（任意。アプリは実装しない）

アプリのコードは変更せず、設計と観点だけを記録します。

- **S3 への CSV エクスポート:** 専用の ServiceAccount と Pod Identity のロール（特定のバケット・プレフィックスへの `PutObject` のみ）をどう設計するか。LBC のロールとどこが違うか。バケットの公開ブロック、暗号化、ライフサイクル、削除時の残存資産は何か。
- **Redis + Worker:** CSV 生成のような非同期処理を、Job（一回きり）と Deployment（常駐）のどちらで動かすか。Redis はクラスター内か ElastiCache か。失敗時の再実行と冪等性をどう保証するか。

## 失敗時に確認すること

- `terraform plan` が cluster を見つけられない: `cluster_name` と region。`aws eks describe-cluster` が同じアカウントで成功するか。
- `plan` で subnet が空: private subnet に `kubernetes.io/role/internal-elb=1` のタグがあるか。
- RDS に接続できない: RDS のセキュリティグループがクラスターのセキュリティグループ（ノードが使うもの）を許可しているか。ノードが別のセキュリティグループを使っていないか。
- `no pg_hba.conf entry ... SSL off`: `PGSSLMODE=require` が ConfigMap に入っているか（`kubectl kustomize` で確認）。
- `password authentication failed`: Secrets Manager のパスワードがローテーションされた可能性。`write-db-secret` と `deploy` を再実行し、Pod を作り直す。
- Controller が起動しない / Webhook のエラーで Service や Ingress を作成できない: `kubectl -n kube-system logs` と `describe pod`。Pod Identity の association の namespace と ServiceAccount 名、Pod Identity Agent が動いているか。
- Ingress に ADDRESS が付かない: Controller のログの認可エラー（IAM ポリシー、association）。subnet のタグ。
- ALB の疎通ができない: `WORKBOARD_ALLOWED_CIDR` が現在のグローバル IP か。ターゲットグループが healthy か。ALB の SG とノードの SG の規則。
- `ImagePullBackOff`: ECR に `phase7` タグのイメージがあるか。
- `helm` が接続できない: `. env.ps1`（Bash は `source env.sh`）を読み込んだか。kubeconfig の context。

## Linux / macOS / WSL での前提

スクリプトは PowerShell 版と同じ処理の Bash 版（`phases/07-aws-integration/scripts/` の `env.sh`・`update-kubeconfig.sh`・`push-images.sh`・`install-lbc.sh`・`write-db-secret.sh`・`deploy.sh`）があり、上の手順の「Linux / macOS / WSL (Bash)」に従います。Bash 4 以降、Docker、AWS CLI v2、Terraform 1.17.x、kubectl 1.34〜1.36、Helm 4.x、`python3` を使います。macOS 標準の bash 3.2 は対象外です（[ADR-0008](../../docs/adr/0008-linux-support.md)）。

## 後片付け・再構築

**ALB・RDS・NAT・EKS は、削除するまで課金が続きます。** 学習を終えたら、必ず [aws-cleanup.md](aws-cleanup.md) の順序（Ingress → アプリ → Helm → RDS の判断と Terraform の削除 → Phase 6 の削除）で削除します。削除は元に戻せません。対象のアカウント・region・クラスター名と、消えるデータ（RDS のダミーデータ、最終スナップショットの有無）を確認し、削除してよいと明示的に判断した場合だけ `terraform destroy` を実行します。削除後は、残り得る資産の点検リストで確認し、翌日以降に請求を確認します。`db.env` とダンプファイルも削除します。

## 完了条件

- [ ] 開始条件（承認、見積もり、予算通知、クリーンアップ手順のレビュー）を満たしてから AWS を操作した（または、AWS を操作せず、ステップ 1・2 だけ実施した理由を記録した）。
- [ ] `helm template` の生成物を読み、ServiceAccount、RBAC、Deployment、Webhook、CRD の内容と、確認した点を書き出した。
- [ ] `terraform plan` の差分を読み、作成されるリソースと料金要因を一覧にした。
- [ ] Controller を導入し、`helm list` / `helm history` / `helm rollback` で release の状態を観察した。
- [ ] RDS に切り替え、private・TLS・セキュリティグループ・Secret の扱いを確認した。
- [ ] 許可 IP から ALB に疎通し、許可外から拒否されることを確認した。
- [ ] 故障実験の実施・省略を記録した。
- [ ] ALB → RDS → Terraform の順で削除し、残り得る資産を点検した。
- [ ] 設計課題に答えた**後で** [ADR-0013（提案）](decisions/0013-rds-connection-and-secret.md)、[ADR-0014（提案）](decisions/0014-aws-load-balancer-controller-and-exposure.md) を読み、自分の回答と比べた。納得できたら Status を「採用」に変更し、異なる判断をした点は理由を学習ポータルの学習メモに残した。

## 学習メモ

観察結果と設計課題への回答は、この README ではなく**学習ポータルに入力します**（各自の PC の Git 管理外 `learning-portal/.data` にだけ保存され、リポジトリには残りません）。実行していない実験は「省略」と理由を書きます。記録する項目は次のとおりです。

- 実行日・OS・シェル
- Terraform / AWS provider / Helm / kubectl のバージョン、Controller の chart と app のバージョン
- 見積もり金額（Phase 6 との合計）と承認した上限、予算通知の設定
- `helm template` で確認した生成物（種類・RBAC・Webhook・Secret・CRD）と気づいた点
- `terraform plan` の差分（作成されるリソース、料金が発生するもの）
- RDS の構成（subnet、セキュリティグループ、暗号化、バックアップ、TLS）
- パスワードの管理方法とローテーション時の影響
- `helm list` / `history` / `rollback` の結果
- Pod Identity の association と IAM ポリシーの評価（最小権限として十分か）
- ALB の公開範囲（許可 IP と拒否の確認）
- データ移行・バックアップ・復元の設計
- 故障実験 A〜D の結果
- 実際にかかった費用（請求の確認後）
- 削除後に残っていた資産・点検の結果
- 疑問・未解決事項

## 実装時の検証記録

2026-11-10、Windows PowerShell 5.1、Git Bash、kubectl v1.34.1（Kustomize v5.7.1）、Terraform 1.17.1、Helm 4.3.1、実装担当が**静的な検証だけ**を行いました。**AWS では何も実施していません。** `terraform plan` / `apply` / `destroy`、AWS CLI、`helm install`（クラスターへの導入）、イメージの push、EKS への適用、`aws sts` を含む AWS API 呼び出しは未実施です。学習者自身の記録は README ではなく学習ポータルに残します。

| 確認・コマンド | 結果 |
| --- | --- |
| `terraform fmt -check -recursive` | エラーなし |
| `terraform init -backend=false` と `terraform validate` | 成功（AWS provider 6.72.0。`.terraform.lock.hcl` を残し、`.terraform/` は削除） |
| `helm repo add eks`、`helm search repo`、`helm show values`、`helm template`（chart 3.6.2、固定した values） | 成功（クラスターに接続せず）。ServiceAccount、ClusterRole/Role と Binding、Deployment（replicas 2）、Service、Secret、Mutating/ValidatingWebhookConfiguration、CRD 7 つなどを確認 |
| `kubectl kustomize phases/07-aws-integration/kustomize/overlays/eks`（ダミーの `db.env`） | 成功。Postgres なし、`POSTGRES_HOST` と `PGSSLMODE=require`、Ingress `alb` と `inbound-cidrs` を確認。確認後ダミーの `db.env` は削除 |
| IAM ポリシー JSON | LBC v3.6.2 のタグから取得し、JSON として読み込めることを確認（SHA-256 は ADR-0014） |
| PowerShell 構文解析、`bash -n` | 全スクリプトでエラーなし。`.ps1` は UTF-8 BOM、`.sh` は LF・BOM なし |

未検証: すべての AWS 側の動作（RDS 作成と接続、TLS の `require` で API が接続できること、Pod Identity の動作、Controller の起動と chart 既定の feature gate、ALB の作成と `inbound-cidrs`、ローテーション時の挙動、データ移行・復元の手順、故障実験）、料金の「要確認」項目、Linux ネイティブでのスクリプト実行。
