#!/usr/bin/env bash
# source して使う: source phases/08-devops-observability/scripts/env.sh
# 実行しただけでは現在のシェルに設定を残せないため、直接実行された場合は案内して終了する。
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo 'このファイルは実行せず、source で読み込んでください: source phases/08-devops-observability/scripts/env.sh' >&2
  exit 1
fi
source "$(dirname "${BASH_SOURCE[0]}")/../../../tools/kind-common.sh"
CLUSTER_NAME='workboard-phase8'
CLUSTER_CONTEXT="kind-$CLUSTER_NAME"
LAB_KUBECONFIG="$REPOSITORY_ROOT/.kube/workboard-phase8.yaml"
# Argo CD は v3.6.1 の公式 install.yaml を、コミット SHA で固定した URL から取得する（decisions/0015）。
ARGOCD_INSTALL_URL='https://raw.githubusercontent.com/argoproj/argo-cd/94037c4d4e1af4bd0651d37a179fbd9e347e668c/manifests/install.yaml'
use_kind_environment "$LAB_KUBECONFIG"
