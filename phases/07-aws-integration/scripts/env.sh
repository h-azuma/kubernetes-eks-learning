#!/usr/bin/env bash
# source して使う: source phases/07-aws-integration/scripts/env.sh
# このシェルだけで、EKS 用の kubeconfig（.kube/workboard-eks.yaml）と AWS のリージョンを設定する。
# AWS の操作はしない。AWS を操作する各スクリプトは confirm_aws_target で対象を確認してから進む。
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo 'このファイルは実行せず、source で読み込んでください: source phases/07-aws-integration/scripts/env.sh' >&2
  exit 1
fi
REPOSITORY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
REGION="${AWS_REGION:-ap-northeast-1}"
CLUSTER_NAME="${EKS_CLUSTER_NAME:-workboard-learning}"
LAB_KUBECONFIG="$REPOSITORY_ROOT/.kube/workboard-eks.yaml"
export AWS_REGION="$REGION"
export KUBECONFIG="$LAB_KUBECONFIG"

# 操作対象のアカウント・リージョン・クラスターを表示し、yes と入力した場合だけ続行する。AWS_ACCOUNT_ID を設定する。
confirm_aws_target() {
  local identity answer arn
  identity=$(aws sts get-caller-identity --query '[Account,Arn]' --output text) || {
    echo 'aws sts get-caller-identity に失敗しました。認証情報を確認してください。' >&2
    return 1
  }
  AWS_ACCOUNT_ID="${identity%%$'\t'*}"
  arn="${identity#*$'\t'}"
  echo "AWS アカウント: $AWS_ACCOUNT_ID"
  echo "呼び出し元     : $arn"
  echo "リージョン     : $REGION"
  echo "クラスター名   : $CLUSTER_NAME"
  read -r -p 'この対象で AWS を操作します。続行するには yes と入力してください: ' answer
  [[ "$answer" == yes ]] || { echo '中止しました。' >&2; return 1; }
}

# Phase 7 で固定する AWS Load Balancer Controller の chart バージョン（helm/aws-load-balancer-controller-values.yaml と同じ版）。
LBC_CHART_VERSION='3.6.2'
TERRAFORM_DIRECTORY="$REPOSITORY_ROOT/phases/07-aws-integration/terraform"

# terraform output の値を 1 つ返す（terraform apply 済みで、state がこのディレクトリにあること）。
terraform_output() {
  terraform "-chdir=$TERRAFORM_DIRECTORY" output -raw "$1"
}
