#!/usr/bin/env bash
# EKS クラスターに接続するための専用 kubeconfig（.kube/workboard-eks.yaml）を作成・更新する（update-kubeconfig.ps1 の Bash 版）。
# 承認済みの AWS 環境でだけ手で実行する。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
confirm_aws_target
aws eks update-kubeconfig --name "$CLUSTER_NAME" --region "$REGION" --kubeconfig "$LAB_KUBECONFIG"
kubectl --kubeconfig "$LAB_KUBECONFIG" get nodes
