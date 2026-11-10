#!/usr/bin/env bash
# source して使う: source phases/05-security-and-failure/scripts/env.sh
# 実行しただけでは現在のシェルに設定を残せないため、直接実行された場合は案内して終了する。
if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
  echo 'このファイルは実行せず、source で読み込んでください: source phases/05-security-and-failure/scripts/env.sh' >&2
  exit 1
fi
source "$(dirname "${BASH_SOURCE[0]}")/../../../tools/kind-common.sh"
CLUSTER_NAME='workboard-phase5'
CLUSTER_CONTEXT="kind-$CLUSTER_NAME"
LAB_KUBECONFIG="$REPOSITORY_ROOT/.kube/workboard-phase5.yaml"
use_kind_environment "$LAB_KUBECONFIG"
