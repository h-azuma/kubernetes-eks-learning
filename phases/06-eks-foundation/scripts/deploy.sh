#!/usr/bin/env bash
# eks overlay を EKS へ適用する（deploy.ps1 の Bash 版）。承認済みの AWS 環境でだけ手で実行する。
# overlay のダミーのレジストリ（111122223333...）を、確認したアカウントの ECR に置き換えて適用する。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
confirm_aws_target
registry="$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
placeholder_registry='111122223333.dkr.ecr.ap-northeast-1.amazonaws.com'
common=(--kubeconfig "$LAB_KUBECONFIG" --context "arn:aws:eks:$REGION:$AWS_ACCOUNT_ID:cluster/$CLUSTER_NAME")
overlay=phases/06-eks-foundation/kustomize/overlays/eks
cd "$REPOSITORY_ROOT"

secret_file="$REPOSITORY_ROOT/$overlay/secrets/db.env"
if [[ ! -e "$secret_file" ]]; then
  (umask 077; printf 'POSTGRES_PASSWORD=%s\n' "$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')" > "$secret_file")
  echo "ローカル専用の DB パスワードを生成しました（値は表示しません）: $secret_file"
fi
# 完了済み Job の spec は変更できない。Alembic は何度実行しても安全なので、毎回削除してから適用する。
kubectl "${common[@]}" -n workboard delete job workboard-migrate --ignore-not-found
kubectl kustomize "$overlay" | sed "s|$placeholder_registry|$registry|g" | kubectl "${common[@]}" apply -f -
kubectl "${common[@]}" -n workboard rollout status deployment/workboard-postgres --timeout=180s
kubectl "${common[@]}" -n workboard wait --for=condition=complete job/workboard-migrate --timeout=300s
for deployment in workboard-api workboard-web; do
  kubectl "${common[@]}" -n workboard rollout status "deployment/$deployment" --timeout=180s
done
kubectl "${common[@]}" -n workboard get pods,deploy,svc
echo '適用完了。README の port-forward 手順（8086 番）で画面を開いてください。'
