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

目的：Terraform ファイルの書式が整っているかを確認します（AWS には接続しません）。

```text
terraform -chdir=phases/06-eks-foundation/terraform fmt -check -recursive
```

確認：出力が何もなければ書式は整っています。整っていないファイルがあると、そのファイル名が表示されます。

目的：provider を取得して、次の `validate` を実行できる状態にします。`-backend=false` を付けているので、state の保存先には接続しません。

```text
terraform -chdir=phases/06-eks-foundation/terraform init -backend=false
```

確認：`Terraform has been successfully initialized!` が表示されれば成功です。`init -backend=false` は provider を取得するだけで、AWS には接続しません。

目的：Terraform の文法と引数の整合を確認します。

```text
terraform -chdir=phases/06-eks-foundation/terraform validate
```

確認：`Success! The configuration is valid.` が表示されれば成功です。`validate` は AWS 側で作成できるかは確認しません。あわせて `terraform/` の変数ファイルを開き、`public_access_cidrs` に validation（`0.0.0.0/0` の拒否）があることを読んで確認します。

目的：環境に依存しない共通部分（`base`）の生成結果を、適用前に読みます。

```text
kubectl kustomize phases/06-eks-foundation/kustomize/base
```

確認：エラーなく YAML が出力されれば成功です。この出力を、あとの `overlays/eks` の出力と比べます。

目的：`eks` overlay は Secret の入力ファイル `secrets/db.env` が必要です。ダミー値だけの例ファイルからコピーして、生成結果を読めるようにします（この例ファイルは Git に入れません）。

**Windows (PowerShell):**

```powershell
Copy-Item phases/06-eks-foundation/kustomize/overlays/eks/secrets/db.env.example phases/06-eks-foundation/kustomize/overlays/eks/secrets/db.env
```

**Linux / macOS / WSL (Bash):**

```bash
cp phases/06-eks-foundation/kustomize/overlays/eks/secrets/db.env.example phases/06-eks-foundation/kustomize/overlays/eks/secrets/db.env
```

確認：エラーが出なければ `db.env` が作られています。`deploy` は `db.env` が無いときだけランダムな値で作成するため、このダミーを残したまま `deploy` するとダミー値が DB のパスワードになります。ダミーのまま使いたくない場合は、生成結果を読み終えたあとで `db.env` を削除してから `deploy` します。

目的：`eks` overlay を生成して、`base` に差分が重なった適用前の最終形を読みます。

```text
kubectl kustomize phases/06-eks-foundation/kustomize/overlays/eks
```

確認：次の 2 点を見ます。(1) イメージが `111122223333.dkr.ecr...`（ダミーのアカウント ID）になっていること。実際のアカウント ID は `scripts/deploy` が適用時にだけ差し替えます。(2) DB が `emptyDir` の Deployment であること（[ADR-0012](decisions/0012-kustomize-eks-and-throwaway-db.md) は課題の後で読みます）。

### 2. （承認後）`terraform plan` の差分を読む

`terraform.tfvars.example` をコピーして `terraform.tfvars` を作り、自分の値に置き換えます。`allowed_account_id`、`admin_principal_arn`、`public_access_cidrs`（自分のグローバル IP の /32）が必須です。`terraform.tfvars` は Git に入れません。

目的：`terraform.tfvars.example` をコピーして、自分の値を入れる `terraform.tfvars` を作ります（`terraform.tfvars` は Git に入れません）。

**Windows (PowerShell):**

```powershell
Copy-Item phases/06-eks-foundation/terraform/terraform.tfvars.example phases/06-eks-foundation/terraform/terraform.tfvars
```

**Linux / macOS / WSL (Bash):**

```bash
cp phases/06-eks-foundation/terraform/terraform.tfvars.example phases/06-eks-foundation/terraform/terraform.tfvars
```

確認：エラーが出なければ `terraform.tfvars` が作られています。エディターで `allowed_account_id`、`admin_principal_arn`、`public_access_cidrs`（自分のグローバル IP の /32）を自分の値に置き換えます。

目的：AWS に何が作られるか（差分）を読みます。AWS の認証情報が必要ですが、`plan` は何も作成しません。

```text
terraform -chdir=phases/06-eks-foundation/terraform plan
```

確認：出力の末尾に `Plan: N to add, 0 to change, 0 to destroy.` のような件数が表示されるはずです（未検証）。作成されるリソースの種類と数、料金が発生するもの（EKS クラスター、EC2、NAT Gateway、EIP）を一覧にして記録します。内容を理解し、費用に同意してから、次の `apply` に進みます。

目的：**費用が発生します。** `plan` で読んだ差分を AWS に実際に作成します。開始条件（承認、見積もり、予算通知、クリーンアップ手順のレビュー）を満たし、明示的に判断した後にだけ自分の手で実行します。

```text
terraform -chdir=phases/06-eks-foundation/terraform apply
```

確認：完了まで十数分かかります。成功すると `Apply complete! Resources: N added, 0 changed, 0 destroyed.` が表示されるはずです（未検証）。実行前に、`plan` の差分と見積もりの金額を記録し、削除する日時を決めておきます。作成した時点から課金が続くため、学習を終えたら必ず [aws-cleanup.md](aws-cleanup.md) の手順で削除します。完了後、`terraform output` で VPC ID や ECR の URL を確認します。

### 3. kubeconfig を作り、クラスターを観察する

新しいターミナルごとに最初の行を実行します。`env.ps1`（Bash は `env.sh`。`source` で読み込みます）は、このシェルだけで EKS 用の kubeconfig（`.kube/workboard-eks.yaml`）と region を使う設定です。

目的：このシェルだけで EKS 用の kubeconfig（`.kube/workboard-eks.yaml`）と region を使う設定にして、以降の `kubectl` と AWS CLI がこの Phase の設定を向くようにします。

**Windows (PowerShell):**

```powershell
. .\phases\06-eks-foundation\scripts\env.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
source phases/06-eks-foundation/scripts/env.sh
```

確認：画面に出力は想定していません。エラーが出なければ設定済みです。Bash で `source` を付けずに実行した場合は、`source` で読み込み直してください。

目的：EKS クラスターに接続するための kubeconfig を作ります。AWS を操作するスクリプトなので、対象のアカウント・region・クラスター名が表示され、`yes` の入力を求められます。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/06-eks-foundation/scripts/update-kubeconfig.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/06-eks-foundation/scripts/update-kubeconfig.sh
```

確認：表示された内容が承認した環境であることを確かめてから `yes` を入力します。エラーなく終了すれば kubeconfig が作られているはずです（未検証）。

目的：Node の一覧と、AZ・OS イメージ・カーネル・kubelet の版を確認します。

```text
kubectl get nodes -o wide
```

確認：Node が 2 台（AZ が別）で `STATUS` が `Ready` であることを見ます。`VERSION`（kubelet の版）がコントロールプレーンの版に合っていること、`OS-IMAGE` と `KERNEL-VERSION` の値も記録します（未検証）。

目的：`kube-system` の Pod を確認して、EKS が標準で動かすアドオンを把握します。

```text
kubectl get pods -n kube-system -o wide
```

確認：`coredns`・`kube-proxy`・`aws-node`（vpc-cni）の Pod があり、`STATUS` が `Running` のはずです（未検証）。`NODE` 列でどの Node に載っているかも見ます。

目的：今の認証で全リソースへ全操作ができるかを確認して、access entry が効いているかを確かめます。

```text
kubectl auth can-i '*' '*'
```

確認：`yes` と表示されれば、access entry が効いています（未検証）。

目的：全 Node の OS イメージ名だけを取り出します。

```text
kubectl get nodes -o jsonpath='{.items[*].status.nodeInfo.osImage}'
```

確認：Node の数だけ OS イメージ名が 1 行に並んで表示されるはずです（未検証）。`get nodes -o wide` の `OS-IMAGE` と一致することを確かめます。

目的：Node の詳細（OS・kubelet・容量・状態・載っている Pod・イベント）を読みます。

```text
kubectl describe node
```

確認：`System Info`、`Conditions`、`Non-terminated Pods`、`Events` を見ます。ノードの OS を更新するのは誰か、EKS が自動で更新するもの・しないものを、`describe node` の情報と合わせて書き出します。

### 4. イメージを ECR に置き、アプリを適用する

目的：ECR にログインし、API/Web を `linux/amd64` でビルドして `phase6` タグで ECR に push します。AWS を操作するスクリプトなので、対象のアカウント・region が表示され、`yes` の入力を求められます。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/06-eks-foundation/scripts/push-images.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/06-eks-foundation/scripts/push-images.sh
```

確認：表示された内容を確かめてから `yes` を入力します。エラーなく終了し、ECR に `phase6` タグのイメージができるはずです（未検証）。

目的：`eks` overlay のダミーのレジストリを実アカウントの ECR に置き換えて EKS に適用し、DB・migration Job・API・Web の準備完了を待ちます。`db.env` が無ければランダムな値で作成します（値は表示しません）。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/06-eks-foundation/scripts/deploy.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/06-eks-foundation/scripts/deploy.sh
```

確認：エラーなく終了し、最後に Pod・Deployment・Service の一覧が表示されるはずです（未検証）。待機が終わらない場合は、あとの `ImagePullBackOff` などの切り分け（「失敗時に確認すること」）を見ます。

目的：`workboard` namespace の Pod・Deployment・Service・Job を、配置先の Node つきで確認します。

```text
kubectl -n workboard get pods,deploy,svc,job -o wide
```

確認：期待結果は、Pod が 2 つのノードのどちらかに配置され、migration Job が `Completed`、API/Web/DB が Ready であることです（未検証）。

目的：API の Pod の詳細を読み、イメージの取得元とイベントを確認します。

```text
kubectl -n workboard describe pod -l app=workboard-api
```

確認：`Image` が ECR のもの（実アカウントの ECR）で、`Events` にエラーがないことを見ます（未検証）。`ImagePullBackOff` になる場合は、「失敗時に確認すること」を見ます。

### 5. ブラウザーと curl で確認する

目的：ローカルの 8086 番から Web に入る入口を作ります。先に 8086 番が使われていないことを確認します。**別のターミナルで実行したままにします。**

```text
kubectl -n workboard port-forward --address 127.0.0.1 svc/workboard-web 8086:80
```

確認：`Forwarding from 127.0.0.1:8086 -> 80` のように表示され、プロンプトに戻らなければ待ち受け中です（未検証）。[http://localhost:8086](http://localhost:8086) を開いてダミータスクを作ります。この入口はローカルの PC だけが使えます。インターネットには公開されていません（ALB は Phase 7）。止めるときは、そのターミナルで `Ctrl+C` を押します。

目的：API の Readiness を `curl` で確認します（port-forward とは別のターミナルで実行します）。

**Windows (PowerShell):**

```powershell
curl.exe -i http://localhost:8086/health/ready
```

**Linux / macOS / WSL (Bash):**

```bash
curl -i http://localhost:8086/health/ready
```

確認：`HTTP/1.1 200` など成功のステータス行が表示されるはずです（未検証）。接続できない場合は、port-forward が動いているかを確かめます。

目的：画面で作ったダミータスクを、API から JSON で読みます。

**Windows (PowerShell):**

```powershell
curl.exe -s http://localhost:8086/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -s http://localhost:8086/api/v1/tasks
```

確認：作成したダミータスクを含む JSON が表示されるはずです（未検証）。

### 6. ネットワークと権限を観察する

目的：Terraform が作った VPC・subnet・NAT・ECR などの出力値を読みます。

```text
terraform -chdir=phases/06-eks-foundation/terraform output
```

確認：`nat_public_ips` などの出力が表示されるはずです（未検証）。どのノードがどの AZ にいるか、private subnet のノードが NAT 経由でイメージを取得していること、NAT の EIP（`nat_public_ips`）がノードの外向き通信の送信元であることを、構成図と対応づけます。

目的：Node ごとの AZ・インスタンスタイプ・Node Group 名を列にして表示します。

```text
kubectl get nodes -L topology.kubernetes.io/zone,node.kubernetes.io/instance-type,eks.amazonaws.com/nodegroup
```

確認：`ZONE`、`INSTANCE-TYPE`、`NODEGROUP` 相当の列が追加され、Node が別の AZ に分かれているはずです（未検証）。API endpoint の許可 CIDR 外のネットワークから `kubectl get nodes` を試せる場合は、拒否されること（接続できない、またはタイムアウト）を確認します（任意）。

## 故障実験

**ダミーのデータだけが入っていることを確認できた場合に実行してください。** 対象はこの Phase のクラスターだけです。

### A. ノードを 1 台、計画的に外す（drain）

目的：drain 前の Pod の配置を記録します。

```text
kubectl get pods -n workboard -o wide
```

確認：各 Pod がどの Node に載っているか（`NODE` 列）を記録し、drain する Node の名前を決めます。

目的：Node を 1 台、計画的に外します（Pod を別の Node へ追い出し、新しい Pod をその Node に置かなくします）。`<ノード名>` は上の出力で決めた Node の名前に置き換えます。DB の `emptyDir` のデータは、この操作で消えます。

```text
kubectl drain <ノード名> --ignore-daemonsets --delete-emptydir-data
```

確認：DaemonSet 以外の Pod が退避（evict）されたと表示されるはずです（未検証）。`--delete-emptydir-data` の意味を調べて書き出します。

目的：drain 後の Pod の配置を確認します。

```text
kubectl get pods -n workboard -o wide
```

確認：Pod が別のノードに再配置されること、Pod が 1 台に集まり得ること、DB（`emptyDir`）がノードを移るとデータが消えることを観察します（未検証）。

目的：外した Node を、再び Pod を置ける状態に戻します。

```text
kubectl uncordon <ノード名>
```

確認：`node/<ノード名> uncordoned` と表示されるはずです（未検証）。`kubectl get nodes` で `SchedulingDisabled` が消えていることを確かめます。

### B. DB Pod を削除する（emptyDir のデータは消える）

目的：DB の Pod を削除して、`emptyDir` のデータが消えることを観察します。

```text
kubectl -n workboard delete pod -l app=workboard-postgres
```

確認：`pod "..." deleted` と表示されるはずです（未検証）。

目的：DB の Deployment が新しい Pod で Ready になるまで待ちます。

```text
kubectl -n workboard rollout status deployment/workboard-postgres --timeout=180s
```

確認：`successfully rolled out` と表示されて終了するはずです（未検証）。180 秒で終わらなければタイムアウトします。

目的：DB を作り直した後のタスクの残り方を API で確認します（port-forward が動いている必要があります）。

**Windows (PowerShell):**

```powershell
curl.exe -s http://localhost:8086/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -s http://localhost:8086/api/v1/tasks
```

確認：タスクが消え（または API が一時的に失敗し）、migration Job を再実行しないとスキーマが戻らないことを観察します（`deploy` スクリプトの再実行で復旧）。Phase 3 の PVC との違いを書き出します。

### C. （任意、費用・影響を確認した場合のみ）ノードの EC2 を 1 台終了（terminate）する

承認した AWS 環境で、自分のクラスターのノードだけを対象にします。対象のインスタンス ID を、タグで絞って確認してから終了します。終了したインスタンスは元に戻せず、Managed Node Group が代わりのノードを作るかを観察します。

目的：終了する対象の EC2 インスタンス ID を、クラスター名のタグで絞って確認します（読み取りだけで、何も変更しません）。

```text
aws ec2 describe-instances --filters "Name=tag:eks:cluster-name,Values=workboard-learning" "Name=instance-state-name,Values=running" --query "Reservations[].Instances[].InstanceId" --output text --region ap-northeast-1
```

確認：このクラスターの running のインスタンス ID だけが表示されるはずです（未検証）。次のコマンドに渡す ID は、必ずこの出力から選びます。

目的：確認したインスタンス 1 台を終了します。**コマンドは `terminate-instances`（終了＝削除）で、元に戻せません。** 費用と影響を確認し、実行すると判断した場合だけ、`<確認したインスタンス ID>` を上の出力の 1 台に置き換えて実行します。

```text
aws ec2 terminate-instances --instance-ids <確認したインスタンス ID> --region ap-northeast-1
```

確認：インスタンスが `shutting-down` になったと表示されるはずです（未検証）。対象が自分のクラスターの 1 台であることを、実行前に必ず確かめます。

目的：Node の状態の変化を見続けます。**別のターミナルで実行したままにします。** 観察が終わったら `Ctrl+C` で止めます。

```text
kubectl get nodes -w
```

確認：Auto Scaling グループが新しいノードを作ること、`kubectl get nodes` で NotReady → 新しい Node が参加するまでの時間、Pod の再スケジュールを観察します（未検証）。

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
