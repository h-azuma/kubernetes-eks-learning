# ADR-0002: Compose の起動依存・永続化・テスト分離

## Status

採用（2026-11-08）。Phase 1 に適用。

## Context

コンテナの起動とアプリの準備完了は異なる。学習用データを残しながら migration と API テストを繰り返し、DB 障害時の API の挙動も観察したい。

## Decision

- PostgreSQL の health 成功 → 一回実行の Alembic migration 成功 → API Readiness 成功 → Web の順に起動する。
- API は同期 SQLAlchemy と Psycopg を使う。小規模 CRUD に不要な非同期レイヤーや repository 層を追加しない。
- Liveness と DB 接続を分離する。DB 接続の回復は `pool_pre_ping` で古い接続を除き、書き込みの自動再試行はしない。
- DB は名前付き volume。API テストは別サービス・別 DB・tmpfs に分離する。
- Web のみループバックへ公開し、Nginx から API を呼ぶ。API の IP は Docker DNS で再解決する。
- 依存の直接バージョンは `pyproject.toml`、解決した制約は `requirements.lock`、npm は `package-lock.json` に固定する。Docker のベースは明示的なパッチタグを使う。

## Alternatives

- API 起動ごとの migration: ファイルは減るが、複数 API で実行が競合し、初期化とリクエスト処理の責務が混ざる。
- 固定秒数の sleep: 環境によって不足・待ちすぎになる。
- SQLite によるテスト: 速いが PostgreSQL の型・接続・migration の問題を見落とす。
- API/DB のホスト公開: 診断しやすいが、不要な公開とポート衝突を増やす。

## Consequences

通常稼働は Web・API・DB の3サービスで、migration は終了コード0で停止する。テスト時だけ専用DBが増える。初回のイメージ取得は必要だが、追加のホスト用 Python 環境を作らずコンテナで検証できる。DB 障害中の CRUD は失敗し得るため、画面でエラーを確認する。

パッチタグは読みやすい一方、レジストリ側の再ビルドで内容が変わり得る。完全なバイト単位の固定が必要になった段階で digest 固定を検討する。

## 依存更新方法

Python の直接依存は `app/api/pyproject.toml` だけを編集する。新しい空の仮想環境で `python -m pip install -e 'app/api[test]'` を実行し、`python -m pip freeze --exclude workboard-api` の結果を `app/api/requirements.lock` に保存する。lock は手で二重管理せず、生成結果として扱う。Windows と Linux の差はコンテナのテストと `pip check` で確認する。

npm は `npm --prefix app/web install --save-dev --save-exact vite@バージョン typescript@バージョン` で `package.json` と lock を同時更新する。通常の再現インストールは `npm ci`。更新後は UI ビルドと Compose の API テストを再実行する。

## Evidence

2026-11-08 に公式資料、PyPI JSON、npm registry、Docker Hub の公式イメージタグを確認し、Python 3.11 に適合する公開版を選択した。ホスト Node.js 24.13.1 は Vite 8 の Node 要件（20.19+ または 22.12+）を満たす。

| 対象 | 固定バージョン |
| --- | --- |
| Python / PostgreSQL | 3.11.18-slim-bookworm / 17.11-bookworm |
| Node / Nginx | 24.22.2-bookworm-slim / 1.30.6-alpine |
| FastAPI / Uvicorn | 0.162.2 / 0.54.0 |
| SQLAlchemy / Alembic / Psycopg | 2.1.8 / 1.20.1 / 3.3.8 |
| Pydantic / pytest / HTTPX | 2.14.3 / 9.2.0 / 0.28.1 |
| Vite / TypeScript | 8.3.6 / 7.0.2 |

- [Compose の起動順](https://docs.docker.com/compose/how-tos/startup-order/)
- [FastAPI のコンテナ構築](https://fastapi.tiangolo.com/deployment/docker/)
- [SQLAlchemy 2.1](https://docs.sqlalchemy.org/en/21/intro.html)
- [Psycopg の対応 Python・PostgreSQL](https://www.psycopg.org/psycopg3/docs/basic/install.html)
- [PostgreSQL のサポート方針](https://www.postgresql.org/support/versioning/)
- [Vite の前提条件](https://vite.dev/guide/)
- [Nginx upstream resolve](https://nginx.org/en/docs/http/ngx_http_upstream_module.html#resolve)
