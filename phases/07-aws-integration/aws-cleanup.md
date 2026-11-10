# Phase 7: AWS 資産の削除と点検

**開始前に必ずレビューしてください。** 以下は、AWS の利用を承認した後に学習者が自分で実行する例です。この教材の作成時には実行していません。削除は元に戻せません。対象のアカウント・region・クラスター名を確認してから実行します。Phase 6 の資産（クラスター、VPC、ECR）の削除は Phase 6 の `aws-cleanup.md` です。**Phase 7 の資産を先に削除し、その後で Phase 6 を削除します。**

## 削除の順序（この順序が重要）

1. **Ingress を先に削除して、ALB を消す。** ALB は AWS Load Balancer Controller が作る。Controller（Helm release）や IAM ロールを先に消すと、ALB とそのセキュリティグループ・ターゲットグループが Kubernetes から消せず、AWS に残る（課金が続き、VPC の削除も阻む）。

   ```text
   kubectl -n workboard delete ingress workboard
   kubectl -n workboard get ingress
   aws elbv2 describe-load-balancers --region ap-northeast-1
   ```

   `describe-load-balancers` から、この ALB が消えるまで待つ。

2. **アプリを削除する。**

   ```text
   kubectl delete namespace workboard
   ```

3. **Helm release を削除する。** CRD は `helm uninstall` では削除されない（`helm` は CRD を削除しない）。クラスターごと消すなら不要。

   ```text
   helm uninstall aws-load-balancer-controller -n kube-system
   helm list -n kube-system
   ```

4. **RDS を削除する前に、データの要否を判断する。**
   - 最終スナップショットを取るか（`db_skip_final_snapshot = false` が既定。スナップショットは削除後も保管料金がかかる）。
   - 不要なら手動スナップショット・最終スナップショットを後で削除する。
   - 削除保護を有効にしている場合は、先に `db_deletion_protection = false` にして `apply`。

5. **Phase 7 の Terraform を削除対象として読み、承認を確認して削除する。**

   ```text
   terraform -chdir=phases/07-aws-integration/terraform plan -destroy
   terraform -chdir=phases/07-aws-integration/terraform destroy
   ```

   削除されるのは、RDS インスタンス、DB subnet group、セキュリティグループ、パラメータグループ、LBC の IAM ロールとポリシー、Pod Identity association、Pod Identity Agent アドオン。

6. **Phase 6 を削除する**（Phase 6 の `aws-cleanup.md`）。

## 残り得る資産の点検リスト

| 資産 | なぜ残るか | 確認コマンド例 |
| --- | --- | --- |
| ALB / ターゲットグループ | Ingress より先に Controller やクラスターを消した | `aws elbv2 describe-load-balancers --region ap-northeast-1` / `aws elbv2 describe-target-groups --region ap-northeast-1` |
| ALB が作った SG | ALB の SG（`k8s-` で始まる名前）と、ノード SG へ追加された規則が VPC の削除を阻む | `aws ec2 describe-security-groups --filters Name=vpc-id,Values=<vpc-id> --region ap-northeast-1` |
| ENI | ALB・RDS の ENI が残り、subnet/VPC の削除を阻む | `aws ec2 describe-network-interfaces --filters Name=vpc-id,Values=<vpc-id> --region ap-northeast-1` |
| RDS インスタンス | 削除保護、Terraform の外で作った | `aws rds describe-db-instances --region ap-northeast-1` |
| RDS スナップショット（最終・手動） | 削除後も残る。保管料金 | `aws rds describe-db-snapshots --region ap-northeast-1` |
| RDS の自動バックアップ | インスタンス削除で削除される（保持設定による。残す設定にした場合は要確認） | `aws rds describe-db-instance-automated-backups --region ap-northeast-1` |
| Secrets Manager のシークレット | RDS 管理のシークレットはインスタンス削除で削除される（公式資料で確認）。削除までの猶予期間・課金の扱いは要確認 | `aws secretsmanager list-secrets --region ap-northeast-1 --include-planned-deletion` |
| IAM ロール / ポリシー | Terraform の外で作った場合 | `aws iam list-roles --query "Roles[?contains(RoleName, 'workboard-learning')].RoleName"` |
| Pod Identity association | クラスターの削除で消えるが、確認する | `aws eks list-pod-identity-associations --cluster-name workboard-learning --region ap-northeast-1` |
| `db.env` | Secrets Manager から複製した DB パスワードを含む Git 管理外のファイル。不要になったら削除 | `phases/07-aws-integration/kustomize/overlays/eks/secrets/db.env` |
| ダンプファイル | データ移行で作った `tasks.dump` | 作業した一時ディレクトリを確認して削除 |
| Terraform state | `phases/07-aws-integration/terraform/terraform.tfstate*`（ローカルのみ、Git 管理外）。DB の識別子などが含まれる | 不要になったら安全に削除 |
| 課金の確認 | 翌日以降に請求の内訳で RDS、ELB、Secrets Manager、スナップショットを確認 | AWS Billing and Cost Management |

## state を失った場合

`terraform.tfstate` を失うと `terraform destroy` で消せません。タグ `Project=workboard-learning` で、ALB → RDS → セキュリティグループ → IAM → アドオン の順に手作業で削除します。
