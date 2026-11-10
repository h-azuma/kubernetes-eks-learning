# Kubernetes / Amazon EKS 学習教材

簡易タスク管理アプリ **WorkBoard** を同じ題材として、コンテナから Kubernetes、AWS 上の設計・運用判断までを段階的に学びます。チームで Phase 1 から順に進められるよう、各 Phase の資材（ラボ手順・マニフェスト・スクリプト・構成図・その Phase の設計判断）を `phases/NN-*/` に分けています。各 Phase は他の Phase のディレクトリに依存せず単独で動きます。

## Phase 一覧

| Phase | 題材 | 状態 | 資材 |
| --- | --- | --- | --- |
| 0 | リポジトリ基盤と環境確認 | 実装済み | [phases/00-foundation](phases/00-foundation/README.md) |
| 1 | Docker Compose と WorkBoard MVP | 実装済み | [phases/01-compose](phases/01-compose/README.md) |
| 2 | kind による Kubernetes 最小構成 | 実装済み | [phases/02-kind-basics](phases/02-kind-basics/README.md) |
| 3 | 設定・Secret・永続化 | 実装済み | [phases/03-config-storage](phases/03-config-storage/README.md) |
| 4 | 可用性・更新・スケーリング（Probe・HPA・PDB・配置制御） | 実装済み | [phases/04-reliability-scaling](phases/04-reliability-scaling/README.md) |
| 5 | セキュリティ・障害調査（RBAC・NetworkPolicy・PSS・Runbook） | 実装済み | [phases/05-security-and-failure](phases/05-security-and-failure/README.md) |
| 6 | EKS 基盤（Terraform・VPC・Managed Node Group・ECR） | 実装済み（AWS 上は未検証） | [phases/06-eks-foundation](phases/06-eks-foundation/README.md) |
| 7 | AWS マネージドサービス連携（RDS・ALB・Pod Identity・Helm） | 実装済み（AWS 上は未検証） | [phases/07-aws-integration](phases/07-aws-integration/README.md) |
| 8 | DevOps・可観測性（CI/CD・Argo CD・Prometheus・SLO） | 実装済み | [phases/08-devops-observability](phases/08-devops-observability/README.md) |
| 9 | ECS と EKS の採用判断 | 実装済み | [phases/09-architecture-review](phases/09-architecture-review/README.md) |

Phase 1〜5 と 8 はローカル（Docker Compose / kind）だけで完結し、AWS 費用はかかりません。kind の各 Phase は専用のクラスターとポートを使うため、他の Phase の環境を壊しません（`workboard-lab`/8080、`workboard-phase3`/8081、`workboard-phase4`/8082、`workboard-phase5`/8083、`workboard-phase8`/8084）。

Phase 6・7 は **AWS の有料リソースを作ります**。Terraform・マニフェスト・スクリプトは静的検証（`terraform validate`、`helm template`、`kubectl kustomize`）まで済んでいますが、AWS 上での動作は未検証です。各 README の開始条件（明示的な承認、見積もり、予算通知、削除手順の確認）を満たしてから自分で実行してください。Phase 8 の CD ワークフローも、AWS 側の準備をするまでは動きません。

前の Phase を終えてから次へ進みます。

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

## 必要なソフトウェア・ツール

自分の PC に導入するものです。版はこの教材で確認した条件で、各 Phase の README の「前提条件」が正本です。Git・Docker・Docker Compose・kubectl・kind・Python・Node.js・AWS CLI・Terraform の導入の有無と版は、`tools/preflight.ps1`（Bash は `tools/preflight.sh`）で確認できます（参照のみで、何もインストールしません）。Helm・k9s・採点用の CLI は preflight の対象外です。

| ソフトウェア | 版の条件 | 使う Phase | 用途・備考 |
| --- | --- | --- | --- |
| Git | 指定なし | すべて | clone、Phase 8 では自分の fork への push |
| PowerShell または Bash | PowerShell 5.1 以降 / Bash 4 以降（macOS 標準の bash 3.2 は不可） | すべて | スクリプトの実行。どちらか一方でよい |
| Python | 3.11 以降 | 学習ポータル、7 | 学習ポータルの教材生成とサーバー、Phase 7 の Bash 版 `write-db-secret.sh`（`python3`）。WorkBoard の API とテストはコンテナ内で動くので不要 |
| Node.js / npm | Node.js 20.19 以降の 20 系、または 22.12 以降 | 学習ポータル | 学習ポータルの画面のビルド（初回の `npm` 導入にネットワークが必要）。WorkBoard の Web はコンテナ内でビルドするので不要 |
| Docker / Docker Compose | Linux コンテナが動くこと、Compose v2（`docker compose`）（Windows / macOS は Docker Desktop、Linux は Docker Engine または Docker Desktop。WSL は Docker Desktop の WSL 統合） | 1〜8 | Compose、イメージのビルド、kind のノード。Phase 4・8 は 3 ノードの kind のため、Docker のメモリに 6 GiB 程度の空きを推奨 |
| kubectl | 1.34〜1.36 | 2〜8 | Kubernetes の操作（Kustomize の `kubectl kustomize` を含む）。Docker Desktop 同梱のものでもよい |
| kind | v0.33.0 | 2〜5、8 | ローカルの Kubernetes。`tools/kind-install.ps1`（Bash は `tools/kind-install.sh`）が Git 管理外の `.tools/` に導入する |
| curl | 指定なし | 1〜8 | 動作確認。Windows は標準の `curl.exe` |
| Terraform | 1.17.x | 6〜8 | AWS 環境の定義。`plan` / `apply` は AWS の承認後だけ |
| AWS CLI | v2 | 6〜8 | 認証、ECR へのログイン、kubeconfig の更新、残った資産の点検 |
| Helm | 4.x（4.3.1 で確認） | 7 | AWS Load Balancer Controller の導入と `helm template` |
| k9s | 指定なし（任意） | 5 | Runbook を `kubectl` で終えた後の観察用。導入しなくても Lab は完了できる |
| Codex CLI / Claude Code CLI | 指定なし（任意） | 学習ポータル | 「AI と理解を振り返る」の採点。ログイン済みのどちらかがあれば使える。採点モデルの既定は `gpt-6-luna` / `claude-sonnet-5-5`（変更方法は [learning-portal/README.md](learning-portal/README.md)） |

アカウントが必要なもの:

- **AWS アカウント（Phase 6〜8）:** 有料リソースを作ります。各 Phase の開始条件を満たしてから使います。
- **GitHub アカウント（Phase 8）:** Argo CD は自分の fork を同期します。CI/CD を試す場合も自分の fork で行います。

Calico、metrics-server、Argo CD、Prometheus、AWS Load Balancer Controller は、構築スクリプトや Helm がクラスターの中に入れるもので、PC への導入は不要です（版は各 Phase の README と ADR に固定してあります）。

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
| `.github/workflows/` | CI（テスト・ビルド・マニフェストと Terraform の検証）と、手動承認制の CD（Phase 8） |

`.tools/`（kind 実行ファイル）と `.kube/`（学習専用 kubeconfig）は各自の PC に作られる Git 管理外のディレクトリです。構成変更の理由は [ADR-0007](docs/adr/0007-phase-directory-layout.md) にあります。

## 注意

- Phase 2 の DB はダミーデータ専用で、DB Pod を削除するとデータが消えます。Phase 3 の保存先は PVC ですが、kind クラスターやその PVC を削除するとデータは消えます（バックアップではありません）。クラスターや DB を削除する前に対象と影響を確認してください。
- `down -v` や `kind delete cluster` などデータを消す操作は、対象と影響を確認し、明示的に実施を決めた場合だけ行います。
- AWS の有料リソースを作成する際は、対象・費用・公開範囲・削除手順を確認し、明示承認を得てから実行します。
- 認証情報や実パスワードは Git に含めません（`.env`、`db.env` などは Git 管理外です）。
