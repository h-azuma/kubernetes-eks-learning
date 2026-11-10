# Lab 06: Amazon EKS 基盤構築

## 学習目標

- VPC、subnet、ルートテーブル、NAT Gateway が、EKS のノードの通信（ECR、API サーバー）にどう関わるかを説明する。
- 標準 EKS と Managed Node Group で、AWS が管理する部分と利用者が管理する部分を、実際のノード・設定から説明する。
- IAM（cluster role、node role）と access entries が、AWS の権限と Kubernetes の権限をどう分けるかを説明する。
- ECR にイメージを置き、EKS 上で WorkBoard の Web/API を動かす。
- `terraform plan` の差分、料金要因、削除後に残り得る資産を読み、記録する。

## 前提条件

**この Lab は AWS の有料リソースを作ります。** 次の開始条件をすべて満たしてから、AWS を操作する手順に進みます。

1. **ユーザー（学習者本人）による AWS 利用の明示承認。** `terraform apply` と AWS を変更する操作は、承認した後に自分の手で実行します。この教材の作成者（AI を含む）は AWS を操作しません。
2. **見積もり金額の確認。** [cost-estimate.md](cost-estimate.md) の「要確認」の値を公式の料金ページで埋め、合計を確認します。
3. **予算通知の設定。** AWS Budgets 等で通知を設定します。**予算通知は課金の停止を保証しません。**
4. **クリーンアップ手順のレビュー。** [aws-cleanup.md](aws-cleanup.md) を読み、削除する日時を決めます。

ツールは Terraform 1.17.x、AWS CLI v2、kubectl 1.34〜1.36、Docker（Linux コンテナエンジン）、Git です。Terraform と AWS provider の版は `terraform/versions.tf` に固定してあります。AWS の認証情報は、環境変数や `~/.aws` のプロファイルなど、Git 管理外に置きます。実際のアカウント ID や認証情報、`terraform.tfvars`、`terraform.tfstate` を Git に入れないでください（`.gitignore` の対象です）。

先の Phase を前提にしませんが、Kubernetes の基本（Pod・Deployment・Service・Job・Kustomize）は Phase 3 までで学んだものとします。この Phase の資材は `phases/06-eks-foundation/` だけで完結します。Web/API の定義は Phase 3 と重複しています（[ADR-0007](../../docs/adr/0007-phase-directory-layout.md) の意図的な重複）。kind は使いません。

## 設計課題（実装前に考える）

1. EKS でも OS・ノードの運用責任は利用者に残るか？ 残るなら何が、誰の責任として残るか？
2. Managed Node Group と EKS Auto Mode では、管理の境界がどう違うか？ 何が見えなくなり、何が増えるか？
3. region はどこにするか？ 何を基準に選ぶか（料金、遅延、AZ 数、サービスの有無）？
4. EKS の API endpoint を公開するか、制限するか？ 制限するなら何で、どの経路で `kubectl` と Terraform を使うか？
5. NAT Gateway を 1 つにするか、AZ ごとに置くか？ 費用と障害時の影響はどう変わるか？
6. VPC を public/private の 2 AZ に分ける理由は何か？ ノードを public subnet に置く案と比べて何が違うか？
7. Terraform の state をどこに置くか？ 失うと何が起きるか？

## 実装タスク

1. [構成図](architecture.md)、[ADR-0007](../../docs/adr/0007-phase-directory-layout.md) を読む。
2. `terraform/` を読み、各ファイルのリソースがどの AWS の部品に対応するか、依存の順序（`depends_on` と参照）を書き出す。
3. 開始条件（前提条件の 1〜4）を満たす。
4. （承認後）`terraform.tfvars` を作り、`terraform plan` の差分を読んで記録してから、`terraform apply` する。
5. 接続用の kubeconfig を作り、ノード・アドオン・OS を観察する。
6. イメージを ECR に push し、`eks` overlay を適用して、`port-forward` で動作を確認する。
7. 故障実験を行い、費用を確認し、削除する。結果を **学習ポータルの学習メモ**（項目は「学習メモ」節）に記録する。

## 検証コマンド・期待結果

すべてリポジトリ直下で実行します。ステップ 1 は AWS に接続せず、いつでも実行できます。ステップ 2 以降は AWS を操作するため、開始条件を満たしてから実行します。AWS CLI を使う前に、操作対象のアカウントと region を確認します（各スクリプトは表示して `yes` の入力を求めます）。

### 1. 適用前に読む（AWS に接続しない）

```text
terraform -chdir=phases/06-eks-foundation/terraform fmt -check -recursive
terraform -chdir=phases/06-eks-foundation/terraform init -backend=false
terraform -chdir=phases/06-eks-foundation/terraform validate
kubectl kustomize phases/06-eks-foundation/kustomize/base
```

Kustomize の `eks` overlay は、Secret の入力ファイル `secrets/db.env` が必要です。ダミーを作って生成結果を読みます（この例ファイルは Git に入れません）。

**Windows (PowerShell):**

```powershell
Copy-Item phases/06-eks-foundation/kustomize/overlays/eks/secrets/db.env.example phases/06-eks-foundation/kustomize/overlays/eks/secrets/db.env
```

**Linux / macOS / WSL (Bash):**

```bash
cp phases/06-eks-foundation/kustomize/overlays/eks/secrets/db.env.example phases/06-eks-foundation/kustomize/overlays/eks/secrets/db.env
```

```text
kubectl kustomize phases/06-eks-foundation/kustomize/overlays/eks
```

観察する点は以下です。

- `terraform init -backend=false` は provider を取得するだけで、AWS には接続しません。`validate` は文法と引数の整合を確認するもので、AWS 側で作成できるかは確認しません。
- `terraform/` の変数に、`public_access_cidrs` の validation（`0.0.0.0/0` の拒否）があること。
- `overlay` の出力で、イメージが `111122223333.dkr.ecr...`（ダミーのアカウント ID）になっていること。実際のアカウント ID は `scripts/deploy` が適用時にだけ差し替えます。
- DB が `emptyDir` の Deployment であること（[ADR-0012](decisions/0012-kustomize-eks-and-throwaway-db.md) は課題の後で読む）。

### 2. （承認後）`terraform plan` の差分を読む

`terraform.tfvars.example` をコピーして `terraform.tfvars` を作り、自分の値に置き換えます。`allowed_account_id`、`admin_principal_arn`、`public_access_cidrs`（自分のグローバル IP の /32）が必須です。`terraform.tfvars` は Git に入れません。

**Windows (PowerShell):**

```powershell
Copy-Item phases/06-eks-foundation/terraform/terraform.tfvars.example phases/06-eks-foundation/terraform/terraform.tfvars
```

**Linux / macOS / WSL (Bash):**

```bash
cp phases/06-eks-foundation/terraform/terraform.tfvars.example phases/06-eks-foundation/terraform/terraform.tfvars
```

```text
terraform -chdir=phases/06-eks-foundation/terraform plan
```

作成されるリソースの種類と数、料金が発生するもの（EKS クラスター、EC2、NAT Gateway、EIP）を一覧にして記録します。`plan` は何も作成しません。内容を理解し、費用に同意してから、次の `apply` に進みます。**`apply` は承認した後にだけ実行します。**

```text
terraform -chdir=phases/06-eks-foundation/terraform apply
```

クラスターの作成には十数分かかります。完了後、`terraform output` で VPC ID や ECR の URL を確認します。

### 3. kubeconfig を作り、クラスターを観察する

新しいターミナルごとに最初の行を実行します。`env.ps1`（Bash は `env.sh`。`source` で読み込みます）は、このシェルだけで EKS 用の kubeconfig（`.kube/workboard-eks.yaml`）と region を使う設定です。

**Windows (PowerShell):**

```powershell
. .\phases\06-eks-foundation\scripts\env.ps1
powershell -NoProfile -File phases/06-eks-foundation/scripts/update-kubeconfig.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
source phases/06-eks-foundation/scripts/env.sh
bash phases/06-eks-foundation/scripts/update-kubeconfig.sh
```

```text
kubectl get nodes -o wide
kubectl get pods -n kube-system -o wide
kubectl auth can-i '*' '*'
kubectl get nodes -o jsonpath='{.items[*].status.nodeInfo.osImage}'
kubectl describe node
```

観察する点は、Node が 2 台（AZ が別）で Ready であること、OS イメージとカーネルの版、kubelet の版がコントロールプレーンの版に合っていること、`kube-system` に coredns・kube-proxy・aws-node（vpc-cni）があること、`can-i` が yes（access entry が効いている）であることです。ノードの OS を更新するのは誰か、EKS が自動で更新するもの・しないものを `describe node` の情報と合わせて書き出します。

### 4. イメージを ECR に置き、アプリを適用する

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/06-eks-foundation/scripts/push-images.ps1
powershell -NoProfile -File phases/06-eks-foundation/scripts/deploy.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/06-eks-foundation/scripts/push-images.sh
bash phases/06-eks-foundation/scripts/deploy.sh
```

`push-images` は ECR にログインし、API/Web を `linux/amd64` でビルドして `phase6` タグで push します。`deploy` は `db.env` が無ければランダムな値で作成し（値は表示しません）、overlay のダミーのレジストリを実アカウントの ECR に置き換えて適用し、DB・migration Job・API・Web の準備完了を待ちます。

```text
kubectl -n workboard get pods,deploy,svc,job -o wide
kubectl -n workboard describe pod -l app=workboard-api
```

期待結果は、Pod が 2 つのノードのどちらかに配置され、migration Job が Completed、API/Web/DB が Ready であることです。イメージの取得元（ECR）とイベントを `describe pod` で確認します。`ImagePullBackOff` になる場合は、「失敗時に確認すること」を見ます。

### 5. ブラウザーと curl で確認する

8086 番が使われていないことを確認し、次のコマンドを実行中のまま残します。

```text
kubectl -n workboard port-forward --address 127.0.0.1 svc/workboard-web 8086:80
```

[http://localhost:8086](http://localhost:8086) でダミータスクを作ります。別のターミナルで次の確認もできます。

**Windows (PowerShell):**

```powershell
curl.exe -i http://localhost:8086/health/ready
curl.exe -s http://localhost:8086/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -i http://localhost:8086/health/ready
curl -s http://localhost:8086/api/v1/tasks
```

この入口はローカルの PC だけが使えます。インターネットには公開されていません（ALB は Phase 7）。

### 6. ネットワークと権限を観察する

```text
terraform -chdir=phases/06-eks-foundation/terraform output
kubectl get nodes -L topology.kubernetes.io/zone,node.kubernetes.io/instance-type,eks.amazonaws.com/nodegroup
```

どのノードがどの AZ にいるか、private subnet のノードが NAT 経由でイメージを取得していること、NAT の EIP（`nat_public_ips`）がノードの外向き通信の送信元であることを、構成図と対応づけます。API endpoint の許可 CIDR 外のネットワークから `kubectl get nodes` を試せる場合は、拒否されること（接続できない、またはタイムアウト）を確認します（任意）。

## 故障実験

**ダミーのデータだけが入っていることを確認できた場合に実行してください。** 対象はこの Phase のクラスターだけです。

### A. ノードを 1 台、計画的に外す（drain）

```text
kubectl get pods -n workboard -o wide
kubectl drain <ノード名> --ignore-daemonsets --delete-emptydir-data
kubectl get pods -n workboard -o wide
kubectl uncordon <ノード名>
```

Pod が別のノードに再配置されること、Pod が 1 台に集まり得ること、DB（emptyDir）がノードを移るとデータが消えることを観察します。`--delete-emptydir-data` の意味を調べます。

### B. DB Pod を削除する（emptyDir のデータは消える）

```text
kubectl -n workboard delete pod -l app=workboard-postgres
kubectl -n workboard rollout status deployment/workboard-postgres --timeout=180s
```

**Windows (PowerShell):**

```powershell
curl.exe -s http://localhost:8086/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -s http://localhost:8086/api/v1/tasks
```

タスクが消え（または API が一時的に失敗し）、migration Job を再実行しないとスキーマが戻らないことを観察します（`deploy` スクリプトの再実行で復旧）。Phase 3 の PVC との違いを書き出します。

### C. （任意、費用・影響を確認した場合のみ）ノードの EC2 を 1 台停止する

承認した AWS 環境で、自分のクラスターのノードだけを対象にします。対象のインスタンス ID を、タグで絞って確認してから停止します。

```text
aws ec2 describe-instances --filters "Name=tag:eks:cluster-name,Values=workboard-learning" "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].InstanceId" --output text --region ap-northeast-1
aws ec2 terminate-instances --instance-ids <確認したインスタンス ID> --region ap-northeast-1
kubectl get nodes -w
```

Auto Scaling グループが新しいノードを作ること、`kubectl get nodes` で NotReady → 新しい Node が参加するまでの時間、Pod の再スケジュールを観察します。

## 失敗時に確認すること

- `terraform validate` / `plan` で変数のエラー: `terraform.tfvars` の必須値（`allowed_account_id`、`admin_principal_arn`、`public_access_cidrs`）。`0.0.0.0/0` は拒否される。
- `plan` / `apply` が別のアカウントで失敗: `allowed_account_id` と現在の認証情報のアカウント。
- `kubectl` がタイムアウトする: 自分の現在のグローバル IP が `public_access_cidrs` に含まれているか。IP が変わった場合は `terraform apply` で更新する。
- `kubectl` が `Unauthorized` / `forbidden`: `admin_principal_arn` が、実際に使っている IAM ユーザー/ロールの ARN か（assumed-role のセッション ARN ではなくロールの ARN）。`aws sts get-caller-identity` を確認する。
- ノードが NotReady / クラスターに参加しない: node role のポリシー、private subnet の NAT へのルート、`kubectl get nodes` のイベント。
- `ImagePullBackOff`: ECR に `phase6` タグのイメージがあるか、`describe pod` のイベント、アカウント ID・region の置き換えが正しいか。ノードの ECR への経路（NAT）が有効か。
- `deploy` の context エラー: `update-kubeconfig` を実行したか。context が `arn:aws:eks:<region>:<account>:cluster/<name>` であるか。
- 8086 が使えない: 他のプロセスが使用中でないか確認し、解放できる場合だけ解放する。

## Linux / macOS / WSL での前提

スクリプトは PowerShell 版と同じ処理の Bash 版（`phases/06-eks-foundation/scripts/` の `env.sh`・`update-kubeconfig.sh`・`push-images.sh`・`deploy.sh`）があり、上の手順の「Linux / macOS / WSL (Bash)」に従います。Bash 4 以降、Docker、AWS CLI v2、Terraform 1.17.x、kubectl 1.34〜1.36 を使います。`--platform linux/amd64` を指定するため、Apple Silicon や ARM の Linux でもビルドできます（エミュレーションで遅くなる場合があります）。macOS 標準の bash 3.2 は対象外です（[ADR-0008](../../docs/adr/0008-linux-support.md)）。

## 後片付け・再構築

port-forward を実行しているターミナルで `Ctrl+C` を押すと入口だけが閉じます。クラスターとアプリは動き続け、**課金も続きます。** 学習を終えたら、必ず [aws-cleanup.md](aws-cleanup.md) の手順で削除します。削除は元に戻せません。対象のアカウント・region・クラスター名と、消えるデータ（Phase 6 はダミーのみ）を確認し、削除してよいと明示的に判断した場合だけ `terraform destroy` を実行します。削除後は、残り得る資産の点検リストで確認し、翌日以降に請求を確認します。再構築は、`terraform apply` からやり直します（ECR のイメージも作り直しになります）。

## 完了条件

- [ ] 開始条件（承認、見積もり、予算通知、クリーンアップ手順のレビュー）を満たしてから AWS を操作した（または、AWS を操作せず、ステップ 1 だけ実施した理由を記録した）。
- [ ] `terraform plan` の差分を読み、作成されるリソースと料金要因を一覧にした。
- [ ] ノード・アドオン・OS イメージを観察し、AWS が管理する部分と利用者が管理する部分を整理した。
- [ ] ECR にイメージを置き、EKS で WorkBoard が動くことを `port-forward` で確認した。
- [ ] 故障実験の実施・省略を記録した。
- [ ] クラスターを削除し、残り得る資産を点検した。
- [ ] 設計課題に答えた**後で** [ADR-0011（提案）](decisions/0011-eks-foundation.md)、[ADR-0012（提案）](decisions/0012-kustomize-eks-and-throwaway-db.md) を読み、自分の回答と比べた。納得できたら Status を「採用」に変更し、異なる判断をした点は理由を学習ポータルの学習メモに残した。

## 学習メモ

観察結果と設計課題への回答は、この README ではなく**学習ポータルに入力します**（各自の PC の Git 管理外 `learning-portal/.data` にだけ保存され、リポジトリには残りません）。実行していない実験は「省略」と理由を書きます。記録する項目は次のとおりです。

- 実行日・OS・シェル
- Terraform / AWS provider / kubectl / Kubernetes のバージョン
- 見積もり金額と承認した上限、予算通知の設定
- `terraform plan` の差分（作成されるリソースの種類と数、料金が発生するもの）
- 選んだ region・endpoint の制限・NAT の構成と理由
- ノードの AZ・OS イメージ・kubelet の版、アドオンの版
- AWS が管理する部分と利用者が管理する部分
- ECR へ push したイメージ、Pod の配置
- 故障実験 A〜C の結果
- 実際にかかった費用（請求の確認後）
- 削除後に残っていた資産・点検の結果
- 疑問・未解決事項

## 実装時の検証記録

2026-11-10、Windows PowerShell 5.1、Git Bash、kubectl v1.34.1（Kustomize v5.7.1）、Terraform 1.17.1、実装担当が**静的な検証だけ**を行いました。**AWS では何も実施していません。** `terraform plan` / `apply` / `destroy`、AWS CLI、イメージの push、EKS への適用、`aws sts` を含む AWS API 呼び出しは未実施です。学習者自身の記録は README ではなく学習ポータルに残します。

| 確認・コマンド | 結果 |
| --- | --- |
| `terraform fmt -check -recursive` | エラーなし |
| `terraform init -backend=false` と `terraform validate` | 成功（AWS provider 6.72.0。`.terraform.lock.hcl` は 5 プラットフォーム分のハッシュを含めて残し、`.terraform/` は削除） |
| `kubectl kustomize` の `base` と `overlays/eks`（ダミーの `db.env`） | 成功。ダミーの ECR イメージ参照、ハッシュ付き ConfigMap/Secret、emptyDir の Postgres Deployment を確認。確認後ダミーの `db.env` は削除 |
| PowerShell 構文解析、`bash -n` | 全スクリプトでエラーなし。`.ps1` は UTF-8 BOM、`.sh` は LF・BOM なし |
| `env.ps1` / `env.sh` の読み込み | `AWS_REGION`、`KUBECONFIG` が設定される（AWS 接続なし） |

未検証: すべての AWS 側の動作（クラスター作成、アクセス制限、ノード参加、ECR、NAT 経由の pull、`deploy` のレジストリ置換の実機動作、故障実験）、料金の「要確認」項目、アドオンの実際の版、Linux ネイティブでのスクリプト実行。
