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

新しい Phase の ADR は `phases/NN-xxx/decisions/` に提案として置き、この表に追加します。
