# Phase 7: 費用見積もり

**これは見積もりの枠組みです。** 料金は AWS 公式ページで確認できた値だけを記載し、確認できなかった値は「要確認」とします（推測しません）。Phase 7 は Phase 6 の見積もり（`phases/06-eks-foundation/cost-estimate.md`）（EKS、EC2、NAT など）に、**RDS、ALB、Secrets Manager、スナップショット** が加わります。実行前に要確認の値を [AWS Pricing Calculator](https://calculator.aws/) と各料金ページで埋め、合計を承認してから開始してください。**予算通知（AWS Budgets）は課金の停止を保証しません。**

- 確認日: 2026-11-10
- region: ap-northeast-1（東京）
- 稼働時間の前提: 1 日 3 時間 × 3 日 = **9 時間**（Phase 6 と同じ時間にクラスターと RDS を稼働）。時間外は Phase 7 の資産（ALB、RDS）を削除する前提。
- 構成: Phase 6 の構成（`t3.medium` × 2、NAT × 1、2 AZ）に、RDS PostgreSQL 17 `db.t4g.micro` Single-AZ（gp3 20 GB、暗号化、自動バックアップ 7 日）、ALB × 1（2 AZ）、Secrets Manager のシークレット × 1（RDS 管理）

## 追加される項目

| 項目 | 単価 | 数量（9 時間） | 概算 | 出典 |
| --- | --- | --- | --- | --- |
| Phase 6 分（EKS、EC2、NAT、EIP、EBS、ECR） | Phase 6 の見積もり（`phases/06-eks-foundation/cost-estimate.md`） | 9 時間 | 確認できた下限 約 $0.95 + 要確認 | 同左 |
| RDS `db.t4g.micro` PostgreSQL Single-AZ | 要確認 /時間（ap-northeast-1） | 1 × 9 | 要確認 | [RDS for PostgreSQL Pricing](https://aws.amazon.com/rds/postgresql/pricing/) |
| RDS Multi-AZ にした場合 | 要確認（Single-AZ のおよそ 2 倍。値は要確認） | — | 要確認 | 同上 |
| RDS ストレージ gp3 20 GB | 要確認 /GB-月 | 20 GB × 日数/30 | 要確認 | 同上 |
| RDS バックアップストレージ | 要確認 /GB-月（DB サイズまでの無料枠の条件は要確認） | 少量 | 要確認 | 同上 |
| RDS スナップショット（最終・手動） | 要確認 /GB-月 | 削除後も残る | 要確認 | 同上 |
| ALB 時間料金 | 要確認 /時間（ap-northeast-1） | 1 × 9 | 要確認 | [ELB Pricing](https://aws.amazon.com/elasticloadbalancing/pricing/) |
| ALB LCU 使用料 | 要確認 /LCU-時間 | 少量（検証トラフィックのみ） | 要確認 | 同上 |
| ALB の Public IPv4 アドレス | $0.005 /時間 /アドレス | 2 AZ × 9 時間（アドレス数は ALB の構成による。要確認） | 約 $0.09（2 個の場合） | [VPC Pricing](https://aws.amazon.com/vpc/pricing/)（確認済みの単価） |
| Secrets Manager（RDS 管理シークレット） | 要確認 /シークレット/月 + API 呼び出し | 1 | 要確認 | [Secrets Manager Pricing](https://aws.amazon.com/secrets-manager/pricing/)。RDS 側のドキュメントも「利用で料金が発生する」と記載 |
| データ転送 | 要確認 /GB | 少量 | 要確認 | EC2 Pricing の Data Transfer |
| CloudWatch Logs / RDS ログ | 要確認 | RDS の既定ではログを CloudWatch へ送らない設定（有効化しない限り $0） | 要確認 | CloudWatch Pricing |

**確認できた値だけの下限（Phase 7 追加分）:** ALB の Public IPv4 約 $0.09。Phase 6 の下限 $0.95 と合わせても約 $1.04 にすぎず、**RDS・ALB・EC2・NAT の時間料金が大半を占めます。** 要確認の値を埋めた合計を、承認前に記録してください。

## 費用を増やす要因

- **削除し忘れ:** RDS、ALB、NAT、EKS は止まらずに課金される。
- **Multi-AZ、インスタンスクラスの変更、ストレージ増加。**
- **スナップショットの残存:** RDS 削除時の最終スナップショットは、削除後も保管料金がかかる。
- **Secrets Manager:** RDS 削除でシークレットも削除されるが、削除までの猶予期間などの扱いは要確認（`aws-cleanup.md`）。
- **ALB を Ingress の削除なしで放置。**
- **自動バックアップの保持日数の増加。**

## 開始前のチェック

- [ ] Phase 6 の見積もりと合算した合計が、承認した金額以内。
- [ ] 予算通知を設定した（停止を保証しない）。
- [ ] 削除の日時を決めた。削除の順序（Ingress → Helm → RDS → Terraform）を [aws-cleanup.md](aws-cleanup.md) で確認した。
