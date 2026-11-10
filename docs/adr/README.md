# ADR 一覧

設計判断の採用理由・代替案・影響・根拠の記録です。番号は全体で一意で、移動しても変わりません。

> **読む順番:** Phase 別の ADR には、その Phase の設計課題の答えにあたる内容が含まれます。**先にラボの設計課題に自分で答えてから**読み、自分の考えと比べてください。

## 全体に関わる ADR（このディレクトリ）

| ADR | 内容 | 状態 |
| --- | --- | --- |
| [0001](0001-application-and-learning-stack.md) | WorkBoard と段階的な学習スタック | 採用 |
| [0004](0004-learning-portal-react.md) | 学習ポータルの画面を React へ移行する | 採用 |
| [0005](0005-kubernetes-ecosystem-tools.md) | Kubernetes エコシステムのツールを段階的に導入する | 採用 |
| [0007](0007-phase-directory-layout.md) | Phase ごとのディレクトリ構成 | 採用 |
| [0008](0008-linux-support.md) | Linux（Bash）対応は PowerShell 版と並べた Bash 版で行う | 採用 |

## Phase 別の ADR（課題に答えた後に読む）

| ADR | Phase | 内容 | 状態 |
| --- | --- | --- | --- |
| [0002](../../phases/01-compose/decisions/0002-compose-startup-and-persistence.md) | 1 | Compose の起動依存・永続化・テスト分離 | 採用 |
| [0003](../../phases/02-kind-basics/decisions/0003-kind-minimal-workloads.md) | 2 | kind の最小ワークロードと一時 DB | 採用 |
| [0006](../../phases/03-config-storage/decisions/0006-kind-configuration-and-persistence.md) | 3 | kind での設定分離と DB 永続化 | 提案 |
| [0009](../../phases/04-reliability-scaling/decisions/0009-reliability-and-scaling.md) | 4 | kind での可用性、更新、スケーリングの構成 | 提案 |
| [0010](../../phases/05-security-and-failure/decisions/0010-security-and-troubleshooting.md) | 5 | kind でのセキュリティ設定と障害調査の構成 | 提案 |
| [0011](../../phases/06-eks-foundation/decisions/0011-eks-foundation.md) | 6 | EKS 基盤（標準 EKS + Managed Node Group、region、endpoint、NAT、Terraform） | 提案 |
| [0012](../../phases/06-eks-foundation/decisions/0012-kustomize-eks-and-throwaway-db.md) | 6 | EKS の最初のワークロード（使い捨て DB、ECR、port-forward） | 提案 |
| [0013](../../phases/07-aws-integration/decisions/0013-rds-connection-and-secret.md) | 7 | RDS への切り替え、接続、マスターパスワード、Terraform の分け方 | 提案 |
| [0014](../../phases/07-aws-integration/decisions/0014-aws-load-balancer-controller-and-exposure.md) | 7 | AWS Load Balancer Controller、Helm、Pod Identity、公開範囲 | 提案 |
| [0015](../../phases/08-devops-observability/decisions/0015-delivery-and-gitops.md) | 8 | CI/CD、GitOps、Secret、監視の構成 | 提案 |
| [0016](../../phases/08-devops-observability/decisions/0016-helm-vs-kustomize-for-workboard.md) | 8 | WorkBoard のマニフェストを Helm chart にするかの比較 | 提案 |
| [0017](../../phases/09-architecture-review/decisions/0017-ecs-vs-eks-evaluation-method.md) | 9 | ECS と EKS の比較の進め方と評価の基準 | 提案 |

新しい Phase の ADR は `phases/NN-xxx/decisions/` に提案として置き、この表に追加します。
