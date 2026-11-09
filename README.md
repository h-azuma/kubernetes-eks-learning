# Kubernetes / Amazon EKS 学習教材

簡易タスク管理アプリ **WorkBoard** を同じ題材として、コンテナから Kubernetes、AWS 上の設計・運用判断まで段階的に学びます。

現在は **Phase 2（kind と Kubernetes の基本）** です。Phase 1 と同じ WorkBoard を Kubernetes に配置し、Pod・Deployment・Service と自動復旧を学びます。Compose の構成も引き続き利用できます。

## 学習ポータルで読む・記録する

教材・構成図・用語・コマンドをブラウザーで読み、メモと設計課題への回答をローカル保存できます。

```powershell
powershell -NoProfile -File scripts/start-learning.ps1
```

[http://127.0.0.1:8765](http://127.0.0.1:8765) を開いてください。既存の WorkBoard・kind・Pod・port-forward は操作しません。終了はこの PowerShell で `Ctrl+C`。記録は次回も残ります。

Codex CLI にログイン済みなら、画面の採点操作時だけ回答・メモをモデルへ送り、補足と回答例を得られます。通常の保存は外部送信しません。[保存先・採点・起動の説明](learning-portal/README.md) に詳細があります。

2026-11-08 の実装時に Windows PowerShell 5.1 と Git Bash で preflight を確認しました。観測結果と未検証事項は [Lab 00 の実装時検証記録](labs/00-repository-foundation/README.md#実装時の検証記録) にあります。

## 学習の順序

| Phase | 題材 |
| --- | --- |
| 0 | リポジトリ基盤と環境確認 |
| 1 | Docker Compose と WorkBoard MVP |
| 2 | kind による Kubernetes 最小構成 |
| 3 | 設定・Secret・永続化 |
| 4 | 信頼性・スケーリング |
| 5 | セキュリティ・障害調査 |
| 6 | EKS 基盤設計・構築 |
| 7 | AWS マネージドサービス連携 |
| 8 | DevOps・可観測性 |
| 9 | ECS と EKS の採用判断 |

まず [設計書](docs/PROJECT_DESIGN.md)、[Lab 00](labs/00-repository-foundation/README.md)、[技術選定 ADR](docs/adr/0001-application-and-learning-stack.md) を読みます。

## Phase 2: kind 上で WorkBoard を動かす

今回の作業環境では kind と専用クラスターを構築済みです。まず現在の PowerShell で以下を実行し、Node が Ready であることを確認してください。

```powershell
. .\scripts\kind-env.ps1
kubectl --context kind-workboard-lab get nodes
```

その後は [Lab 02](labs/02-kubernetes-basics/README.md) の「2. 現在の PowerShell で対象を選び、状態を観察する」から進めます。観察結果・問いへの回答は、同じファイル末尾の **「学習メモ」** に記入します。

新しく clone した環境では、Docker Desktop の Linux コンテナエンジンと kubectl 1.34〜1.36 を用意し、リポジトリ直下で次を実行します。

```powershell
powershell -NoProfile -File scripts/kind-install.ps1
powershell -NoProfile -File scripts/kind-up.ps1
. .\scripts\kind-env.ps1
kubectl --context kind-workboard-lab -n workboard port-forward --address 127.0.0.1 svc/workboard-web 8080:80
```

最後のコマンドを実行中のまま [http://localhost:8080](http://localhost:8080) を開きます。8080 番を Compose が使っている場合は、Compose の手順で停止してから実行してください。

kind v0.33.0 は SHA-256 検証後に `.tools` へ配置し、Kubernetes v1.35.8 を使います。標準の kubeconfig やシステム PATH は変更しません。初回はノードイメージを取得し、ノードから公式レジストリへ接続して PostgreSQL を取得するためネットワーク接続が必要です。Linux/macOS/WSL の手動手順は Lab 02 にあります。

**Phase 2 の DB はダミーデータ専用で、DB Pod を削除するとデータが消えます。** Phase 1 の Compose volume と別です。クラスターや DB を削除する前に対象と影響を確認してください。構成と判断は [構成図](docs/architecture/02-kind.md)・[ADR-0003](docs/adr/0003-kind-minimal-workloads.md) に記載しています。

<a id="workboard-を起動する"></a>

## Phase 1: Compose 上で WorkBoard を起動する

Docker Desktop の Linux コンテナエンジンを起動し、リポジトリ直下で操作します。Docker エンジンは `docker info` で確認できます。kind・Terraform は今回不要です。

初回だけ `.env.example` を `.env` にコピーします。すでに `.env` がある場合は上書きせず、そのファイルを使ってください。

Windows PowerShell:

```powershell
if (-not (Test-Path .env)) { Copy-Item .env.example .env }
```

Linux / macOS / WSL の Bash:

```bash
if [ ! -f .env ]; then cp .env.example .env; fi
```

`.env` をエディターで開き、`POSTGRES_PASSWORD` の例をローカル専用の値に変更します。このファイルは Git の対象外です。DB 初期化後に値を変更しても既存 DB のパスワードは自動で変わりません。

共通の起動コマンド:

```text
docker compose -f docker/compose.yaml up --build -d
docker compose -f docker/compose.yaml ps -a
```

`migrate` は正常終了（Exited 0）、`api` と `db` は healthy、`web` は Up が期待結果です。初回はイメージの取得・ビルドに時間がかかります。[WorkBoard](http://localhost:8080) を開くとタスクを作成・編集・削除できます。[API ドキュメント](http://localhost:8080/docs) も利用できます。

次は [Lab 01](labs/01-compose-basics/README.md) を上から進めてください。観察結果と問いへの回答は、同ファイル末尾の **「学習メモ」** に直接記入します。[構成図](docs/architecture/01-compose.md) と [起動・永続化の ADR](docs/adr/0002-compose-startup-and-persistence.md) に採用理由を記載しています。

## テストと停止

専用の一時 DB で API テストを実行します。学習用タスクには触れません。

```text
docker compose -f docker/compose.yaml --profile test run --build --rm tests
```

ホスト側の UI 型チェック・ビルドを行う場合:

```text
npm --prefix app/web ci
npm --prefix app/web run build
```

使い終わったら、次でコンテナとネットワークを片付けます。名前付き volume にデータは残ります。

```text
docker compose -f docker/compose.yaml --profile test down
```

`down -v` はデータを消すため、通常の後片付けには使いません。volume の削除実験は対象・影響を確認し、明示的に実施を決めた場合だけ行います。

## 環境確認

リポジトリ直下で実行してください。スクリプトはローカルのバージョン表示だけを行います。ツールのインストール、コンテナ起動、クラスター操作、AWS API 呼び出しは行いません。

Windows PowerShell 5.1 以降:

```powershell
powershell -NoProfile -File .\scripts\preflight.ps1
```

実行ポリシーで拒否される場合は組織のルールを確認してください。PowerShell 7 を利用する場合は `powershell` を `pwsh` に置き換えます。

Linux / macOS、または WSL 内の Bash:

```bash
bash scripts/preflight.sh
```

Windows では PowerShell から Windows 側のツールを調べる経路と、WSL2 のシェルから Linux 側のツールを調べる経路があります。結果はそれぞれの PATH に依存します。Docker Desktop と WSL2 連携は Phase 1 の候補ですが、バージョン表示の成功だけでは Docker エンジンの稼働や WSL 連携を確認できません。WSL のディストリビューション・世代・Docker Desktop 連携は **要確認** です。

結果の「利用可能」はバージョン取得成功、「未導入」はコマンド未検出、「確認失敗」は検出したコマンドの実行失敗を意味します。Git が利用できなければ終了コードは 1、それ以外は 0 です。他のツールが未導入でも Phase 0 は進められます。バージョンの互換性とエンジンの稼働は各フェーズ開始時に別途確認します。

## 作業と後片付け

各ラボで「問い → 実装 → 観察 → 設計判断 → 完了条件」を記録します。未実施の検証は未実施と書きます。Compose は上の `down`、kind は [Lab 02 の後片付け](labs/02-kubernetes-basics/README.md#後片付け再構築) を確認します。port-forward の終了だけではクラスターやアプリは停止しません。

Git 未初期化の作業フォルダーを利用する場合は、ファイルを確認してから `git init` で履歴管理を開始できます。リモート URL の設定、コミット、公開は各自の運用に従ってください。

AWS の有料リソースを作成する際は、対象・費用・公開範囲・削除手順を確認し、明示承認を得てから実行します。
