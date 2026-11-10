# ADR-0013: RDS PostgreSQL への切り替え、接続、マスターパスワード、Terraform の分け方

> **読む順番:** この ADR には Lab 07 の設計課題の答えにあたる内容が含まれます。先に [Phase 7 のラボ](../README.md) の設計課題に自分で答えてから読み、自分の考えと比べてください。

## Status

提案（2026-11-10）。Phase 7 に適用。学習者が Lab 07 の設計課題に回答し、内容を確認したうえで「採用」に変更する。AWS では未検証（plan/apply 未実施）。

## Context

Phase 6 の DB は使い捨ての Postgres（emptyDir）だった。Phase 7 では DB を Amazon RDS PostgreSQL に移し、コンテナ内 DB と責任分界を比較する。Web/API は Stateless のままで、データだけを Kubernetes の外で管理する。RDS は private subnet に置き、EKS のノード（Pod）からだけ接続させる。アプリのコード（`app/`）は変更しない。

## Decision

### 1. Terraform は Phase 6 のディレクトリ・state を参照しない

Phase 7 の `terraform/` は独自の state を持ち、既存のクラスターを変数 `cluster_name` と data source（`aws_eks_cluster`、タグで subnet を検索）で見つける。理由は、[ADR-0007](../../../docs/adr/0007-phase-directory-layout.md) の「他 Phase のディレクトリに依存しない」を守りつつ、Phase 7 のためにクラスターを作り直させない（EKS・NAT を 2 回作ると費用が増える）ため。`terraform_remote_state` で Phase 6 の state を読む案は、Phase 6 の state ファイルの置き場所に依存し、依存が見えにくい。代わりに「Phase 6 が `kubernetes.io/role/internal-elb=1` を private subnet に付けている」「ノードがクラスターのセキュリティグループを使う」という約束を前提条件として README に明記する。

### 2. RDS の構成

- エンジンは PostgreSQL 17（メジャーのみ指定し、マイナーは RDS の既定に任せる。ローカルの `postgres:17.11` とメジャーを揃える）。`auto_minor_version_upgrade = true`。
- インスタンスは `db.t4g.micro`、gp3 20 GB、暗号化あり、Single-AZ（変数で Multi-AZ に変更可能）。料金は cost-estimate.md。
- private subnet の DB subnet group に置き、`publicly_accessible = false`。
- セキュリティグループは、EKS のクラスターセキュリティグループ（ノードが使う）からの 5432 だけを許可する。VPC 全体の CIDR や `0.0.0.0/0` には開けない。セキュリティグループ参照にしておくと、ノードが増減・入れ替わっても IP を管理しなくてよい。
- パラメータグループで `rds.force_ssl = 1`（TLS 必須）を明示する。PostgreSQL 15 以降では既定が 1 だが、設定として見えるようにする。
- 自動バックアップは 7 日保持（ポイントインタイムリカバリ、PITR が使える）。削除時は最終スナップショットを取る（`skip_final_snapshot = false`）。削除保護は既定で無効（学習用の削除のしやすさを優先。本番では有効にする）。

### 3. マスターパスワードは RDS 管理（Secrets Manager）にする

`manage_master_user_password = true` にして、RDS がパスワードを生成し Secrets Manager に保管する。Terraform の変数にも state にもパスワードを持たない。`password` 引数を使うと、値が Terraform の state に平文で保存される（state はローカルファイルで暗号化されない）ため。
Kubernetes の Secret には、`scripts/write-db-secret` が Secrets Manager から値を取り出して Git 管理外の `secrets/db.env` に書き、Kustomize の `secretGenerator` が Secret を作る。値は画面に表示しない。

トレードオフ: RDS 管理のパスワードは既定で 7 日ごとに自動で変わる（公式資料で確認）。Kubernetes の Secret は自動では追従しないため、変更後に API の認証が失敗し得る。対応は、`write-db-secret` と `deploy` を再実行して Pod を作り直すこと（手動）。自動追従には External Secrets Operator や Secrets Store CSI Driver が必要で、この Phase の範囲外とする（設計書 §9.1: MVP に導入しない）。マスターユーザーをアプリがそのまま使うのも学習用の簡略化で、本番ではアプリ専用の権限を絞ったユーザーを作る。

### 4. 接続の TLS は `PGSSLMODE=require`

RDS は TLS を必須にしている。API は psycopg 3（libpq）で接続しており、libpq は環境変数 `PGSSLMODE` を読む。ConfigMap に `PGSSLMODE=require` を追加するだけで、`app/` を変更せずに TLS 接続になる（migration Job も同じ ConfigMap を使う）。
`require` は通信を暗号化するが、サーバー証明書は検証しない。中間者攻撃への耐性が必要なら `verify-full` とし、RDS の CA 証明書バンドルをコンテナに配り `PGSSLROOTCERT` で指す。その場合はイメージにバンドルを含めるか ConfigMap/initContainer で配る追加の作業が必要で、学習の焦点から外れるため採用しない。VPC 内の private な経路・暗号化・SG による制限で足りるかを、設計課題として振り返る。

### 5. ローカルのデータは pg_dump / pg_restore で移す

論理バックアップ（`pg_dump`）をローカルの DB から取り、VPC 内の一時的な Pod から `pg_restore` で RDS に入れる。手順と、バックアップ・PITR・復元の設計は [data-migration.md](../data-migration.md)。

## Alternatives

- **Phase 6 の state を `terraform_remote_state` で参照:** 値の受け渡しは簡単。Phase の独立性に反し、state の場所に依存する。
- **Phase 7 の Terraform に Phase 6 の全リソースを含める（1 つに統合）:** 独立性はあるが、Phase 6 の学習範囲を Phase 7 が飲み込む。
- **`password` を変数で渡す:** 最も単純。state とシェル履歴に残るリスクがある（`sensitive` にしても state には平文）。
- **自分で Secrets Manager のシークレットを作る（`random_password` + `aws_secretsmanager_secret`）:** 自動ローテーションを避けられる。ただし state に値が残る。
- **RDS Proxy / IAM データベース認証:** 認証情報の管理を減らせるが、追加リソースと設定が必要。発展課題。
- **Aurora PostgreSQL:** 高可用だが、費用と構成が増える。
- **VPC 全体を許可する SG:** 設定は簡単だが、最小権限に反する。
- **`sslmode=verify-full`:** 安全性は高いが、CA バンドルの配布が必要（上記）。

## Consequences

- DB の運用（パッチ、バックアップ、フェイルオーバー）の一部が AWS に移る。代わりに、RDS・Secrets Manager の費用と、AWS への依存が増える。
- Pod の外に DB があるため、DB の障害・接続不能は API の Readiness（`/health/ready` が 503）に直接影響する（[ADR-0014](0014-aws-load-balancer-controller-and-exposure.md) の health check の判断と関連）。
- 7 日ごとのパスワード変更で、手動で追従しないと API が DB に接続できなくなる。
- 論理バックアップ（pg_dump）はスキーマとデータの移行には適するが、PITR のような時点復元の代わりではない。
- 削除時の最終スナップショットは、削除後も保管料金がかかる。不要になったら手動で削除する。

## Evidence

2026-11-10 に確認した。Terraform は `init -backend=false` と `validate` が成功。AWS には接続していない。

- [Using SSL with a PostgreSQL DB instance](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/PostgreSQL.Concepts.General.SSL.html)（RDS for PostgreSQL は既定で SSL/TLS を使い、`rds.force_ssl` の既定は 15 以降で 1。`sslmode` と `sslrootcert`）
- [Password management with Amazon RDS and AWS Secrets Manager](https://docs.aws.amazon.com/AmazonRDS/latest/UserGuide/rds-secrets-manager.html)（既定で 7 日ごとにローテーション、DB 削除でシークレットも削除、利用で Secrets Manager の料金が発生）
- psycopg 3 は libpq の環境変数（`PGSSLMODE` 等）を読む。API の `database.py` は `sslmode` を指定していないため、環境変数が有効。
