#!/usr/bin/env bash
# HTTP 応答を一定間隔で記録する（watch-http.ps1 の Bash 版）。復旧時間の測定に使う。
# 使い方: bash watch-http.sh [URL] [間隔の秒数] [回数（0 は Ctrl+C まで）]
# 出力: 時刻 HTTP ステータス 所要秒数（接続できないときのステータスは 000）
set -euo pipefail
url="${1:-http://localhost:8082/api/v1/tasks}"
interval="${2:-1}"
count="${3:-0}"
i=0
while ((count == 0 || i < count)); do
  result=$(curl -s -o /dev/null --max-time 2 -w '%{http_code} %{time_total}' "$url" || true)
  printf '%s %s\n' "$(date +%H:%M:%S)" "${result:-000 0}"
  i=$((i + 1))
  sleep "$interval"
done
