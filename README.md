# Kubernetes / Amazon EKS 学習教材

簡易タスク管理アプリ **WorkBoard** を同じ題材として、コンテナから Kubernetes、AWS 上の設計・運用判断まで段階的に学びます。

現在は **Phase 0（リポジトリ基盤）** です。学習の順序、設計判断の記録方法、ツールの確認手順を用意しています。アプリの実装は Phase 1 からです。

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

各ラボで「問い → 実装 → 観察 → 設計判断 → 完了条件」を記録します。未実施の検証は未実施と書きます。Phase 0 は参照のみの確認なので、停止・削除するサービスはありません。

Git 未初期化の作業フォルダーを利用する場合は、ファイルを確認してから `git init` で履歴管理を開始できます。リモート URL の設定、コミット、公開は各自の運用に従ってください。

AWS の有料リソースを作成する際は、対象・費用・公開範囲・削除手順を確認し、明示承認を得てから実行します。
