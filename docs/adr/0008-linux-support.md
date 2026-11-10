# ADR-0008: Linux（Bash）対応は PowerShell 版と並べた Bash 版で行う

## Status

採用（2026-11-10）。ユーザーの決定。全体に適用。

## Context

教材は Windows PowerShell 前提で作られており、kind の導入・クラスター構築・学習ポータルの起動は `.ps1` だけだった。Linux（Ubuntu など）でも Phase 0〜3 と学習ポータルを使えるようにしたい。Windows の既存の動作と手順は変えない。

## Decision

- `tools/` と `phases/NN-*/scripts/` の各 `.ps1` に、同じ場所・同じ名前・同じ引数・同じ処理の `.sh` を並べる。クラスター名・kubeconfig・ポート・メッセージの意味は同じにする。
  - `tools/kind-common.sh`（共通関数）、`tools/kind-install.sh`、`tools/start-learning.sh`、`phases/02-kind-basics/scripts/{env,up}.sh`、`phases/03-config-storage/scripts/{env,up}.sh`。
  - `env.sh` は `source` で現在のシェルに読み込む（直接実行すると案内して終了する）。共通関数は対話シェルに読み込まれるため `set -e` を設定しない。`up.sh` などの実行用スクリプトが `set -euo pipefail` を設定する。
  - `kind-install.sh` は Linux（x86_64 / arm64）の公式 release と `.sha256sum` を取得・照合し、`.tools/kind` に置く。sudo と PATH の永続変更は不要。`.tools/kind.exe` とは共存する。
- Bash 4 以降を前提とする。macOS 標準の bash 3.2 は対象外で、macOS の kind 導入は公式手順に任せる。外部コマンドは `docker`、`kind`、`kubectl`、`curl`、`sha256sum` 程度に限り、新しい依存は増やさない。
- `.gitattributes` の `*.sh text eol=lf` で LF を保ち、`.sh` は BOM なしで保存して実行権限を付ける。
- ラボ README は、シェルで異なるコマンドを `**Windows (PowerShell):**` と `**Linux / macOS / WSL (Bash):**` の見出しで並べて書く。両シェルで同じコマンド（`kubectl` など）は、1つの `text` ブロックにまとめる。
- 学習ポータルは、README の PowerShell ブロックと直後の Bash ブロックを1つの手順にまとめ、画面のタブで切り替える。既定は `navigator.userAgent` に Windows を含むかで決め、選択はブラウザーの localStorage に保存する。
- `learning-portal/tests/test_platform_scripts.py` で、各 `.ps1` に対応する `.sh` があること（逆も）と、`.sh` が LF・BOM なしであることを確認する。

## Alternatives

- **Python 一本化:** 1つのスクリプトで全 OS に対応でき保守は一本になる。ただし、学習者が読む対象が「シェルのコマンド列」から「Python の制御コード」に変わり、Windows の既存手順（`.ps1`）も置き換える必要があるため採用しなかった。
- **PowerShell 7（pwsh）を Linux にも入れる:** `.ps1` を共有できる。ただし Linux の学習者に追加の導入を要求し、Windows PowerShell 5.1（BOM 付き UTF-8 前提）との互換も保つ必要があるため採用しなかった。
- **WSL だけを案内する:** 保守は増えないが、Linux ネイティブの利用者に対応できない。

## Consequences

- スクリプトの二重保守が生じる。変更時は `.ps1` と `.sh` の両方を更新する（`AGENTS.md`）。同期テストは存在と改行しか確認せず、処理内容の一致は人が見直す。
- ラボ README のシェル別コマンドは並べて書くため、手順の分量が増える。
- ネイティブ Linux、macOS、Docker Engine 単独の環境は実機で未検証。

## Evidence

- WSL2 Ubuntu（Docker Desktop の WSL 統合）で、`bash -n` による全 `.sh` の構文確認、`tools/kind-install.sh`（取得・SHA-256 照合・再実行）、`phases/03-config-storage/scripts/up.sh`（既存の `workboard-phase3` に対する冪等な再実行）、`phases/02-kind-basics/scripts/up.sh`（新規構築、Node Ready、全 Deployment 1/1、migration Job Complete、再実行）に成功した。Phase 2 の検証用クラスターは確認後に削除した。
- WSL のホーム配下へ複製した学習ポータルで、単体テスト、教材生成、サーバー起動、bootstrap、保存 API に成功した。WSL には Node.js が無く、画面のビルドと `tools/start-learning.sh` の通し実行は未検証。
- Windows 側で、全 `.ps1` の構文解析、単体テスト、教材生成、`npm run build` が成功した。
