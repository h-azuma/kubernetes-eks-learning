# Lab 01: Docker Compose と WorkBoard

## 学習目標

- Web・API・DB を分ける理由と、コンテナ間の DNS・ポートを説明できる。
- 起動順と readiness の違いを観察できる。
- API・ブラウザーの再起動後にデータが残る理由を説明できる。
- DB 障害時に Liveness と Readiness の違いを確認できる。

## 前提条件

Lab 00 完了、Git、Docker と Compose、Linux コンテナエンジンが必要です。初回は公式イメージ・依存のダウンロードとディスク容量が必要です。AWS の利用・課金はありません。ホストでの UI ビルドには Node.js 20.19+ または 22.12+ が必要ですが、Compose 内でもビルドできます。

## 設計課題（実装前に考える）

1. なぜ Web・API・DB を一つのコンテナにまとめないのか？
2. `depends_on` の起動順だけで DB が SQL を受け付けることを保証できるか？
3. コンテナ内の API が `localhost:5432` に接続すると、どこへ接続するか？
4. API 再起動後にタスクが残るのは、API がデータを保持しているからか？
5. DB が止まったとき API の Liveness も失敗させると、何が起きるか？

## 実装タスク

1. [構成図](architecture.md) と [ADR](decisions/0002-compose-startup-and-persistence.md) を読む。
2. 下の「Phase 1: Compose 上で WorkBoard を起動する」に従い `.env` を作成・編集する。
3. 以下のコマンドを **リポジトリ直下** で実行する。
4. 画面・API・ログを観察し、**学習ポータルの学習メモ**（項目はこのファイルの「学習メモ」節）に記録する。

## Phase 1: Compose 上で WorkBoard を起動する

Docker の Linux コンテナエンジン（Windows / macOS は Docker Desktop、Linux は Docker Engine または Docker Desktop）を起動し、リポジトリ直下で操作します。Docker エンジンは `docker info` で確認できます。kind・Terraform は今回不要です。

初回だけ `.env.example` を `.env` にコピーします。すでに `.env` がある場合は上書きせず、そのファイルを使ってください。

**Windows (PowerShell):**

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

**Linux / macOS / WSL (Bash):**

```bash
if [ ! -f .env ]; then cp .env.example .env; fi
```

`.env` をエディターで開き、`POSTGRES_PASSWORD` の例をローカル専用の値に変更します。このファイルは Git の対象外です。DB 初期化後に値を変更しても既存 DB のパスワードは自動で変わりません。

共通の起動コマンド:

```text
docker compose -f phases/01-compose/compose.yaml up --build -d
docker compose -f phases/01-compose/compose.yaml ps -a
```

`migrate` は正常終了（Exited 0）、`api` と `db` は healthy、`web` は Up が期待結果です。初回はイメージの取得・ビルドに時間がかかります。[WorkBoard](http://localhost:8080) を開くとタスクを作成・編集・削除できます。[API ドキュメント](http://localhost:8080/docs) も利用できます。

## 検証コマンド・期待結果

### 1. 設定と起動を確認する

```text
docker compose -f phases/01-compose/compose.yaml config --quiet
docker compose -f phases/01-compose/compose.yaml up --build -d
docker compose -f phases/01-compose/compose.yaml ps -a
docker compose -f phases/01-compose/compose.yaml logs --tail=30 migrate api
```

設定確認が成功し、DB→migration→API→Web の順に準備されます。`migrate` の Exited 0 は正常終了です。API・DB が healthy、Web が Up になるまで待ちます。

失敗時は `.env` の有無、Docker Desktop の起動、8080 番の重複、`logs` を確認します。初期化後に `.env` の認証値を変えると DB 内の値と不一致になります。volume 削除で解決しようとせず、まず元の設定を確認してください。引数なしの `config` は展開後の認証値も表示するため、ログ共有時は `--quiet` を使います。

### 2. 画面で CRUD と再読込を試す

[http://localhost:8080](http://localhost:8080) を開きます。

1. タイトル「Compose の学習」、説明を入力して「作成」。一覧に未着手のタスクが出る。
2. 「編集」からタイトル・説明・ステータスを変更し「更新」。変更が反映される。
3. 絞り込みを変え、該当ステータスだけが表示されることを確認。
4. ブラウザーを再読込し、同じタスクが残ることを確認。
5. 削除の動作は、後の永続化実験を終えてから確認する。

不正な入力、通信失敗時は画面のメッセージを確認します。API の具体的な仕様は [OpenAPI](http://localhost:8080/docs) から確認できます。

### 3. API と health を確認する

**Windows (PowerShell):**

```powershell
Invoke-RestMethod http://localhost:8080/health/live
Invoke-RestMethod http://localhost:8080/health/ready
Invoke-RestMethod http://localhost:8080/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -i http://localhost:8080/health/live
curl -i http://localhost:8080/health/ready
curl -i http://localhost:8080/api/v1/tasks
```

正常時は両 health が 200、一覧には画面で作成したタスクが出ます。

### 4. 再起動・公開ポート・データ保持を観察する

```text
docker compose -f phases/01-compose/compose.yaml restart api
docker compose -f phases/01-compose/compose.yaml ps
docker compose -f phases/01-compose/compose.yaml port web 80
docker compose -f phases/01-compose/compose.yaml port api 8000
docker compose -f phases/01-compose/compose.yaml port db 5432
```

API が healthy に戻ったらブラウザーを再読込します。タスクは残ります。Web の公開先は `127.0.0.1:8080`、API/DB は公開ポートなし（port コマンドの「公開されていない」というエラーは期待どおり）です。

通常の `down` と再起動も試せます:

```text
docker compose -f phases/01-compose/compose.yaml down
docker compose -f phases/01-compose/compose.yaml up -d
```

同じタスクが残ることを確認してから、画面の「削除」で検証用タスクを削除してください。

### 5. 自動 API テストを実行する

```text
docker compose -f phases/01-compose/compose.yaml --profile test run --build --rm tests
```

テストは `workboard_test` という専用 PostgreSQL の tmpfs 上で migration・CRUD・入力エラー・health を確認します。終了コード 0、全テスト成功が期待結果です。学習用 DB のデータを削除しません。

## 故障実験: DB 停止と復旧

学習用環境を利用中のほかの人がいないことを確認してから実行します。

```text
docker compose -f phases/01-compose/compose.yaml stop db
```

次の URL のステータスを確認します。PowerShell の `curl` は別コマンドの別名になり得るため `curl.exe` を明記します。

**Windows (PowerShell):**

```powershell
curl.exe -i http://localhost:8080/health/live
curl.exe -i http://localhost:8080/health/ready
```

**Linux / macOS / WSL (Bash):**

```bash
curl -i http://localhost:8080/health/live
curl -i http://localhost:8080/health/ready
```

期待結果は Liveness 200、Readiness 503。API の DB 接続は数秒で失敗し、画面でのタスク操作も失敗し得ます。API のコンテナが unhealthy になっても、Compose が自動で再起動するとは限りません。

次で復旧し、Readiness が 200 に戻るまで待ちます。

```text
docker compose -f phases/01-compose/compose.yaml start db
docker compose -f phases/01-compose/compose.yaml ps
```

API を再起動しなくても接続が回復することと、既存タスクが残ることを観察します。**volume を消す実験は今回は行いません。** 実施する場合は、対象の volume と失われるデータを確認し、削除の明示承認後に別途行います。

## UI の型チェックとビルド（任意）

ホスト側で UI の型チェック・ビルドを行う場合は、リポジトリ直下で実行します。

```text
npm --prefix app/web ci
npm --prefix app/web run build
```

## 後片付け

```text
docker compose -f phases/01-compose/compose.yaml --profile test down
```

学習用 volume は残ります。`-v` は付けません。テスト DB は tmpfs のためコンテナ削除で消えます。

## 完了条件

- [x] Web・API・DB が起動し、画面で作成・一覧・更新・削除を確認した。
- [x] ブラウザー再読込・API 再起動・通常の down/up 後にデータが残った。
- [x] Web だけがループバックへ公開されていることを確認した。
- [x] API テストが成功した。
- [x] DB 停止時の health の差と復旧を観察した。
- [x] 下記に観察結果と設計課題への回答を書き、理由を説明できる。
- [x] コンテナを停止し、残した volume を把握した。

## 学習メモ

観察結果と設計課題への回答は、この README ではなく**学習ポータルに入力します**（各自の PC の Git 管理外 `learning-portal/.data` にだけ保存され、リポジトリには残りません）。実行していない実験は「省略」と理由を書きます。記録する項目は次のとおりです。

- 実行日・OS・シェル
- 起動結果・migration の状態
- 画面の CRUD・絞り込み
- ブラウザー再読込・API 再起動後のデータ
- down/up 後のデータ
- 公開ポート
- 自動テストの結果
- DB 停止時の live / ready と復旧
- 後片付け・残った volume
- 疑問・未解決事項

## 実装時の検証記録

2026-11-08、Windows PowerShell 5.1 と Docker Desktop の Linux エンジンで確認しました。

| 確認・コマンド | 結果 |
| --- | --- |
| `docker compose -f phases/01-compose/compose.yaml config --quiet` | 成功 |
| `docker compose -f phases/01-compose/compose.yaml up --build -d` | 成功。migration 終了0、API/DB healthy、Web Up |
| `npm --prefix app/web run build` | TypeScript 型チェック・Vite build 成功 |
| `docker compose -f phases/01-compose/compose.yaml --profile test run --build --rm tests` | 専用 PostgreSQL 上で15件成功 |
| `docker compose -f phases/01-compose/compose.yaml exec -T api alembic check` | モデルと migration に差分なし |
| `docker compose -f phases/01-compose/compose.yaml exec -T api python -m pip check` | 依存不整合なし |
| `docker compose -f phases/01-compose/compose.yaml exec -T web nginx -t` | 設定構文正常 |
| 既存 Edge を一時的な Playwright から操作 | 作成・一覧・編集・絞り込み・再読込保持・削除に成功、JavaScript エラーなし |
| 本体 API 再起動 | 検証用タスクを保持 |
| DB 停止・再開 | live 200 / ready 503、再開後は API 再起動なしで ready 200 |
| 通常の down/up | 同じタスクを保持、確認後に検証用タスクだけ削除 |
| 公開ポート | Web の `127.0.0.1:8080` だけ。API/DB のホスト公開なし |
| `.env` | ローカル専用のランダム値で新規作成、Git 除外を確認 |
| `docker compose -f phases/01-compose/compose.yaml --profile test down` | コンテナ・ネットワークを停止・削除。`workboard_postgres-data` が残っていることを確認 |

テストでは Starlette が HTTPX に関する非推奨警告を1件表示しました。テストは成功しており、依存更新時に再確認します。ブラウザー確認用 Playwright は OS の一時フォルダーに導入し、アプリの依存には追加していません。Linux/macOS のホスト操作、volume 削除によるデータ消失実験、AWS・Kubernetes 操作は未実施です。

DRY/KISS の見直しでは、DB 接続設定・セッション生成、タスク検索、入力型、UI の API 呼び出しを共通化しました。migration 内の型・列定義は過去スキーマを固定するため、現在のモデルを参照して自動で変わる共通化を行いません。
