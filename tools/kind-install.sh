#!/usr/bin/env bash
# 公式 kind を SHA-256 照合して .tools/kind に置く（kind-install.ps1 の Linux 版）。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/kind-common.sh"

[[ "$(uname -s)" == 'Linux' ]] || die 'このスクリプトは Linux（WSL を含む）用です。他の OS は Phase 2 の手動手順を使ってください。'
case "$(uname -m)" in
  x86_64 | amd64) asset='kind-linux-amd64' ;;
  aarch64 | arm64) asset='kind-linux-arm64' ;;
  *) die "未対応の CPU です: $(uname -m)。Phase 2 の手動手順を使ってください。" ;;
esac

mkdir -p "$TOOLS_DIRECTORY"
kind_path="$TOOLS_DIRECTORY/kind"
if [[ -e "$kind_path" ]]; then
  installed=$("$kind_path" version) || die '既存の .tools/kind を実行できません。自動上書きはしません。'
  [[ "$installed" == *"$KIND_VERSION"* ]] || die '既存の .tools/kind のバージョンが異なります。自動上書きはしません。'
  echo "kind $KIND_VERSION は導入済みです。"
  exit 0
fi

download_path="$kind_path.download"
trap 'rm -f "$download_path"' EXIT
url="https://github.com/kubernetes-sigs/kind/releases/download/$KIND_VERSION/$asset"
echo "公式 kind $KIND_VERSION を .tools に取得し、SHA-256 を検証します。"
curl -fsSL --retry 3 -o "$download_path" "$url"
expected=$(curl -fsSL --retry 3 "$url.sha256sum" | awk '{print $1; exit}')
actual=$(sha256sum "$download_path" | awk '{print $1}')
if [[ ! "$expected" =~ ^[0-9a-fA-F]{64}$ || "${actual,,}" != "${expected,,}" ]]; then
  die 'kind の SHA-256 が一致しません。取得ファイルは実行しません。'
fi
chmod +x "$download_path"
mv "$download_path" "$kind_path"
"$kind_path" version
echo 'このシェルで kind を使うには source phases/02-kind-basics/scripts/env.sh を実行してください。'
