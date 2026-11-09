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

1. [構成図](../../docs/architecture/01-compose.md) と [ADR](../../docs/adr/0002-compose-startup-and-persistence.md) を読む。
2. [全体 README の起動手順](../../README.md#workboard-を起動する) に従い `.env` を作成・編集する。
3. 以下のコマンドを **リポジトリ直下** で実行する。
4. 画面・API・ログを観察し、**このファイル末尾の「学習メモ」** を埋める。

## 検証コマンド・期待結果

### 1. 設定と起動を確認する

```text
docker compose -f docker/compose.yaml config --quiet
docker compose -f docker/compose.yaml up --build -d
docker compose -f docker/compose.yaml ps -a
docker compose -f docker/compose.yaml logs --tail=30 migrate api
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

PowerShell:

```powershell
Invoke-RestMethod http://localhost:8080/health/live
Invoke-RestMethod http://localhost:8080/health/ready
Invoke-RestMethod http://localhost:8080/api/v1/tasks
```

Bash:

```bash
curl -i http://localhost:8080/health/live
curl -i http://localhost:8080/health/ready
curl -i http://localhost:8080/api/v1/tasks
```

正常時は両 health が 200、一覧には画面で作成したタスクが出ます。

### 4. 再起動・公開ポート・データ保持を観察する

```text
docker compose -f docker/compose.yaml restart api
docker compose -f docker/compose.yaml ps
docker compose -f docker/compose.yaml port web 80
docker compose -f docker/compose.yaml port api 8000
docker compose -f docker/compose.yaml port db 5432
```

API が healthy に戻ったらブラウザーを再読込します。タスクは残ります。Web の公開先は `127.0.0.1:8080`、API/DB は公開ポートなし（port コマンドの「公開されていない」というエラーは期待どおり）です。

通常の `down` と再起動も試せます:

```text
docker compose -f docker/compose.yaml down
docker compose -f docker/compose.yaml up -d
```

同じタスクが残ることを確認してから、画面の「削除」で検証用タスクを削除してください。

### 5. 自動 API テストを実行する

```text
docker compose -f docker/compose.yaml --profile test run --build --rm tests
```

テストは `workboard_test` という専用 PostgreSQL の tmpfs 上で migration・CRUD・入力エラー・health を確認します。終了コード 0、全テスト成功が期待結果です。学習用 DB のデータを削除しません。

## 故障実験: DB 停止と復旧

学習用環境を利用中のほかの人がいないことを確認してから実行します。

```text
docker compose -f docker/compose.yaml stop db
```

PowerShell なら `curl.exe`、Bash なら `curl` を使って次の URL のステータスを確認します。PowerShell の `curl` は別コマンドの別名になり得るため `curl.exe` を明記します。

```powershell
curl.exe -i http://localhost:8080/health/live
curl.exe -i http://localhost:8080/health/ready
```

期待結果は Liveness 200、Readiness 503。API の DB 接続は数秒で失敗し、画面でのタスク操作も失敗し得ます。API のコンテナが unhealthy になっても、Compose が自動で再起動するとは限りません。

次で復旧し、Readiness が 200 に戻るまで待ちます。

```text
docker compose -f docker/compose.yaml start db
docker compose -f docker/compose.yaml ps
```

API を再起動しなくても接続が回復することと、既存タスクが残ることを観察します。**volume を消す実験は今回は行いません。** 実施する場合は、対象の volume と失われるデータを確認し、削除の明示承認後に別途行います。

## 後片付け

```text
docker compose -f docker/compose.yaml --profile test down
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

この表の `未記録` を、自分が実行した結果に置き換えてください。実装担当の検証記録とは別に、自分の観察を残します。

| 項目 | 観察・結果 |
| --- | --- |
| 実行日・OS・シェル | 2026/11/8・Windows・Powershell |
| 起動結果・migration の状態 | Exited(0) |
| 画面の CRUD・絞り込み | できた |
| ブラウザー再読込・API 再起動後のデータ | 残ることを確認した |
| down/up 後のデータ | volumeが残っている限りはのころうことを確認した |
| 公開ポート | Webサーバのみ外部にポートが解放されており、APIとDBはコンテナ同士にしかポートが解放されていないことを確認した |
| 自動テストの結果 | 15 passed |
| DB 停止時の live / ready と復旧 | liveは200だがreadyは503となることを確認し、DBを復旧させるとreadyも200になることを確認した |
| 後片付け・残った volume | 後片付けを実施した。volumeは残してあるので、再度docker compose upすれば前のデータが残っている状態で始められる |
| 疑問・未解決事項 | なし |

### 設計課題への回答

1. コンテナを分ける理由: 一つのコンテナにまとめてしまうとコンテナ一つがつぶれたときにサービスがまるごとダウンしてしまうが、マイクロサービス化することで障害影響範囲を最小に抑えられる→個別に更新・再起動・管理ができるから
2. 起動順と readiness の違い: service_completed_successfullyに設定することでDBが立ち上がる前にAPIが叩ける状態は実現しなくなるが、サービス稼働中にDBだけダウンしたりした場合においては接続の保証はできない→service_healthy は DB の準備完了を待ち、service_completed_successfully は migration の正常終了を待つ。どちらも起動時の条件で、稼働中の接続は保証しない
3. コンテナ内の localhost の意味: docker-composeで管理されているネットワーク内の5432ポートが開かれているコンテナ？→コンテナ自身のポートに通信する。
4. データが残る理由: volumeという外部保存領域にデータを保管するようにしているから
5. DB 障害と Liveness を分ける理由: APIコンテナが死んでいるのか、DBコンテナが死んでいるのかの判別がつかなくなり、障害の影響範囲の判断が遅れてしまう→APIの障害としてしまうことでAPI毎無駄に再起動しなければならなくなる事態を防ぐ

## 実装時の検証記録

2026-11-08、Windows PowerShell 5.1 と Docker Desktop の Linux エンジンで確認しました。

| 確認・コマンド | 結果 |
| --- | --- |
| `docker compose -f docker/compose.yaml config --quiet` | 成功 |
| `docker compose -f docker/compose.yaml up --build -d` | 成功。migration 終了0、API/DB healthy、Web Up |
| `npm --prefix app/web run build` | TypeScript 型チェック・Vite build 成功 |
| `docker compose -f docker/compose.yaml --profile test run --build --rm tests` | 専用 PostgreSQL 上で15件成功 |
| `docker compose -f docker/compose.yaml exec -T api alembic check` | モデルと migration に差分なし |
| `docker compose -f docker/compose.yaml exec -T api python -m pip check` | 依存不整合なし |
| `docker compose -f docker/compose.yaml exec -T web nginx -t` | 設定構文正常 |
| 既存 Edge を一時的な Playwright から操作 | 作成・一覧・編集・絞り込み・再読込保持・削除に成功、JavaScript エラーなし |
| 本体 API 再起動 | 検証用タスクを保持 |
| DB 停止・再開 | live 200 / ready 503、再開後は API 再起動なしで ready 200 |
| 通常の down/up | 同じタスクを保持、確認後に検証用タスクだけ削除 |
| 公開ポート | Web の `127.0.0.1:8080` だけ。API/DB のホスト公開なし |
| `.env` | ローカル専用のランダム値で新規作成、Git 除外を確認 |
| `docker compose -f docker/compose.yaml --profile test down` | コンテナ・ネットワークを停止・削除。`workboard_postgres-data` が残っていることを確認 |

テストでは Starlette が HTTPX に関する非推奨警告を1件表示しました。テストは成功しており、依存更新時に再確認します。ブラウザー確認用 Playwright は OS の一時フォルダーに導入し、アプリの依存には追加していません。Linux/macOS のホスト操作、volume 削除によるデータ消失実験、AWS・Kubernetes 操作は未実施です。

DRY/KISS の見直しでは、DB 接続設定・セッション生成、タスク検索、入力型、UI の API 呼び出しを共通化しました。migration 内の型・列定義は過去スキーマを固定するため、現在のモデルを参照して自動で変わる共通化を行いません。
