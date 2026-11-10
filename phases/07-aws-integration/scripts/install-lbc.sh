#!/usr/bin/env bash
# AWS Load Balancer Controller を Helm で導入・更新する（install-lbc.ps1 の Bash 版）。承認済みの AWS 環境でだけ手で実行する。
# 先に README の手順で helm template の生成物を読み、Terraform で IAM ロールと Pod Identity を作成済みであること。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
confirm_aws_target
context="arn:aws:eks:$REGION:$AWS_ACCOUNT_ID:cluster/$CLUSTER_NAME"
vpc_id="$(terraform_output vpc_id)"
cd "$REPOSITORY_ROOT"

helm repo add eks https://aws.github.io/eks-charts --force-update
helm repo update eks
# helm upgrade --install は初回だけ CRD を入れる。2 回目以降の upgrade は CRD を更新しない（README 参照）。
helm upgrade --install aws-load-balancer-controller eks/aws-load-balancer-controller \
  --version "$LBC_CHART_VERSION" \
  --namespace kube-system \
  --kubeconfig "$LAB_KUBECONFIG" --kube-context "$context" \
  --values phases/07-aws-integration/helm/aws-load-balancer-controller-values.yaml \
  --set "clusterName=$CLUSTER_NAME" --set "region=$REGION" --set "vpcId=$vpc_id"
kubectl --kubeconfig "$LAB_KUBECONFIG" --context "$context" -n kube-system rollout status deployment/aws-load-balancer-controller --timeout=180s
helm list --namespace kube-system --kubeconfig "$LAB_KUBECONFIG" --kube-context "$context"
