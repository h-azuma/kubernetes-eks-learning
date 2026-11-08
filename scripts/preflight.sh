#!/usr/bin/env bash

git_available=0

show_tool_version() {
  local name="$1" command="$2" output
  shift 2
  if ! command -v "$command" >/dev/null 2>&1; then
    printf '[未導入] %s : コマンドが見つかりません\n' "$name"
    return 1
  fi
  if ! output=$("$command" "$@" 2>&1); then
    printf '[確認失敗] %s : バージョンを取得できません\n' "$name"
    return 1
  fi
  if [[ -z "$output" ]]; then
    printf '[確認失敗] %s : バージョン出力がありません\n' "$name"
    return 1
  fi
  printf '[利用可能] %s : %s\n' "$name" "$output"
}

printf '環境確認（バージョン表示のみ。稼働状態・互換性は未確認）\n'
if show_tool_version 'Git' git --version; then git_available=1; fi
show_tool_version 'Docker' docker --version
show_tool_version 'Docker Compose' docker compose version
show_tool_version 'kubectl' kubectl version --client=true --output=yaml
show_tool_version 'kind' kind version
show_tool_version 'Python' python3 --version
show_tool_version 'Node.js' node --version
show_tool_version 'AWS CLI' aws --version
show_tool_version 'Terraform' terraform version

if [[ "$git_available" -ne 1 ]]; then
  printf 'Phase 0 必須の Git を確認してください。\n'
  exit 1
fi
printf 'Phase 0 の必須ツールを確認しました。他ツールの不足は後続フェーズで対応できます。\n'
exit 0
