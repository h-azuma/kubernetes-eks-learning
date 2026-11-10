#!/usr/bin/env bash
# Phase 2/3 の env.sh・up.sh が source で読み込む共通処理（kind-common.ps1 の Bash 版）。
# 対話シェルにも source されるため、ここでは set -e などのシェルオプションを変更しない。
REPOSITORY_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
KIND_VERSION='v0.33.0'
TOOLS_DIRECTORY="$REPOSITORY_ROOT/.tools"

die() {
  printf '%s\n' "$*" >&2
  exit 1
}

use_kind_environment() {
  export KUBECONFIG="$1"
  case ":$PATH:" in
    *":$TOOLS_DIRECTORY:"*) ;;
    *) export PATH="$TOOLS_DIRECTORY:$PATH" ;;
  esac
}

assert_kind_prerequisites() {
  local tool client major minor docker_os
  for tool in docker kind kubectl; do
    command -v "$tool" >/dev/null 2>&1 || die "$tool がありません。先に Phase 2 の導入手順を実行してください。"
  done
  client=$(kubectl version --client=true --output=yaml) || die 'kubectl のバージョンを取得できません。'
  major=$(sed -n 's/^ *major: *"\{0,1\}\([0-9]*\).*/\1/p' <<<"$client" | head -n 1)
  minor=$(sed -n 's/^ *minor: *"\{0,1\}\([0-9]*\).*/\1/p' <<<"$client" | head -n 1)
  if [[ "$major" != '1' || -z "$minor" ]] || ((minor < 34 || minor > 36)); then
    die 'この Kubernetes 1.35 ラボには kubectl 1.34〜1.36 が必要です。'
  fi
  docker_os=$(docker info --format '{{.OSType}}') || die 'Docker に接続できません。Docker を起動してください。'
  [[ "$docker_os" == 'linux' ]] || die 'Docker の Linux コンテナエンジンを起動してください。'
}

initialize_kind_cluster() {
  local name="$1" kubeconfig="$2" config_path="$3" clusters
  clusters=$(kind get clusters) || die 'kind クラスター一覧を取得できません。'
  if ! grep -qxF -- "$name" <<<"$clusters"; then
    if [[ -e "$kubeconfig" ]]; then
      die 'クラスターはありませんが専用 kubeconfig が残っています。対象を確認してから対処してください。'
    fi
    mkdir -p "$(dirname "$kubeconfig")"
    kind create cluster --name "$name" --config "$config_path" --kubeconfig "$kubeconfig" --wait 180s
  elif [[ ! -e "$kubeconfig" ]]; then
    die '同名クラスターが既にありますが、この教材の kubeconfig がありません。自動変更はしません。'
  fi
}

import_workboard_images() {
  local cluster_name="$1"
  docker build --provenance=false --target runtime -t workboard-api:kind app/api
  docker build --provenance=false -t workboard-web:kind app/web
  kind load docker-image workboard-api:kind workboard-web:kind --name "$cluster_name"
}
