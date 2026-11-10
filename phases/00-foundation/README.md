# Lab 00: リポジトリ基盤

## 学習目標

- 教材の目的、学習順序、今回の範囲を説明できる。
- ツールの未導入と実行失敗を区別し、次のフェーズに必要な準備を整理できる。
- ADR と Git の除外設定の役割を説明できる。

## 前提条件

Git と PowerShell 5.1 以降、または Bash を利用する。その他のツールは未導入でも本ラボを完了できる。AWS 利用やコンテナ起動はなく、クラウド費用は発生しない。

## 設計課題（実装前に考える）

1. なぜ最初から EKS にアプリを配置しないのか？
2. バージョン表示の成功で、DB 接続や Docker エンジンの起動まで保証できるか？
3. 設計書を二つ複製すると、更新時にどんな問題が起きるか？
4. `.gitignore` に追加すれば、過去にコミットした秘密値も消えるか？

## 実装タスク

1. [全体 README](../../README.md) と [一次設計書](../../docs/PROJECT_DESIGN.md) を読み、Phase 0 の範囲を確認する。
2. `.gitignore` と `.editorconfig` を読み、秘密情報の扱いとファイル形式を確認する。
3. [ADR-0001](../../docs/adr/0001-application-and-learning-stack.md) の採用理由・代替案を確認する。
4. 自分が利用するシェルで preflight を実行し、結果を学習ポータルの学習メモに記録する。

## 検証コマンド・期待結果

リポジトリ直下で実行します。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File .\tools\preflight.ps1
$LASTEXITCODE
```

**Linux / macOS / WSL (Bash):**

```bash
bash -n tools/preflight.sh
bash tools/preflight.sh
echo $?
```

Git、Docker、Docker Compose、kubectl、kind、Python、Node.js、AWS CLI、Terraform の結果が表示される。Git のバージョン取得に成功すれば終了コード 0。他ツールは未導入でもよい。Bash は `python3`、PowerShell は `python` を確認する。各シェルの PATH が異なると結果も変わる。

コマンド未検出なら PATH と導入先を確認する。「確認失敗」なら対象のバージョンコマンドを単独で実行し、終了コードと出力を調べる。実行ポリシーの拒否はシェルの設定として確認する。

Git 初期化済みの作業コピーでは、次で除外設定も観察できる:

```text
git check-ignore --no-index .env terraform/environments/lab/terraform.tfvars terraform/environments/lab/terraform.tfstate credentials.json private.key
git check-ignore --no-index .env.example terraform/environments/lab/terraform.tfvars.example
```

最初のコマンドは全対象のパスを表示して終了コード 0。次は何も表示せず終了コード 1（例示ファイルは除外されない）。ファイルを作る必要はない。未初期化なら `git init` を行うか、Git の除外確認は未実施として記録する。

## 完了条件

- [x] preflight を実行し、必須の Git が利用できる。
- [x] 未導入・確認失敗と、後続フェーズで必要なツールを記録した。
- [x] バージョン取得と実際の稼働確認の違いを説明できる。
- [x] 技術選定の理由と代替案を説明できる。
- [x] 検証結果、未実施事項、疑問を下記に記録した。

## 学習メモ

観察結果と設計課題への回答は、この README ではなく**学習ポータルに入力します**（各自の PC の Git 管理外 `learning-portal/.data` にだけ保存され、リポジトリには残りません）。実行していない実験は「省略」と理由を書きます。記録する項目は次のとおりです。

- 実行日・OS・シェル
- preflight の終了コード
- 利用可能なツールとバージョン
- 未導入・確認失敗
- Git 除外の確認結果
- WSL2 / Docker Desktop の経路
- 設計課題への自分の回答
- 疑問・未解決事項

参照: [一次設計書](../../docs/PROJECT_DESIGN.md)、[Git gitignore](https://git-scm.com/docs/gitignore)。具体的なツールのバージョン選択は該当フェーズで公式資料を確認する。

## 実装時の検証記録

2026-11-08 に実装担当が Windows 上で確認。学習者自身の記録は README ではなく学習ポータルに残す。

| 確認 | 結果 |
| --- | --- |
| PowerShell 5.1 構文解析 | エラーなし |
| `powershell -NoProfile -File tools/preflight.ps1` | 終了コード 0 |
| Git Bash 5.2.37 の `bash -n` と preflight 実行 | 構文エラーなし、終了コード 0 |
| Git | 2.53.0.windows.1 |
| Docker / Compose | 29.1.2 / v2.40.3-desktop.1。ローカル設定ファイルの読み取り拒否警告あり |
| kubectl / Kustomize | v1.34.1 / v5.7.1（クライアントのみ） |
| Python | PowerShell の `python`: 3.11.9。Git Bash の `python3`: 確認失敗 |
| Node.js / AWS CLI | v24.13.1 / 2.39.3 |
| kind / Terraform | コマンド未検出 |
| Git 除外対象 / 例示ファイル | 想定どおり除外 / 非除外 |
| WSL2 | `wsl --status` が `Wsl/EnumerateDistros/E_ACCESSDENIED` で失敗。状態確認不能 |
| WSL2 Ubuntu（Docker Desktop の WSL 統合）での `bash -n` と `bash tools/preflight.sh`（2026-11-10） | 構文エラーなし、Git・Docker・Compose・kubectl・Python・AWS CLI は利用可能、kind・Node.js・Terraform は未導入、終了コード 0 |
| ネイティブ Linux / macOS での実行 | 未実施 |
| Docker エンジン・Docker Desktop の連携・Kubernetes・AWS 接続 | 未実施 |

`git init` でローカルリポジトリを初期化した。検証用ユーザーと作業フォルダー所有者の差により通常の Git 操作が拒否されたため、除外検証時だけ `git -c safe.directory=C:/Users/azhid/kubernetes-eks-learning check-ignore --no-index ...` を使用した。グローバル設定の変更、コミット、プッシュは行っていない。

自分のユーザーで再実行するときは、まず通常の `git status` と上の検証コマンドを使う。同じ所有者エラーが出た場合は、作業フォルダーの所有者と場所を確認したうえで、該当コマンドに限って `-c safe.directory=確認した絶対パス` を付ける。Docker の警告が再現する場合は、自分のユーザーで `docker --version` と `docker compose version` を実行し、Docker 設定ファイルの読み取り権限を確認する。バージョン取得に成功してもエンジン稼働は保証されないため、Phase 1 開始時に別途確認する。

`.gitattributes` でスクリプトの LF 改行を固定し、Windows の Git 設定による Bash スクリプトの CRLF 化を防ぐ。

実装時に [Docker Compose version](https://docs.docker.com/reference/cli/docker/compose/version/)、[kubectl version](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_version/)、[Git gitignore](https://git-scm.com/docs/gitignore) の公式資料を参照した。`kubectl` はクライアントのみのオプションを指定している。
