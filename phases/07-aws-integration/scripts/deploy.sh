#!/usr/bin/env bash
# eks overlay を EKS へ適用する（deploy.ps1 の Bash 版）。承認済みの AWS 環境でだけ手で実行する。
# ダミーのレジストリ・RDS エンドポイント・許可 CIDR を、確認した実際の値に置き換えて適用する。
# 事前に write-db-secret を実行し、環境変数 WORKBOARD_ALLOWED_CIDR（例: 自分の IP/32）を設定する。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"

allowed_cidr="${WORKBOARD_ALLOWED_CIDR:-}"
if [[ ! "$allowed_cidr" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}/([0-9]|[12][0-9]|3[0-2])$ || "$allowed_cidr" == 0.0.0.0/* ]]; then
  echo 'WORKBOARD_ALLOWED_CIDR に、公開を許可する自分の IP の CIDR（例: 198.51.100.7/32）を設定してください。0.0.0.0/0 は不可。' >&2
  exit 1
fi
overlay=phases/07-aws-integration/kustomize/overlays/eks
[[ -e "$REPOSITORY_ROOT/$overlay/secrets/db.env" ]] || { echo '先に write-db-secret を実行してください。' >&2; exit 1; }
confirm_aws_target
registry="$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
rds_host="$(terraform_output db_endpoint_address)"
common=(--kubeconfig "$LAB_KUBECONFIG" --context "arn:aws:eks:$REGION:$AWS_ACCOUNT_ID:cluster/$CLUSTER_NAME")
cd "$REPOSITORY_ROOT"

# 完了済み Job の spec は変更できない。Alembic は何度実行しても安全なので、毎回削除してから適用する。
kubectl "${common[@]}" -n workboard delete job workboard-migrate --ignore-not-found
kubectl kustomize "$overlay" \
  | sed -e "s|111122223333.dkr.ecr.ap-northeast-1.amazonaws.com|$registry|g" \
        -e "s|workboard-learning-db.example.ap-northeast-1.rds.amazonaws.com|$rds_host|g" \
        -e "s|203.0.113.10/32|$allowed_cidr|g" \
  | kubectl "${common[@]}" apply -f -
kubectl "${common[@]}" -n workboard wait --for=condition=complete job/workboard-migrate --timeout=300s
for deployment in workboard-api workboard-web; do
  kubectl "${common[@]}" -n workboard rollout status "deployment/$deployment" --timeout=180s
done
kubectl "${common[@]}" -n workboard get pods,deploy,svc,ingress
echo 'ALB が作成されるまで数分かかります。kubectl get ingress の ADDRESS を README の手順で確認してください。'
