# Lab 02: kind と Kubernetes の基本

## 学習目標

- Control Plane・Node・Pod・ReplicaSet・Deployment の役割を区別する。
- label/selector と Service DNS が、Pod の置き換えにどう対応するか観察する。
- マニフェストの再適用と、Pod 削除後の自動復旧を確認する。
- Compose の volume と、今回の一時 DB の保存期間の違いを説明する。

## 前提条件

Lab 01 完了、Linux コンテナエンジンが動く Docker（Windows / macOS は Docker Desktop、Linux は Docker Engine または Docker Desktop）、kubectl 1.34〜1.36、kind v0.33.0。今回のノードは Kubernetes v1.35.8 です。Docker にローカルノード1台を動かす CPU・メモリ・ディスクの空きが必要です。初回はイメージをダウンロードしますが AWS 費用はありません。

この DB はダミーデータ専用です。Compose の DB/volume/.env を使わず、Pod を削除するとデータは消えます。Phase 3 で永続化を導入します。

## 設計課題（実装前に考える）

1. Pod を直接作る方法と、Deployment で管理する方法は何が違うか？
2. Pod の IP を直接使わず Service を使う理由は何か？
3. Service の selector と Pod の label が一致しないとどうなるか？
4. API Pod を削除した場合と、DB Pod を削除した場合でデータはどう変わるか？
5. `docker compose up` と `kubectl apply` は、どちらも定義を渡すが、稼働後に誰が状態を維持するか？

## 実装タスク

1. [構成図と Compose との比較](architecture.md)、[ADR-0003](decisions/0003-kind-minimal-workloads.md) を読む。
2. 専用 kind を用意し、クラスターに同じ WorkBoard イメージを投入する。
3. Namespace・DB・migration Job・Web/API を適用し、状態と通信先を観察する。
4. Pod を置き換え、結果を **学習ポータルの学習メモ**（項目は「学習メモ」節）に記録する。

## 検証コマンド・期待結果

すべてリポジトリ直下で実行します。`-f` は定義ファイル、`-n` は Namespace、`--context` は操作対象クラスターの設定名です。今回の全 Kubernetes 操作は `kind-workboard-lab` を指定します。

各コマンドは 1 つずつ実行します。コマンドの直前の「目的」で何のために打つかを、直後の「確認」で出力のどこを見るかを確かめてから、次のコマンドへ進みます。

### 1. ツール導入とクラスター構築

初回だけ実行します。Windows は PowerShell 5.1 以降、Linux / macOS / WSL は Bash（Linux 側の条件は「Linux / macOS / WSL での前提」を参照）で行います。PowerShell と Bash は同じ処理をするスクリプトです。

構築スクリプト `up`（`up.ps1` / `up.sh`）の起動処理は以下の順です。固定秒数の sleep ではなく、実際の状態を待ちます。

1. `kind create cluster`（存在しなければ作成）
2. 同じ API/Web Dockerfile のビルド
3. `kind load docker-image` でノードへイメージ投入
4. Namespace・DB 適用 → DB Deployment の準備完了待ち
5. migration Job 適用 → Complete 待ち
6. Web/API 適用 → Deployment の準備完了待ち

目的：kind のインストーラーを実行します。公式 kind を取得し SHA-256 を検証して、Windows では `.tools/kind.exe`、Linux では `.tools/kind` に置きます。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File tools/kind-install.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash tools/kind-install.sh
```

確認：エラーが出ずに終了すれば完了です。管理者権限や永続的な PATH 変更は不要です。

目的：上の 1〜6 の構築（クラスター作成、イメージ投入、Namespace・DB・migration・Web/API の適用、準備完了待ち）を実行して、専用 kubeconfig `.kube/workboard-kind.yaml` を作ります。Docker・kubectl の対応も確認します。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/02-kind-basics/scripts/up.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/02-kind-basics/scripts/up.sh
```

確認：エラーなく終了することを見ます。期待結果は Node が Ready、Deployment が各1 Pod、migration Job が Completed です。既存クラスター・DB の削除はしません。同名クラスターだけあり、専用 kubeconfig がない場合は確認のため停止します。イメージ投入はホストの Docker と kind ノードのイメージ保存先が別であるため必要です。API/Web は `imagePullPolicy: Never` なので投入忘れは `ErrImageNeverPull` になります。PostgreSQL は `IfNotPresent` でノードが公式レジストリから取得します。ローカル学習用ビルドは `--provenance=false` とし、複数 platform・attestation の manifest をノードへ持ち込む問題を避けます。

### 2. 現在のシェルで対象を選び、状態を観察する

**構築済みのこの作業環境では、まずここから進めてください。** 新しいターミナルを開くたびに最初の行を実行します。PowerShell の先頭のドットとスペース、Bash の `source` は、設定を今のシェルへ読み込む指定です（Bash の `env.sh` は実行ではなく `source` で使います）。

目的：このシェルだけで `.tools` と専用 KUBECONFIG を使う設定にして、以降の `kubectl` が `workboard-lab` を向くようにします。

**Windows (PowerShell):**

```powershell
. .\phases\02-kind-basics\scripts\env.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
source phases/02-kind-basics/scripts/env.sh
```

確認：画面に出力は想定していません。エラーが出なければ設定済みです。標準 kubeconfig やシステム PATH は変更しません。

目的：Node が Ready か確認します。

```text
kubectl --context kind-workboard-lab get nodes
```

確認：STATUS が `Ready` であることを見ます。

目的：`workboard` Namespace の Pod・ReplicaSet・Deployment・Service を一覧して、全体の状態を確認します。

```text
kubectl --context kind-workboard-lab -n workboard get pods,rs,deploy,svc
```

確認：Deployment が各1 Pod で、Pod・ReplicaSet・Deployment・Service が揃っていることを見ます。Compose 用コンテナはこの一覧には出ません。

目的：Pod の label を表示して、Service の selector と対応づけます。

```text
kubectl --context kind-workboard-lab -n workboard get pods --show-labels
```

確認：Pod の LABELS に `app=workboard-api` などが付いていることを見ます。後の手順で Service の selector と見比べます。

目的：API の所有関係を調べます。まず API の Pod の詳細（IP・Node）を見ます。

```text
kubectl --context kind-workboard-lab -n workboard get pods -l app=workboard-api -o wide
```

確認：API の Pod が 1 つ表示され、Pod IP が見えることを見ます。

目的：API の Pod を管理している ReplicaSet を確認します。

```text
kubectl --context kind-workboard-lab -n workboard get rs -l app=workboard-api -o wide
```

確認：Pod 名の前半と ReplicaSet 名が対応していることを見ます。Deployment → ReplicaSet → Pod の順に管理されます。

目的：Deployment の詳細を読みます。

```text
kubectl --context kind-workboard-lab -n workboard describe deployment workboard-api
```

確認：`NewReplicaSet` が前の手順の ReplicaSet であること、Pod テンプレートの label が `app=workboard-api` であることを見ます。

目的：Service の詳細を読みます。

```text
kubectl --context kind-workboard-lab -n workboard describe service workboard-api
```

確認：Service の selector `app=workboard-api` と Pod の label を見比べます。Service の ClusterIP と Pod IP は別であることを見ます。

目的：Service の転送先 Pod を表す EndpointSlice を確認します。

```text
kubectl --context kind-workboard-lab -n workboard get endpointslices -l kubernetes.io/service-name=workboard-api
```

確認：EndpointSlice に転送先 Pod のアドレスが含まれることを見ます。

### 3. ブラウザーで同じアプリを使う

目的：Web Service をホストの 8080 番へ転送して、ブラウザーから WorkBoard を使えるようにします。8080 番を Compose 等で使っていないことを確認してから実行します。このコマンドは実行中のまま残し、ブラウザーと次の確認コマンドは別のターミナルで操作します。

```text
kubectl --context kind-workboard-lab -n workboard port-forward --address 127.0.0.1 svc/workboard-web 8080:80
```

確認：`Forwarding from 127.0.0.1:8080 -> 80` が表示され、コマンドは終了せずに待機し続けます。`8080:80` はホスト8080番から Service80番への転送です。[http://localhost:8080](http://localhost:8080) でダミータスク「kind の学習」を作り、編集・ステータス絞り込み・再読込を試してください。削除の確認は別のダミータスクで行い、「kind の学習」は次の実験用に残します。Service を指定した port-forward は、selector から選ばれた Web Pod へトンネルします。ClusterIP 自体を外部公開する操作ではありません。Web から API への通信では実際に ClusterIP Service を使います。

目的：別のターミナルで、API の Liveness を Web 経由で確認します。

**Windows (PowerShell):**

```powershell
curl.exe -i http://localhost:8080/health/live
```

**Linux / macOS / WSL (Bash):**

```bash
curl -i http://localhost:8080/health/live
```

確認：ステータス行が `200` であることを見ます。

目的：別のターミナルで、API の Readiness を Web 経由で確認します。

**Windows (PowerShell):**

```powershell
curl.exe -i http://localhost:8080/health/ready
```

**Linux / macOS / WSL (Bash):**

```bash
curl -i http://localhost:8080/health/ready
```

確認：ステータス行が `200` であることを見ます。port-forward は永続的な公開設定ではなく、コマンドを止めると接続できなくなります。

### 4. API Pod を削除し、自動復旧を観察する

目的：別のターミナルで、このシェルが専用設定（`workboard-lab`）を使うようにします。

**Windows (PowerShell):**

```powershell
. .\phases\02-kind-basics\scripts\env.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
source phases/02-kind-basics/scripts/env.sh
```

確認：画面に出力は想定していません。エラーが出なければよいです。

目的：削除する前の API Pod の名前・UID・IP を記録します。

```text
kubectl --context kind-workboard-lab -n workboard get pods -l app=workboard-api -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,IP:.status.podIP
```

確認：Pod が 1 つ表示されることを見て、名前・UID・IP を控えます。削除後に比べるための値です。

目的：API Pod を削除して、Deployment（ReplicaSet）に作り直させます。DB は削除しません。

```text
kubectl --context kind-workboard-lab -n workboard delete pod -l app=workboard-api
```

確認：`pod "..." deleted` と表示されます。削除すると元の UID を取得できなくなるため、直前の記録を済ませてから実行してください。

目的：新しい API Pod の準備完了まで待ちます。

```text
kubectl --context kind-workboard-lab -n workboard rollout status deployment/workboard-api --timeout=180s
```

確認：待機が終わり、180 秒のタイムアウトで失敗しないことを見ます。

目的：作り直された API Pod の名前・UID・IP を、削除前の記録と比べます。

```text
kubectl --context kind-workboard-lab -n workboard get pods -l app=workboard-api -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,IP:.status.podIP
```

確認：名前・UID が変わり、Pod が1つに戻ります。IP は再利用される場合もあるので「必ず変わる」とは判断しません。ブラウザー再読込でタスクが残り、同じ URL から操作できることを確認します。API Pod を消しただけなので DB は残っています。

### 5. マニフェストを再適用する

目的：Namespace・DB・migration・Web/API のマニフェストを再適用して、`apply` が冪等であることを確認します。

```text
kubectl --context kind-workboard-lab apply -f phases/02-kind-basics/manifests/namespace.yaml -f phases/02-kind-basics/manifests/postgres.yaml -f phases/02-kind-basics/manifests/migrate.yaml -f phases/02-kind-basics/manifests/app.yaml
```

確認：定義を変更していなければ、基本的に各行が `unchanged` と表示されます。再適用だけで毎回新しい Pod が作られるわけではありません。完了済み migration Job も再実行されません。

アプリコードを変更して構築スクリプトを再実行した場合は、同じ `:kind` タグを使うため、次のコマンドで新しいイメージから Pod を作り直します。

目的：Web と API の Deployment を再起動して、新しいイメージから Pod を作り直します（アプリコードを変更して構築スクリプトを再実行したときだけ実行します）。

```text
kubectl --context kind-workboard-lab -n workboard rollout restart deployment/workboard-api deployment/workboard-web
```

確認：`deployment.apps/workboard-api restarted` などと表示されることを見ます。Web Pod を置き換えると port-forward の接続も終了することがあります。その場合は手順3を再実行します。

## 故障実験: 一時 DB とデータ消失

**このラボで作ったダミータスクを失ってよいと確認できた場合だけ実行してください。** 次の DB Pod 削除はタスクとスキーマを消します。Compose の DB/volume には影響しません。

目的：DB Pod を削除します。消えるのは、この Pod の emptyDir にあるタスクとスキーマです。実行前に、失ってよいダミータスクだけであることを確認してください。

```text
kubectl --context kind-workboard-lab -n workboard delete pod -l app=workboard-postgres
```

確認：`pod "..." deleted` と表示されます。DB は新しい emptyDir で起動します。

目的：新しい DB Pod の準備完了まで待ちます。

```text
kubectl --context kind-workboard-lab -n workboard rollout status deployment/workboard-postgres --timeout=180s
```

確認：待機が終わり、180 秒のタイムアウトで失敗しないことを見ます。既存の migration Job は完了済みなので、そのままではテーブルがありません。`/health/ready` は接続の `SELECT 1` だけを確認するため200に戻る場合もありますが、CRUD が使えることまでは保証しません。

スキーマを戻すには Job だけを削除して再適用します。

目的：完了済みの migration Job だけを削除します。完了済みの Job は再実行されないため、削除してから作り直します。

```text
kubectl --context kind-workboard-lab -n workboard delete job workboard-migrate
```

確認：`job.batch "workboard-migrate" deleted` と表示されます。

目的：migration のマニフェストだけを再適用して、Job を作り直します。

```text
kubectl --context kind-workboard-lab apply -f phases/02-kind-basics/manifests/migrate.yaml
```

確認：`job.batch/workboard-migrate created` と表示されます。

目的：migration Job の完了まで待ちます。

```text
kubectl --context kind-workboard-lab -n workboard wait --for=condition=complete job/workboard-migrate --timeout=180s
```

確認：`job.batch/workboard-migrate condition met` と表示され、180 秒のタイムアウトで失敗しないことを見ます。ブラウザーを再読込すると一覧が空になります。タスクを新規作成して動作復旧を確認します。元のタスクの復元ではありません。

## 失敗時に確認すること

- `kind` が見つからない: installer の後、このシェルで `scripts/env.ps1`（Bash は `source .../env.sh`）を読み込んだか。
- 接続先がない/証明書エラー: 専用 KUBECONFIG と context を使っているか。他のクラスターへ切り替えて試さない。
- `ErrImageNeverPull`: `kind load docker-image ... --name workboard-lab` が成功したか。
- Job が失敗: `kubectl --context kind-workboard-lab -n workboard logs job/workboard-migrate` と DB の状態を確認。
- API が動かない: `describe pod`、`logs deployment/workboard-api`、`get events --sort-by=.metadata.creationTimestamp` を同じ context/Namespace で確認。
- Service から接続できない: selector・label・EndpointSlice、readiness、アプリの待受ポートを確認。
- Web から502: Nginx の接続先と DNS、API の準備状態を確認。Compose の Docker DNS アドレスを kind で固定しない。

## Linux / macOS / WSL での前提

スクリプトは PowerShell 版と同じ処理の Bash 版（`tools/kind-install.sh`、`phases/02-kind-basics/scripts/env.sh`・`up.sh`）があり、上の手順の「Linux / macOS / WSL (Bash)」に従います。

- Bash 4 以降が必要です。macOS 標準の bash 3.2 は対象外で、Homebrew などで新しい bash を入れてください。`kind-install.sh` は Linux（x86_64 / arm64）用です。macOS では [公式導入手順](https://kind.sigs.k8s.io/docs/user/quick-start/#installation) で kind v0.33.0 を入れ、`.tools/` に置くか PATH に通します。
- Docker は Linux コンテナエンジンを起動しておき、実行ユーザーが `docker` を sudo なしで使えるようにします。WSL では Docker Desktop の WSL 統合を有効にし、WSL 内で `docker info` が成功することを確認します。
- kubectl は 1.34〜1.36 を [公式手順](https://kubernetes.io/docs/tasks/tools/) で導入します。スクリプトは kubectl を導入しません。
- `.tools/kind`（Linux）と `.tools/kind.exe`（Windows）は同じ `.tools/` に共存できます。同じ作業ツリーを Windows と WSL で共有する場合も、クラスター名・kubeconfig・ポートは共通です。
- 外部コマンドは `docker`、`kind`、`kubectl`、`curl`、`sha256sum` だけです。

## 後片付け・再構築

port-forward を実行しているターミナルで `Ctrl+C` を押すとブラウザーの入口を閉じます。これはクラスターの停止ではなく、Node とアプリは動き続けます。

kind クラスターを削除すると今回の DB データも失います。クラスター名と消失するデータを確認し、削除してよいと明示的に判断した場合だけ次のコマンドを使います。

目的：kind クラスター `workboard-lab` を削除します。削除前に、クラスター名が `workboard-lab` であることと、失う DB データ（ダミータスク）を確認してください。

```text
kind delete cluster --name workboard-lab
```

確認：クラスター `workboard-lab` が削除されたことを示す表示になることを見ます。削除を実施した場合、専用 kubeconfig が残っていれば対象を確認してそのファイルだけを削除してから、構築スクリプトを実行します。他の kubeconfig は削除しません。作り直したクラスターは空の DB で始まります。Compose の volume は残ります。

## 完了条件

- [ ] Node が Ready、Web/API/DB の Deployment と Service が存在する。
- [ ] Deployment → ReplicaSet → Pod と label/selector の関係を説明できる。
- [ ] ブラウザーから CRUD・絞り込み・再読込を確認した。
- [ ] API Pod の削除後に新しい Pod が作られ、Service 経由の操作とデータ保持を確認した。
- [ ] マニフェストの再適用結果を観察した。
- [ ] 一時 DB のデータ寿命と migration の再実行方法を説明できる。
- [ ] 下記に結果・未実施の実験・設計課題への回答を記録した。

## 学習メモ

観察結果と設計課題への回答は、この README ではなく**学習ポータルに入力します**（各自の PC の Git 管理外 `learning-portal/.data` にだけ保存され、リポジトリには残りません）。実行していない実験は「省略」と理由を書きます。記録する項目は次のとおりです。

- 実行日・OS・シェル
- kind / kubectl / Kubernetes バージョン
- Node・Deployment・ReplicaSet・Pod の状態
- Service の selector と Pod label
- 画面の CRUD・絞り込み・再読込
- API Pod 削除前後の名前・UID・IP
- API Pod 削除後の Service とデータ
- マニフェスト再適用
- DB 再作成と migration 再実行
- Compose との責任範囲の違い
- 後片付け・残したクラスター
- 疑問・未解決事項

## 実装時の検証記録

2026-11-08、Windows PowerShell 5.1、Docker Desktop の Linux エンジンで実装担当が確認しました。学習者自身の記録は README ではなく学習ポータルに残します。

| 確認・コマンド | 結果 |
| --- | --- |
| `tools/kind-install.ps1` | 公式 kind v0.33.0 を SHA-256 照合後に `.tools/kind.exe` へ導入 |
| PowerShell 3スクリプトの構文解析 | エラーなし、PowerShell 5.1 用 UTF-8 BOM を確認 |
| `phases/02-kind-basics/scripts/up.ps1` | Node v1.35.8 が Ready、全 Deployment が 1/1、migration が Completed |
| 既存 kubectl | v1.34.1。サーバーとの minor 差1 |
| 構築スクリプトの再実行 | 終了コード0。既存クラスター・Pod・DB を維持し、定義は unchanged |
| 所有関係と通信先 | API Pod → ReplicaSet → Deployment、Service selector・Pod label・EndpointSlice の対応を確認 |
| port-forward 経由の HTTP | 画面/live/ready/tasks は200。CRUD・status 絞り込み・不正入力422を確認 |
| API Pod の削除 | UID が別の Pod へ変更、Service ClusterIP は `10.96.99.186` のまま、タスクも保持 |
| DB Pod の削除 | emptyDir のタスク・スキーマが消失。migration Job の再作成後に空の一覧と CRUD 復旧を確認 |
| 既存 Edge を一時 Playwright から操作 | 画面の作成・一覧・編集・絞り込み・再読込・削除に成功。JavaScript エラーなし |
| Nginx の生成設定 | kind の DNS `10.96.0.10` と API Service FQDN を使用し、Nginx の `$host` は変換されず維持 |
| Compose の回帰確認 | `config --quiet` と `run --build --rm --no-deps web nginx -t` 成功。学習用 DB・volume は操作せず、検証で作った空のネットワークだけ削除 |
| Git 除外 | `.tools`・専用 `.kube`・既存 `.env` が対象外 |
| 終了時の状態 | 検証用タスクは削除済み。port-forward を停止し、kind クラスターとアプリは起動中で維持 |

初回はホストの PostgreSQL マルチプラットフォーム manifest を `kind load` した際、未取得 digest により失敗しました。最終構成では API/Web だけを `--provenance=false` でビルドして投入し、PostgreSQL はノードが取得します。この修正後、クラスターを削除せず同じ構築スクリプトを再実行して成功しました。

2026-11-10、WSL2 Ubuntu（Docker Desktop の WSL 統合）で `tools/kind-install.sh` と `phases/02-kind-basics/scripts/up.sh` を確認しました（クラスター新規作成、Node Ready、全 Deployment 1/1、migration Job Complete、再実行も成功）。ネイティブ Linux、macOS、Docker Engine 単独での実行は未実施です。クラスター全削除後の再構築は Windows では未実施です。既存 Compose のタスクは移行・削除していません。PVC・StatefulSet・ConfigMap/Secret・Ingress・AWS は今回追加していません。
