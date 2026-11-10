# Phase 7: データ移行・バックアップ・復元の設計

ローカルの PVC 上の DB（Phase 3 の `workboard-phase3`）にあるダミータスクを、RDS に移す設計と手順です。**この手順は AWS では実機検証していません。** 実行前にデータがダミーであること、対象（接続先のクラスターと RDS）を確認します。

## 1. 移行の方針

- **方式:** 論理バックアップ。`pg_dump` で `tasks` テーブルのデータを取り出し、`pg_restore` で RDS に入れる。
- **スキーマ:** migration Job（Alembic、`deploy` が実行）が RDS に作る。移行するのは**データだけ**（`--data-only`）で、`alembic_version` は含めない（二重作成を避ける）。
- **RDS は private** のため、手元の PC から直接接続できない。VPC 内（EKS の Pod）から `pg_restore` する。
- ダンプファイルにはデータが含まれる。Git に入れず、作業後に削除する（`.gitignore` 対象の `*.dump` はないので、置き場所に注意する。リポジトリ外の一時ディレクトリを使う）。
- ダンプ元のクラスター（kind）と移行先（EKS）で、`--context` を明示して取り違えを防ぐ。

## 2. 手順（案）

1. **ダンプ（ローカルの kind 側）。** コンテナ内でファイルに書き出し、`kubectl cp` で取り出す。シェルのパイプ経由だとバイナリが壊れる場合があるため、リダイレクトを使わない。

   ```text
   kubectl --context kind-workboard-phase3 -n workboard exec workboard-postgres-0 -- pg_dump -U workboard -d workboard --format=custom --data-only --table=tasks -f /tmp/tasks.dump
   kubectl --context kind-workboard-phase3 -n workboard cp workboard-postgres-0:/tmp/tasks.dump <リポジトリ外の一時ディレクトリ>/tasks.dump
   ```

2. **RDS 側のスキーマを先に作る。** `deploy` を実行し、migration Job が Complete になっていることを確認する。
3. **一時的な DB クライアント Pod を EKS に作る。** ConfigMap と Secret の名前はハッシュ付きなので、`kubectl -n workboard get configmap,secret` で確認して置き換える。

   ```text
   apiVersion: v1
   kind: Pod
   metadata:
     name: db-client
     namespace: workboard
   spec:
     restartPolicy: Never
     containers:
       - name: client
         image: postgres:17.11-bookworm
         command: [sleep, "3600"]
         envFrom:
           - configMapRef:
               name: <workboard-config-ハッシュ>
           - secretRef:
               name: <workboard-db-ハッシュ>
   ```

   ConfigMap の `POSTGRES_HOST`・`POSTGRES_DB`・`POSTGRES_USER`・`PGSSLMODE` と Secret の `POSTGRES_PASSWORD` が環境変数になる。`pg_restore` には libpq の変数名（`PGHOST`、`PGPASSWORD` 等）が必要なので、コマンドで対応づける（次の手順）。
4. **ダンプを Pod にコピーして復元する。**

   ```text
   kubectl --context <EKS の context> -n workboard cp <一時ディレクトリ>/tasks.dump db-client:/tmp/tasks.dump
   kubectl --context <EKS の context> -n workboard exec db-client -- sh -c 'PGHOST=$POSTGRES_HOST PGUSER=$POSTGRES_USER PGPASSWORD=$POSTGRES_PASSWORD PGDATABASE=$POSTGRES_DB pg_restore --data-only --no-owner --single-transaction /tmp/tasks.dump'
   kubectl --context <EKS の context> -n workboard exec db-client -- sh -c 'PGHOST=$POSTGRES_HOST PGUSER=$POSTGRES_USER PGPASSWORD=$POSTGRES_PASSWORD PGDATABASE=$POSTGRES_DB psql -c "SELECT count(*) FROM tasks"'
   ```

5. **検証。** 件数がローカルと一致するか、API（`/api/v1/tasks`）でタイトルが見えるか。
6. **後片付け。** `kubectl delete pod db-client`、ダンプファイルを削除する。

## 3. 確認する点・リスク

- 既存データがある RDS に流すと、主キー（UUID）の重複で失敗する。`--single-transaction` で途中失敗時に全体を戻す。
- 失敗時はダンプが残っている限り、やり直せる。やり直す前に `TRUNCATE tasks` が必要かを判断する（影響を確認してから）。
- ダンプ内に機密がないこと（ダミーのみ）。
- 文字コード・バージョン差: ローカル `postgres:17.11` と RDS の PostgreSQL 17 でメジャーが同じ。`pg_dump` は移行先と同じかそれより新しいメジャーのクライアントで使う。

## 4. バックアップ・PITR・復元の設計

| 手段 | 内容 | 復元の単位 | 注意 |
| --- | --- | --- | --- |
| RDS 自動バックアップ（保持 7 日） | 日次スナップショットとトランザクションログ。ポイントインタイムリカバリ（PITR）が可能 | 保持期間内の任意の時点（最新復元可能時刻は要確認） | **復元は新しい DB インスタンスを作る**（既存を上書きしない）。新しいエンドポイントになる |
| 手動スナップショット | 任意の時点で取得。自動バックアップと違い、保持期間の経過で消えない | スナップショット時点 | 取得・保管に料金がかかる。削除し忘れが残存資産になる |
| 最終スナップショット | インスタンス削除時に取得（`skip_final_snapshot = false`） | 削除直前 | 保管料金。不要なら手動削除（`aws-cleanup.md`） |
| 論理バックアップ（`pg_dump`） | SQL/カスタム形式のダンプ | テーブル・DB 単位 | 時点復元の代わりにはならない。バージョン間の移行に向く |

**復元の考え方（演習）:**

1. 復元は新しいインスタンスに行う。DB subnet group、セキュリティグループ、パラメータグループ（`rds.force_ssl`）を、元と同じに指定し直す必要があるかを確認する（引き継がれる範囲は要確認）。
2. データを確認してから、ConfigMap の `POSTGRES_HOST` を新しいエンドポイントに変えて `deploy` し直す。
3. Secrets Manager の管理下のパスワードが、復元後のインスタンスでどう扱われるか（要確認。復元後に `db.env` を作り直す必要があるか）。
4. 目標復旧時点（RPO）と復旧時間（RTO）を、学習用の環境ではどこまで求めるか決める。
5. 復元の演習は新しいインスタンスの費用がかかるため、実施は承認した場合のみ。実施後は新旧どちらも削除対象にする。
