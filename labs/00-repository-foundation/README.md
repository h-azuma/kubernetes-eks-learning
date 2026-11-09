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
4. 自分が利用するシェルで preflight を実行し、結果を学習メモに記録する。

## 検証コマンド・期待結果

Windows PowerShell（リポジトリ直下）:

```powershell
powershell -NoProfile -File .\scripts\preflight.ps1
$LASTEXITCODE
```

Linux / macOS / WSL の Bash（リポジトリ直下）:

```bash
bash -n scripts/preflight.sh
bash scripts/preflight.sh
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

実際の観察で埋める。未実施の項目にチェックを付けない。

| 項目 | 観察・結果 |
| --- | --- |
| 実行日・OS・シェル | 2026/11/8・Windows・Powershell |
| preflight の終了コード | 0 |
| 利用可能なツールとバージョン | Docker 29.1.2, Docker Compose v2.40.3-desktop.1, kubectl 1.34, Python 3.11.9, Node.js v24.13.1, aws-cli/2.39.3 |
| 未導入・確認失敗 | kind, Terraform |
| Git 除外の確認結果 | 設定済み |
| WSL2 / Docker Desktop の経路 | 確認済み |
| 設計課題への自分の回答 | 下記 |
| 疑問・未解決事項 | なし |

設計課題への回答
1. EKSはKubernetesをAWS上で管理するためのサービスであり、Kubernetesをまず理解する前にEKSを学ぼうとすると混乱するから。また、EKSは従量課金のサービスであり、最初から載せてしまうとどんどん課金されていってしまうから
2. DB接続やDockerエンジンの起動までは保証できない。デーモンが動いていないとDockerは動作できず、バージョンが返ってくるのは飽くまでもマシンにインストールされていることを示すだけだから
3. 二重管理になり、片方の更新漏れが発生すると、どちらが正しい情報かを判断するのが難しくなってしまう
4. 消えない。コミット履歴は残り続けるので履歴を遡ることで見えてしまう

参照: [一次設計書](../../docs/PROJECT_DESIGN.md)、[Git gitignore](https://git-scm.com/docs/gitignore)。具体的なツールのバージョン選択は該当フェーズで公式資料を確認する。

## 実装時の検証記録

2026-11-08 に実装担当が Windows 上で確認。上の学習メモは学習者自身が記録するための欄として残す。

| 確認 | 結果 |
| --- | --- |
| PowerShell 5.1 構文解析 | エラーなし |
| `powershell -NoProfile -File scripts/preflight.ps1` | 終了コード 0 |
| Git Bash 5.2.37 の `bash -n` と preflight 実行 | 構文エラーなし、終了コード 0 |
| Git | 2.53.0.windows.1 |
| Docker / Compose | 29.1.2 / v2.40.3-desktop.1。ローカル設定ファイルの読み取り拒否警告あり |
| kubectl / Kustomize | v1.34.1 / v5.7.1（クライアントのみ） |
| Python | PowerShell の `python`: 3.11.9。Git Bash の `python3`: 確認失敗 |
| Node.js / AWS CLI | v24.13.1 / 2.39.3 |
| kind / Terraform | コマンド未検出 |
| Git 除外対象 / 例示ファイル | 想定どおり除外 / 非除外 |
| WSL2 | `wsl --status` が `Wsl/EnumerateDistros/E_ACCESSDENIED` で失敗。状態確認不能 |
| Linux / macOS / WSL 内での実行 | 未実施 |
| Docker エンジン・Docker Desktop の連携・Kubernetes・AWS 接続 | 未実施 |

`git init` でローカルリポジトリを初期化した。検証用ユーザーと作業フォルダー所有者の差により通常の Git 操作が拒否されたため、除外検証時だけ `git -c safe.directory=C:/Users/azhid/kubernetes-eks-learning check-ignore --no-index ...` を使用した。グローバル設定の変更、コミット、プッシュは行っていない。

自分のユーザーで再実行するときは、まず通常の `git status` と上の検証コマンドを使う。同じ所有者エラーが出た場合は、作業フォルダーの所有者と場所を確認したうえで、該当コマンドに限って `-c safe.directory=確認した絶対パス` を付ける。Docker の警告が再現する場合は、自分のユーザーで `docker --version` と `docker compose version` を実行し、Docker 設定ファイルの読み取り権限を確認する。バージョン取得に成功してもエンジン稼働は保証されないため、Phase 1 開始時に別途確認する。

`.gitattributes` でスクリプトの LF 改行を固定し、Windows の Git 設定による Bash スクリプトの CRLF 化を防ぐ。

実装時に [Docker Compose version](https://docs.docker.com/reference/cli/docker/compose/version/)、[kubectl version](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_version/)、[Git gitignore](https://git-scm.com/docs/gitignore) の公式資料を参照した。`kubectl` はクライアントのみのオプションを指定している。
