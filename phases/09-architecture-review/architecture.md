# 構成図の比較: WorkBoard を ECS と EKS で動かす

同じ WorkBoard（Web: Nginx、API: FastAPI、DB: PostgreSQL）を AWS で動かす場合の構成を並べた概念図です。実際に作る構成ではなく、比較のための出発点です。図に無い要素（VPC 設計、NAT、WAF、バックアップ等）は、比較で自分で足してください。DB は Phase 7 と同じく Amazon RDS に置く前提で揃えています（どちらの案でも DB の位置は同じなので、差は出ません）。

## 1. ECS 案（Fargate 起動タイプを例に）

```text
Browser (アクセス制限あり)
   |
   v
ALB (ECS サービスのロードバランサー設定で Target Group に接続)
   |
   v
ECS Cluster
  Service web  -> Task (Task Definition: Nginx)
  Service api  -> Task (Task Definition: FastAPI)  --+
                                                      |
                                                      v
                                              Amazon RDS PostgreSQL

ECR   : イメージ保管 (Task Definition から参照)
IAM   : タスク実行ロール (イメージ取得・ログ出力) / タスクロール (アプリの AWS 権限)
ログ   : awslogs ドライバーで CloudWatch Logs へ
VPC   : Public subnets (ALB) / Private subnets (Task, RDS)
```

EC2 起動タイプにする場合は、Task が動く EC2 インスタンス（容量プロバイダー経由）の OS・パッチ・容量管理が追加で自分の責任になります。

## 2. EKS 案（Phase 6〜7 の構成）

```text
Browser (アクセス制限あり)
   |
   v
ALB (AWS Load Balancer Controller が Ingress から作成)
   |
   v
EKS Cluster
  Service web -> Deployment web (Nginx Pod)
  Service api -> Deployment api (FastAPI Pod)  --+
                                                 |
                                                 v
                                         Amazon RDS PostgreSQL

ECR   : イメージ保管 (Pod の image から参照)
IAM   : クラスター/ノードのロール、access entries、Pod Identity (ServiceAccount と IAM ロールの関連づけ)
ログ   : 収集用のエージェントやアドオンを別途導入して CloudWatch Logs 等へ
VPC   : Public subnets (ALB) / Private subnets (nodes, RDS)
ノード : Managed Node Groups (または Auto Mode / Fargate)
```

## 3. 要素の対応表

| 役割 | ECS 案 | EKS 案 |
| --- | --- | --- |
| 実行の単位 | Task | Pod |
| 望ましい個数の維持・更新 | Service | Deployment（ReplicaSet） |
| 実行内容の定義 | Task Definition | Pod テンプレート（マニフェスト） |
| 外部入口の ALB | サービスのロードバランサー設定 | Ingress と AWS Load Balancer Controller |
| 内部の名前解決 | サービス検出の機能 | Service と DNS |
| コンテナへの IAM 権限 | タスクロール | Pod Identity（または他の方式） |
| 実行基盤の権限 | タスク実行ロール | ノードロール、クラスターロール |
| 計算資源 | Fargate または EC2（容量プロバイダー） | Managed Node Groups、Auto Mode、Fargate など |
| 設定・機密値 | Task Definition の環境変数、Secrets 連携 | ConfigMap / Secret |
| 構成の記述 | Task Definition / Terraform 等 | マニフェスト / Kustomize / Helm / Terraform 等 |
| ログ | awslogs ドライバー等 | 収集用エージェントの導入が必要 |
| イメージ | ECR | ECR |
| DB | RDS | RDS |

この表はあくまで対応の目安です。名前が似ていても機能の範囲は同じではないため、各行の違いを公式資料で確認し、[比較レポート](ecs-vs-eks.md)の根拠に結びつけてください。「EKS の方が高機能」「ECS の方が簡単」といった評価はここでは書きません。それは比較軸ごとに自分で判断する内容です。

## 4. 図から読み取る観点

- 両案で共通のもの（ALB、RDS、ECR、VPC）と、案によって増減するもの（コントロールプレーンの料金体系、ノード運用、アドオン）はどれか。
- 同じ「ロール」でも、権限を渡す相手（実行基盤かアプリか）はどこで分かれるか。
- 将来、別チームのサービスが増えたとき、図のどの部分が共有され、どの部分がサービスごとに増えるか。
