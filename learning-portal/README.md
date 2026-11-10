# ローカル学習ポータル

Phase 0〜9 の教材、構成図、用語、確認コマンド、設計課題を一つの画面で読み、メモと回答を保存します。Phase 0〜9 はすべて各ラボの README を原本にした教材です。Phase 6・7 の AWS の手順は静的検証だけで、AWS 上では未検証です。画面のコマンドは表示するだけで、ポータルは実行しません。

## 起動する

Python 3.11 以降と Node.js が使える PowerShell（Windows）または Bash 4 以降（Linux / macOS / WSL）で、リポジトリ直下から実行します。Linux では `python3`・`node`・`npm` が PATH にあることが前提で、Docker はポータルの起動には不要です（ラボの実行には必要）。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File tools/start-learning.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash tools/start-learning.sh
```

教材データの更新、必要時の npm 依存導入、画面のビルド後に、[http://127.0.0.1:8765](http://127.0.0.1:8765) で起動します。このターミナルは実行中のまま残してください。初回の npm 導入にはネットワーク接続が必要です。

8765 番が使用中の場合は既存プロセスを停止せず、説明を表示して終了します。すでにポータルを起動しているなら同じ URL を開いてください。ポータルは `127.0.0.1` にのみ待ち受け、外部公開・ホスティング登録をしません。

終了は `Ctrl+C` です。ポータルを終了・再起動しても記録は残ります。**WorkBoard・kind・Pod・既存の port-forward・他の Codex / Claude セッションは起動も停止もしません。**

## 記録の保存先

メモ・回答・完了状態・採点結果は `learning-portal/.data/progress.sqlite3` に保存します。このフォルダーは Git の対象外です。画面からの保存はローカルだけで完結し、モデルへ送信しません。バックアップする場合はポータルを停止してから `.data` をコピーしてください。

記録はこのポータルだけに保存し、ラボ README には書きません。初回だけ、旧形式で README に記入された Lab 00〜02 の学習メモと回答があれば読み取ります（新しい README は項目名の一覧だけで、取り込む記入はありません）。元の Markdown は変更しません。既存の DB 記録は再起動時にも上書きしません。`誤った記述→訂正` の履歴も元のまま取り込みます。未記録・テンプレートだけの回答は空にし、未実施のフェーズを自動で完了扱いにしません。

ラボの「完了条件」と画面の「学習目標」は異なるため、チェックを位置で対応させません。既存ラボの全完了チェックが付いていた事実はフェーズの完了状態として取り込み、各学習目標のチェックは画面で改めて確認します。

教材そのものは `content/build_content.py` で設計書・ラボから再生成します。教材更新はユーザーの保存内容の再取り込みではありません。

## AI で採点する（Codex / Claude）

API キーの入力は不要です。ローカルに Codex CLI か Claude Code CLI を導入し、事前に `codex login`、または `claude` でログインしておきます。画面の「AI と理解を振り返る」の横で採点に使う AI を選べます（既定は利用可能な最初のもの。選択はブラウザーの localStorage に保存）。画面の「AI と理解を振り返る」を操作したときだけ、そのフェーズの設計課題・評価基準・入力した回答とメモを、選んだ CLI のログイン先へ送信します。

| | Codex | Claude |
| --- | --- | --- |
| 送信先 | Codex 経由で OpenAI のモデル | Claude Code 経由で Anthropic のモデル |
| 利用枠 | 利用中の Codex アカウント | 利用中の Claude アカウント |
| 起動時の確認 | `--version` / `login status` / `features list` | `--version` / `auth status`（`loggedIn: true`） |
| 採点モデル（既定） | `gpt-6-luna` | `claude-sonnet-5-5` |
| 採点モデルの変更 | 環境変数 `CODEX_GRADER_MODEL` | 環境変数 `CLAUDE_GRADER_MODEL` |
| 実行ファイルの指定 | `CODEX_CLI_PATH` | `CLAUDE_CLI_PATH`（Windows は `.exe` の絶対パス、Linux は実行権限のある実行ファイルまたは npm の `codex.js`） |

採点モデルは CLI の `--model` で毎回指定します（Codex はユーザー設定を読まないため、`~/.codex/config.toml` の `model` は使われません）。自分の契約で使えないモデルの場合は、ポータルを起動する前に上の環境変数で変更してください。使えないモデルを指定すると採点は失敗として表示され、点数は付きません。採点に使うモデルは、画面の採点 AI の選択肢に「Codex（gpt-6-luna）」のように表示されます。起動時の確認ではモデルへ接続しません。CLI が見つからない・未ログインの場合も、教材の閲覧と記録の保存は使えます。ログイン後にポータルを再起動してください。どちらも通常の導入先から実行ファイルを検出し、特殊な導入先では起動前に上記の環境変数で絶対パスを指定できます。認証情報をポータルのコードや教材へコピーしないでください。

採点は既存セッションを再開せず、独立した一時セッションで実行します。実行場所は一時フォルダーで、学習者の入力はシェル引数へ埋め込まず標準入力だけで渡します。採点のために Kubernetes・Docker・ファイルを操作させません。

- Codex: sandbox は read-only、ユーザー設定読込は無効。対応 CLI では shell・exec・apps・plugins・browser 等も無効にします。
- Claude: `-p`、`--tools ""`（全ツール無効）、`--strict-mcp-config`（MCP 無効）、`--restricted`（ユーザー/プロジェクト/ローカル設定を無視）、`--disable-slash-commands`、`--no-session-persistence`、`--permission-mode dontAsk`、`--permission-prompts none`、`--json-schema` を使い、結果は `--output-format json` の `structured_output` から取り出します。`--bare` は API キー専用で claude.ai ログインでは使えないため使いません。そのため、グローバルの `CLAUDE.md` 等の指示文脈が読み込まれ得ますが、ツールは全て無効です（`CLAUDE.md` が実際に読み込まれるかは未確認）。

同時採点はプロバイダーをまたいで全体で1件、上限240秒です。タイムアウトや終了時は採点プロセスのツリーを停止します。失敗時に点数を捏造せず、日本語のエラーを返します。CLI の生ログはブラウザーに表示せず、標準エラーは破棄します。

各設計課題は5点満点、総合点は全課題の合計から0〜100点へ換算します。構造化された出力をサーバー側で再検証してから保存します。矢印で訂正した回答は訂正後を最終見解として評価します。採点は学習の補助で、実環境の操作を観察した証明ではありません。

画面で先に入力を保存し、サーバーは採点開始時と終了時に最新の保存内容と一致することを確認します。古い採点リクエストや、採点中の別タブ等の更新があれば、最新の記録を上書きせず409で再採点を案内します。回答・メモを後から変更した場合は、古い採点結果を外します。

## 実装と確認

バックエンドは Python 標準ライブラリの HTTP サーバーと SQLite、画面は React 19.3.1・TypeScript・Vite です。構成図は HTML カードと境界枠、SVG の矢印で描き、Kubernetes / AWS の公式アイコン（`public/icons/`、出典は `public/icons/README.md`）を使います。図の定義は `content/build_content.py` の `phase_diagram` で、教材・図解・ノート・評価を React コンポーネントで描画します。入力と画面の状態は React の state、保存・採点は小さな hook で管理します。React Router や外部の状態管理ライブラリは使いません。React の安定版と型定義の互換性は [公式ドキュメント](https://react.dev/versions) と npm metadata で確認しています。通常の入口は上の起動スクリプトです。ラボの手順は、README の PowerShell ブロックと直後の Bash ブロックを1つの手順にまとめ、画面のタブ（Windows (PowerShell) / Linux / macOS / WSL (Bash)）で切り替えます。初期の選択はブラウザーの OS（`navigator.userAgent`）から決め、選択は localStorage に保存します。原本の README が唯一の情報源で、画面用に別のコマンドは持ちません。画面だけの Vite preview では保存 API は動きません。

```powershell
python -m unittest discover -s learning-portal/tests -v
```

テストは一時フォルダーの DB と別ポートを使い、実際の学習記録や既存ラボを上書きしません。モデルに接続しない通常テストと、明示的な接続確認を分離しています。

2026-11-09 の確認:

- SQLite の再起動保持、初回 import の非破壊性、保存、回答変更後の採点無効化を確認。
- 別タブ保存と遅延採点の競合、入力制限、同一 Origin/Host、静的ファイルの境界、資料の allowlist を確認。
- CLI 引数へ回答を埋め込まないこと、タイムアウト時のプロセス停止、出力検証と点数計算を確認。
- 実 Codex CLI 0.167.0 で**架空の短い回答1問だけ**を送信し、構造化出力と100点の算出を確認。既存のユーザー回答は送信していない。
- 実 Claude Code CLI 2.1.321 で**架空の短い回答1問だけ**を送信し、構造化出力の検証と100点の算出を確認（約10秒）。既存のユーザー回答は送信していない。
- `start-learning.ps1` から教材生成・UI ビルド・サーバー起動に成功。画面と bootstrap と許可された資料は HTTP 200、全10フェーズを表示し、Codex ログイン検出も成功。起動確認後はこのポータルだけを停止した。

ルート配信は `dist` のみです。参考資料は教材に列挙した Markdown の allowlist だけを `/api/source` からプレーンテキストで表示し、任意のリポジトリファイルは公開しません。
