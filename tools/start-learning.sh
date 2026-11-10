#!/usr/bin/env bash
# 学習ポータルを起動する（start-learning.ps1 の Bash 版）。
set -euo pipefail
repository_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
portal_root="$repository_root/learning-portal"

fail() {
  echo "$*" >&2
  exit 1
}

if (exec 3<>/dev/tcp/127.0.0.1/8765) 2>/dev/null; then
  fail '127.0.0.1:8765 は使用中です。既存プロセスは停止しません。起動済みならブラウザーで同じURLを開いてください。'
fi
for name in python3 npm; do
  command -v "$name" >/dev/null 2>&1 || fail "$name がありません。Python と Node.js の導入状況を確認してください。"
done

cd "$repository_root"
echo '教材を更新し、学習画面をビルドします。WorkBoard や kind は操作しません。'
python3 "$portal_root/content/build_content.py" || fail '教材データの生成に失敗しました。'
lock_path="$portal_root/package-lock.json"
installed_lock="$portal_root/node_modules/.package-lock.json"
[[ -f "$lock_path" ]] || fail 'package-lock.json がありません。リポジトリの内容を確認してください。'
if [[ ! -f "$installed_lock" || "$lock_path" -nt "$installed_lock" ]]; then
  npm --prefix "$portal_root" ci || fail '学習画面の依存パッケージを導入できませんでした。'
fi
npm --prefix "$portal_root" run build || fail '学習画面のビルドに失敗しました。'
python3 "$portal_root/server.py" || fail '学習ポータルを起動できませんでした。'
