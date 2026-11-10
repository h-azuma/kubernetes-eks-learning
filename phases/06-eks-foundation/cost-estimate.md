# Phase 6: 費用見積もり

**これは見積もりの枠組みです。** 料金は AWS 公式ページで確認できた値だけを記載し、確認できなかった値は「要確認」とします（推測しません）。実行前に [AWS Pricing Calculator](https://calculator.aws/) と各料金ページで要確認の値を埋め、合計をユーザーが承認してから開始してください。**予算通知（AWS Budgets）は課金の停止を保証しません。** 通知はクラスターを止めず、通知までの遅れもあります。止めるのは削除だけです。

- 確認日: 2026-11-10
- region: ap-northeast-1（東京）
- 稼働時間の前提: 1 日 3 時間 × 3 日 = **9 時間**（その間は起動したまま。時間外は `terraform destroy` で削除する前提。削除しなければ 24 時間 × 日数で課金される）
- 台数・構成: Managed Node Group `t3.medium` × 2 台（On-Demand）、2 AZ、NAT Gateway × 1、ECR リポジトリ 2 つ、コントロールプレーンログ無効

## 料金表

| 項目 | 単価 | 数量（9 時間） | 概算 | 出典 |
| --- | --- | --- | --- | --- |
| EKS コントロールプレーン（標準サポート） | $0.10 /クラスター時間 | 1 × 9 | **$0.90** | [EKS Pricing](https://aws.amazon.com/eks/pricing/)（確認済み） |
| EKS 延長サポート（参考） | $0.60 /クラスター時間 | 0（標準サポート中の版のみ使う） | $0 | 同上（確認済み） |
| EC2 `t3.medium` On-Demand | 要確認 /時間（ap-northeast-1） | 2 × 9 | 要確認 | [EC2 On-Demand Pricing](https://aws.amazon.com/ec2/pricing/on-demand/)。ページ本文から東京の値を確認できなかった |
| NAT Gateway 時間料金 | 要確認 /時間（ap-northeast-1） | 1 × 9 | 要確認 | [VPC Pricing](https://aws.amazon.com/vpc/pricing/)。東京の値を確認できなかった（参考: us-east-2 は $0.045 /時間） |
| NAT Gateway データ処理 | 要確認 /GB | イメージ pull と API 通信の量（数 GB 想定、要実測） | 要確認 | 同上。**ECR からのイメージ取得もここで課金される** |
| Public IPv4 アドレス | $0.005 /時間 /アドレス（使用中・未使用とも） | NAT の EIP × 1 × 9 | **$0.045** | VPC Pricing（確認済み。ノードは private なので公開 IPv4 を持たない） |
| EBS gp3（ノードのルート 20 GB） | 要確認 /GB-月 | 2 × 20 GB、削除まで | 要確認 | [EBS Pricing](https://aws.amazon.com/ebs/pricing/) |
| ECR 保管 | 要確認 /GB-月 | 約 1 GB 未満（直近 5 件のみ保持） | 要確認 | [ECR Pricing](https://aws.amazon.com/ecr/pricing/) |
| データ転送（インターネットへ） | 要確認 /GB | 学習では少量 | 要確認 | [EC2 Pricing](https://aws.amazon.com/ec2/pricing/on-demand/) の Data Transfer |
| CloudWatch Logs | 要確認 /GB（取り込み・保管） | コントロールプレーンログ無効なら 0 | 要確認（有効にしない限り $0） | [CloudWatch Pricing](https://aws.amazon.com/cloudwatch/pricing/) |

**確認できた値だけの下限:** $0.90 + $0.045 ≈ **$0.95**（9 時間）。実際の合計は、EC2 と NAT の時間料金・データ処理料金・EBS が加わるため、これより大きくなります。要確認を埋めた合計を、承認前に記録してください。

計算式（要確認の値が分かったら）: 合計 = 0.90 + 0.045 + (t3.medium 単価 × 2 × 9) + (NAT 時間単価 × 9) + (NAT $/GB × 転送 GB) + (EBS $/GB-月 × 40 GB × 日数/30) + ECR + データ転送。

## 費用を増やす要因

- **削除し忘れ:** 24 時間放置すると、EKS だけで 1 日 $2.40。EC2・NAT も加わる。最大のリスク。
- **NAT Gateway:** 時間料金が止まらず、データ処理料金もかかる。AZ ごとに作る（`single_nat_gateway = false`）と時間料金が倍になる。
- **延長サポート:** 標準サポートが終わった版を使い続けると $0.60 /時間になる。`upgrade_policy` は STANDARD。
- **ノード台数・インスタンスタイプの変更、Auto Scaling による増加（最大 3 台）。**
- **コントロールプレーンログの有効化、ECR のイメージ増加。**
- **削除後に残る資産:** EBS、ECR イメージ、ログ、Elastic IP など（`aws-cleanup.md`）。

## 開始前のチェック

- [ ] 要確認の値を公式ページで埋め、合計がユーザーの承認した金額以内。
- [ ] AWS Budgets の通知（メール）を設定した。通知は停止を保証しないことを理解した。
- [ ] 削除の日時を決めた。削除手順（`aws-cleanup.md`）をレビューした。
