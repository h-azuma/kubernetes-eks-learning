# Phase 6: AWS 資産の削除と点検

**開始前に必ずレビューしてください。** 以下のコマンドは、AWS の利用を承認した後に学習者が自分で実行する例です。この教材の作成時には実行していません。削除は元に戻せません。対象のアカウント・region・クラスター名を確認してから実行します。

## 削除の順序

1. **Kubernetes のリソースを先に消す（Service type LoadBalancer / Ingress が作る ALB・NLB を残さないため）。** Phase 6 のアプリは入口に LoadBalancer を使わないが、念のため確認する。

   ```text
   kubectl get svc,ingress -A
   kubectl delete namespace workboard
   ```

2. **ECR のイメージを確認する。** `ecr_force_delete = false`（既定）のため、イメージが残っていると `terraform destroy` は ECR で失敗する。イメージを残す必要がなければ削除する。

   ```text
   aws ecr list-images --repository-name workboard-api --region ap-northeast-1
   aws ecr batch-delete-image --repository-name workboard-api --region ap-northeast-1 --image-ids imageTag=phase6
   aws ecr batch-delete-image --repository-name workboard-web --region ap-northeast-1 --image-ids imageTag=phase6
   ```

3. **`terraform plan -destroy` で削除対象を読む。** 想定外のリソース（学習用以外）が含まれないことを確認する。

   ```text
   terraform -chdir=phases/06-eks-foundation/terraform plan -destroy
   ```

4. **承認を確認して `terraform destroy`。** 削除されるのは、クラスター、ノード、NAT、EIP、VPC、ECR リポジトリ、IAM ロール。**Phase 7 の RDS・ALB・IAM が残っている場合は、先に Phase 7 の削除を終えること**（VPC の削除が失敗する）。

   ```text
   terraform -chdir=phases/06-eks-foundation/terraform destroy
   ```

## 残り得る資産の点検リスト

削除後、`Project=workboard-learning` のタグ、またはクラスター名で探す。

| 資産 | なぜ残るか | 確認コマンド例 |
| --- | --- | --- |
| ALB / NLB / ターゲットグループ | Ingress や Service を先に消さずにクラスターを消した | `aws elbv2 describe-load-balancers --region ap-northeast-1` |
| ENI | ロードバランサーや EKS が作ったものが残り、subnet/VPC の削除を阻む | `aws ec2 describe-network-interfaces --filters Name=vpc-id,Values=<vpc-id> --region ap-northeast-1` |
| セキュリティグループ | EKS や LBC が作ったもの（Terraform の管理外）が VPC の削除を阻む | `aws ec2 describe-security-groups --filters Name=vpc-id,Values=<vpc-id> --region ap-northeast-1` |
| EBS ボリューム | Phase 6 では PVC を使わないため通常は残らない。PVC を追加した場合は reclaim policy で残り得る | `aws ec2 describe-volumes --filters Name=status,Values=available --region ap-northeast-1` |
| NAT Gateway / Elastic IP | NAT を消しても EIP が未解放だと、未使用の IPv4 として課金が続く | `aws ec2 describe-nat-gateways --region ap-northeast-1` / `aws ec2 describe-addresses --region ap-northeast-1` |
| ECR リポジトリ / イメージ | `force_delete` が無効、手作業で作ったリポジトリ | `aws ecr describe-repositories --region ap-northeast-1` |
| CloudWatch Logs ロググループ | EKS は `/aws/eks/<cluster>/cluster` を作り、保持期間を設定しないと残る。ログ有効化時のみ | `aws logs describe-log-groups --log-group-name-prefix /aws/eks/ --region ap-northeast-1` |
| IAM ロール / ポリシー | Terraform 管理外で手作業で作ったもの | `aws iam list-roles --query "Roles[?contains(RoleName, 'workboard-learning')].RoleName"` |
| Terraform state | `terraform.tfstate` は PC のローカルにのみある。削除後も残るが、機密を含み得るので不要になったら安全に消す（Git に入れない） | `phases/06-eks-foundation/terraform/` の `terraform.tfstate*` |
| kubeconfig | `.kube/workboard-eks.yaml` が削除済みクラスターを指す | 対象を確認してこのファイルだけ削除する |
| 課金の確認 | 翌日以降に請求の内訳で EKS、EC2、NAT、Public IPv4 が止まったか確認 | AWS Billing and Cost Management（Cost Explorer） |

## state を失った場合

`terraform.tfstate` を失うと `terraform destroy` で消せません。タグ `Project=workboard-learning` で、上の表の順にコンソールまたは CLI で手作業で削除します。順序は、ノードグループ → クラスター → NAT Gateway → EIP → ENI/SG → subnet → IGW → VPC → ECR → IAM。

## 破棄前に確認すること

- 削除してよい対象のクラスター名・アカウント・region を声に出して確認した。
- Phase 6 の DB は emptyDir のため、保存すべきデータはない（ダミーのみ）。
- Phase 7 の資産が残っていない。
