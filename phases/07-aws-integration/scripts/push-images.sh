#!/usr/bin/env bash
# WorkBoard の API/Web イメージをビルドして ECR へ push する（push-images.ps1 の Bash 版）。ECR リポジトリ（workboard-api, workboard-web）が既にあること。
# 承認済みの AWS 環境でだけ手で実行する。タグは kustomize/overlays/eks の newTag と同じ phase7。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
confirm_aws_target
registry="$AWS_ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"
cd "$REPOSITORY_ROOT"

aws ecr get-login-password --region "$REGION" | docker login --username AWS --password-stdin "$registry"

# EKS のノードは x86_64。Apple Silicon などでも linux/amd64 を明示してビルドする。
docker build --platform linux/amd64 --provenance=false --target runtime -t "$registry/workboard-api:phase7" app/api
docker build --platform linux/amd64 --provenance=false -t "$registry/workboard-web:phase7" app/web
docker push "$registry/workboard-api:phase7"
docker push "$registry/workboard-web:phase7"
echo 'push 完了。'
