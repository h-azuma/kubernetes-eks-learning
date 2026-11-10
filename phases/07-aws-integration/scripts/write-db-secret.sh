#!/usr/bin/env bash
# RDS のマスターパスワードを Secrets Manager から取り出し、Git 管理外の Secret 入力ファイル db.env を作る
# （write-db-secret.ps1 の Bash 版）。値は表示しない。承認済みの AWS 環境でだけ手で実行する。
# RDS 管理のパスワードは既定で 7 日ごとに自動で変わる。変わったらこのスクリプトを再実行して deploy し直す。
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/env.sh"
confirm_aws_target
secret_file="$REPOSITORY_ROOT/phases/07-aws-integration/kustomize/overlays/eks/secrets/db.env"
secret_arn="$(terraform_output db_master_secret_arn)"

secret_json="$(aws secretsmanager get-secret-value --secret-id "$secret_arn" --region "$REGION" --query SecretString --output text)"
password="$(printf '%s' "$secret_json" | python3 -c 'import json,sys; print(json.load(sys.stdin)["password"])')"
(umask 077; printf 'POSTGRES_PASSWORD=%s\n' "$password" > "$secret_file")
echo "DB パスワードを書き出しました（値は表示しません）: $secret_file"
