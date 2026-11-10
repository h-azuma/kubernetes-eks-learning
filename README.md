# Kubernetes / Amazon EKS 学習教材

簡易タスク管理アプリ **WorkBoard** を同じ題材として、コンテナから Kubernetes、AWS 上の設計・運用判断までを段階的に学びます。チームで Phase 1 から順に進められるよう、各 Phase の資材（ラボ手順・マニフェスト・スクリプト・構成図・その Phase の設計判断）を `phases/NN-*/` に分けています。各 Phase は他の Phase のディレクトリに依存せず単独で動きます。

## Phase 一覧

| Phase | 題材 | 状態 | 資材 |
| --- | --- | --- | --- |
| 0 | リポジトリ基盤と環境確認 | 実装済み | [phases/00-foundation](phases/00-foundation/README.md) |
| 1 | Docker Compose と WorkBoard MVP | 実装済み | [phases/01-compose](phases/01-compose/README.md) |
| 2 | kind による Kubernetes 最小構成 | 実装済み | [phases/02-kind-basics](phases/02-kind-basics/README.md) |
| 3 | 設定・Secret・永続化 | 実装済み | [phases/03-config-storage](phases/03-config-storage/README.md) |
| 4 | 信頼性・スケーリング | 予習 | [一次設計書](docs/kubernetes-eks-hands-on-design.md) |
| 5 | セキュリティ・障害調査 | 予習 | [一次設計書](docs/kubernetes-eks-hands-on-design.md) |
| 6 | EKS 基盤設計・構築 | 予習 | [一次設計書](docs/kubernetes-eks-hands-on-design.md) |
| 7 | AWS マネージドサービス連携 | 予習 | [一次設計書](docs/kubernetes-eks-hands-on-design.md) |
| 8 | DevOps・可観測性 | 予習 | [一次設計書](docs/kubernetes-eks-hands-on-design.md) |
| 9 | ECS と EKS の採用判断 | 予習 | [一次設計書](docs/kubernetes-eks-hands-on-design.md) |

「予習」は設計書の計画を読む段階で、実環境の手順や資材はまだありません。先の Phase はあらかじめ着手せず、前の Phase を終えてから進めます。

## 学習の進め方

1. まず [設計書](docs/PROJECT_DESIGN.md) と、全体に関わる [技術選定 ADR](docs/adr/0001-application-and-learning-stack.md) を読みます。
2. Phase 0 から順に、各 `phases/NN-*/README.md` の「設計課題」を実装前に自分で考え、手順を実行して観察します。
3. 観察結果と設計課題への回答は、README ではなく **学習ポータルに記録** します。回答は各自の PC の Git 管理外（`learning-portal/.data`）にだけ保存されます。
4. 設計課題に答えた**後で**、その Phase の `decisions/` にある ADR を読み、自分の回答と比べます。全 ADR の所在は [docs/adr/README.md](docs/adr/README.md) にあります。
5. 各 Phase の `architecture.md` に構成図があります。

## 学習ポータルで読む・記録する

教材・構成図・用語・コマンドをブラウザーで読み、メモと設計課題への回答をローカルに保存できます。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File tools/start-learning.ps1
```

**Linux / macOS / WSL (Bash 4 以降):**

```bash
bash tools/start-learning.sh
```

[http://127.0.0.1:8765](http://127.0.0.1:8765) を開いてください。既存の WorkBoard・kind・Pod・port-forward は操作しません。終了は同じターミナルで `Ctrl+C` です。記録は次回も残ります。Codex CLI にログイン済みなら、画面の採点操作時だけ回答・メモをモデルへ送り、補足と回答例を得られます。通常の保存は外部送信しません。保存先・採点・起動の説明は [learning-portal/README.md](learning-portal/README.md) にあります。

## 対応環境

Windows（PowerShell 5.1 以降）と Linux / macOS / WSL（Bash 4 以降。macOS 標準の bash 3.2 は対象外）の両方で使えます。各スクリプトは `.ps1` と同じ場所に同じ処理の `.sh` があり、ラボ README には両方のコマンドを並べています。方針は [ADR-0008](docs/adr/0008-linux-support.md) にあります。Linux では Docker Engine または Docker Desktop が必要です。実機での確認範囲（WSL2 Ubuntu で確認、ネイティブ Linux・macOS は未確認）は ADR-0008 にあります。

## 環境確認

リポジトリ直下で実行します。ツールのバージョン表示だけを行い、インストール、コンテナ起動、クラスター操作、AWS API 呼び出しはしません。詳細と読み方は [Phase 0](phases/00-foundation/README.md) にあります。

```powershell
powershell -NoProfile -File .\tools\preflight.ps1
```

```bash
bash tools/preflight.sh
```

2026-11-08 の実装時に Windows PowerShell 5.1 と Git Bash で、2026-11-10 に WSL2 Ubuntu で preflight を確認しました。観測結果と未検証事項は [Phase 0 の実装時検証記録](phases/00-foundation/README.md#実装時の検証記録) にあります。

## リポジトリ構成

| ディレクトリ | 内容 |
| --- | --- |
| `app/` | 全 Phase で共通の WorkBoard（API・Web） |
| `tools/` | 全 Phase 共通のスクリプト（preflight、kind 導入、学習ポータル起動、kind 共通処理）。PowerShell 版（`.ps1`）と Bash 版（`.sh`）を並べて置く |
| `docs/` | 一次設計書と、全体に関わる ADR（`docs/adr/`） |
| `phases/NN-*/` | Phase ごとのラボ手順・マニフェスト・スクリプト・構成図・ADR（`decisions/`） |
| `learning-portal/` | 学習用 Web アプリ |

`.tools/`（kind 実行ファイル）と `.kube/`（学習専用 kubeconfig）は各自の PC に作られる Git 管理外のディレクトリです。構成変更の理由は [ADR-0007](docs/adr/0007-phase-directory-layout.md) にあります。

## 注意

- Phase 2 の DB はダミーデータ専用で、DB Pod を削除するとデータが消えます。Phase 3 の保存先は PVC ですが、kind クラスターやその PVC を削除するとデータは消えます（バックアップではありません）。クラスターや DB を削除する前に対象と影響を確認してください。
- `down -v` や `kind delete cluster` などデータを消す操作は、対象と影響を確認し、明示的に実施を決めた場合だけ行います。
- AWS の有料リソースを作成する際は、対象・費用・公開範囲・削除手順を確認し、明示承認を得てから実行します。
- 認証情報や実パスワードは Git に含めません（`.env`、`db.env` などは Git 管理外です）。
