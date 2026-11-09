# Lab 02: kind と Kubernetes の基本

## 学習目標

- Control Plane・Node・Pod・ReplicaSet・Deployment の役割を区別する。
- label/selector と Service DNS が、Pod の置き換えにどう対応するか観察する。
- マニフェストの再適用と、Pod 削除後の自動復旧を確認する。
- Compose の volume と、今回の一時 DB の保存期間の違いを説明する。

## 前提条件

Lab 01 完了、Docker Desktop の Linux コンテナエンジン、kubectl 1.34〜1.36、kind v0.33.0。今回のノードは Kubernetes v1.35.8 です。Docker にローカルノード1台を動かす CPU・メモリ・ディスクの空きが必要です。初回はイメージをダウンロードしますが AWS 費用はありません。

この DB はダミーデータ専用です。Compose の DB/volume/.env を使わず、Pod を削除するとデータは消えます。Phase 3 で永続化を導入します。

## 設計課題（実装前に考える）

1. Pod を直接作る方法と、Deployment で管理する方法は何が違うか？
2. Pod の IP を直接使わず Service を使う理由は何か？
3. Service の selector と Pod の label が一致しないとどうなるか？
4. API Pod を削除した場合と、DB Pod を削除した場合でデータはどう変わるか？
5. `docker compose up` と `kubectl apply` は、どちらも定義を渡すが、稼働後に誰が状態を維持するか？

## 実装タスク

1. [構成図と Compose との比較](../../docs/architecture/02-kind.md)、[ADR-0003](../../docs/adr/0003-kind-minimal-workloads.md) を読む。
2. 専用 kind を用意し、クラスターに同じ WorkBoard イメージを投入する。
3. Namespace・DB・migration Job・Web/API を適用し、状態と通信先を観察する。
4. Pod を置き換え、以下の **「学習メモ」** に結果を直接記入する。

## 検証コマンド・期待結果

すべてリポジトリ直下で実行します。`-f` は定義ファイル、`-n` は Namespace、`--context` は操作対象クラスターの設定名です。今回の全 Kubernetes 操作は `kind-workboard-lab` を指定します。

### 1. ツール導入とクラスター構築

Windows PowerShell 5.1 以降で初回だけ実行します。

```powershell
powershell -NoProfile -File scripts/kind-install.ps1
powershell -NoProfile -File scripts/kind-up.ps1
```

installer は公式 kind を取得し SHA-256 を検証して `.tools/kind.exe` に置きます。管理者権限や永続的な PATH 変更は不要です。構築スクリプトは Docker・kubectl の対応を確認し、専用 kubeconfig `.kube/workboard-kind.yaml` を作ります。既存クラスター・DB の削除はしません。同名クラスターだけあり、専用 kubeconfig がない場合は確認のため停止します。

起動処理は以下の順です。固定秒数の sleep ではなく、実際の状態を待ちます。

1. `kind create cluster`（存在しなければ作成）
2. 同じ API/Web Dockerfile のビルド
3. `kind load docker-image` でノードへイメージ投入
4. Namespace・DB 適用 → DB Deployment の準備完了待ち
5. migration Job 適用 → Complete 待ち
6. Web/API 適用 → Deployment の準備完了待ち

期待結果は Node が Ready、Deployment が各1 Pod、migration Job が Completed です。イメージ投入はホストの Docker と kind ノードのイメージ保存先が別であるため必要です。API/Web は `imagePullPolicy: Never` なので投入忘れは `ErrImageNeverPull` になります。PostgreSQL は `IfNotPresent` でノードが公式レジストリから取得します。ローカル学習用ビルドは `--provenance=false` とし、複数 platform・attestation の manifest をノードへ持ち込む問題を避けます。

### 2. 現在の PowerShell で対象を選び、状態を観察する

**構築済みのこの作業環境では、まずここから進めてください。** 新しい PowerShell を開くたびに最初の行を実行します。先頭のドットとスペースは、設定を今のシェルへ読み込む指定です。

```powershell
. .\scripts\kind-env.ps1
kubectl --context kind-workboard-lab get nodes
kubectl --context kind-workboard-lab -n workboard get pods,rs,deploy,svc
kubectl --context kind-workboard-lab -n workboard get pods --show-labels
```

`kind-env.ps1` は今のシェルだけに `.tools` と専用 KUBECONFIG を設定します。標準 kubeconfig やシステム PATH は変更しません。Compose 用コンテナはこの一覧には出ません。

API の所有関係も調べます。

```powershell
kubectl --context kind-workboard-lab -n workboard get pods -l app=workboard-api -o wide
kubectl --context kind-workboard-lab -n workboard get rs -l app=workboard-api -o wide
kubectl --context kind-workboard-lab -n workboard describe deployment workboard-api
kubectl --context kind-workboard-lab -n workboard describe service workboard-api
kubectl --context kind-workboard-lab -n workboard get endpointslices -l kubernetes.io/service-name=workboard-api
```

Deployment → ReplicaSet → Pod の順に管理されます。Service の selector `app=workboard-api` と Pod の label を見比べてください。Service の ClusterIP と Pod IP は別です。EndpointSlice には転送先 Pod のアドレスが含まれます。

### 3. ブラウザーで同じアプリを使う

8080 番を Compose 等で使っていないことを確認します。次のコマンドは実行中のまま残し、ブラウザーを別に開きます。

```powershell
kubectl --context kind-workboard-lab -n workboard port-forward --address 127.0.0.1 svc/workboard-web 8080:80
```

`8080:80` はホスト8080番から Service80番への転送です。`Forwarding from 127.0.0.1:8080 -> 80` が期待結果。[http://localhost:8080](http://localhost:8080) でダミータスク「kind の学習」を作り、編集・ステータス絞り込み・再読込を試してください。削除の確認は別のダミータスクで行い、「kind の学習」は次の実験用に残します。

Service を指定した port-forward は、selector から選ばれた Web Pod へトンネルします。ClusterIP 自体を外部公開する操作ではありません。Web から API への通信では実際に ClusterIP Service を使います。

他の PowerShell で以下を実行すれば health も確認できます。

```powershell
curl.exe -i http://localhost:8080/health/live
curl.exe -i http://localhost:8080/health/ready
```

どちらも200が期待結果です。port-forward は永続的な公開設定ではなく、コマンドを止めると接続できなくなります。

### 4. API Pod を削除し、自動復旧を観察する

別の PowerShell で専用設定を読み込み、現在の Pod の名前・UID・IP を記録します。

```powershell
. .\scripts\kind-env.ps1
kubectl --context kind-workboard-lab -n workboard get pods -l app=workboard-api -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,IP:.status.podIP
kubectl --context kind-workboard-lab -n workboard delete pod -l app=workboard-api
kubectl --context kind-workboard-lab -n workboard rollout status deployment/workboard-api --timeout=180s
kubectl --context kind-workboard-lab -n workboard get pods -l app=workboard-api -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,IP:.status.podIP
```

名前・UID が変わり、Pod が1つに戻ります。IP は再利用される場合もあるので「必ず変わる」とは判断しません。ブラウザー再読込でタスクが残り、同じ URL から操作できることを確認します。API Pod を消しただけなので DB は残っています。

### 5. マニフェストを再適用する

```powershell
kubectl --context kind-workboard-lab apply -f kubernetes/kind/namespace.yaml -f kubernetes/kind/postgres.yaml -f kubernetes/kind/migrate.yaml -f kubernetes/kind/app.yaml
```

定義を変更していなければ基本的に `unchanged` です。再適用だけで毎回新しい Pod が作られるわけではありません。完了済み migration Job も再実行されません。

アプリコードを変更して構築スクリプトを再実行した場合は、同じ `:kind` タグを使うため、以下で新しいイメージから Pod を作り直します。

```powershell
kubectl --context kind-workboard-lab -n workboard rollout restart deployment/workboard-api deployment/workboard-web
```

Web Pod を置き換えると port-forward の接続も終了することがあります。その場合は手順3を再実行します。

## 故障実験: 一時 DB とデータ消失

**このラボで作ったダミータスクを失ってよいと確認できた場合だけ実行してください。** 次の DB Pod 削除はタスクとスキーマを消します。Compose の DB/volume には影響しません。

```powershell
kubectl --context kind-workboard-lab -n workboard delete pod -l app=workboard-postgres
kubectl --context kind-workboard-lab -n workboard rollout status deployment/workboard-postgres --timeout=180s
```

DB は新しい emptyDir で起動します。既存の migration Job は完了済みなので、そのままではテーブルがありません。`/health/ready` は接続の `SELECT 1` だけを確認するため200に戻る場合もありますが、CRUD が使えることまでは保証しません。

スキーマを戻すには Job だけを削除して再適用します。

```powershell
kubectl --context kind-workboard-lab -n workboard delete job workboard-migrate
kubectl --context kind-workboard-lab apply -f kubernetes/kind/migrate.yaml
kubectl --context kind-workboard-lab -n workboard wait --for=condition=complete job/workboard-migrate --timeout=180s
```

ブラウザーを再読込すると一覧が空になります。タスクを新規作成して動作復旧を確認します。元のタスクの復元ではありません。

## 失敗時に確認すること

- `kind` が見つからない: installer の後、この PowerShell で `kind-env.ps1` を読み込んだか。
- 接続先がない/証明書エラー: 専用 KUBECONFIG と context を使っているか。他のクラスターへ切り替えて試さない。
- `ErrImageNeverPull`: `kind load docker-image ... --name workboard-lab` が成功したか。
- Job が失敗: `kubectl --context kind-workboard-lab -n workboard logs job/workboard-migrate` と DB の状態を確認。
- API が動かない: `describe pod`、`logs deployment/workboard-api`、`get events --sort-by=.metadata.creationTimestamp` を同じ context/Namespace で確認。
- Service から接続できない: selector・label・EndpointSlice、readiness、アプリの待受ポートを確認。
- Web から502: Nginx の接続先と DNS、API の準備状態を確認。Compose の Docker DNS アドレスを kind で固定しない。

## Linux / macOS / WSL での再現

Windows 用スクリプトは使わず、公式 release の OS/CPU に合う kind v0.33.0 と `.sha256sum` を取得・照合し、実行可能にして `.tools/kind` に置きます。[公式導入手順](https://kind.sigs.k8s.io/docs/user/quick-start/#installation) に従ってください。kubectl は1.34〜1.36を使います。

```bash
export PATH="$PWD/.tools:$PATH"
export KUBECONFIG="$PWD/.kube/workboard-kind.yaml"
mkdir -p .kube
kind create cluster --name workboard-lab --config kubernetes/kind/cluster.yaml --kubeconfig "$KUBECONFIG" --wait 180s
docker build --provenance=false --target runtime -t workboard-api:kind app/api
docker build --provenance=false -t workboard-web:kind app/web
kind load docker-image workboard-api:kind workboard-web:kind --name workboard-lab
kubectl --context kind-workboard-lab apply -f kubernetes/kind/namespace.yaml -f kubernetes/kind/postgres.yaml
kubectl --context kind-workboard-lab -n workboard rollout status deployment/workboard-postgres --timeout=180s
kubectl --context kind-workboard-lab apply -f kubernetes/kind/migrate.yaml
kubectl --context kind-workboard-lab -n workboard wait --for=condition=complete job/workboard-migrate --timeout=180s
kubectl --context kind-workboard-lab apply -f kubernetes/kind/app.yaml
kubectl --context kind-workboard-lab -n workboard rollout status deployment/workboard-api --timeout=180s
kubectl --context kind-workboard-lab -n workboard rollout status deployment/workboard-web --timeout=180s
```

初回構築用です。同名クラスターがある場合は作成を繰り返さず、対象と kubeconfig を確認します。以後の kubectl 操作は上の手順と共通です。Bash の HTTP 確認には `curl.exe` の代わりに `curl` を使います。

## 後片付け・再構築

port-forward の PowerShell で `Ctrl+C` を押すとブラウザーの入口を閉じます。これはクラスターの停止ではなく、Node とアプリは動き続けます。

kind クラスターを削除すると今回の DB データも失います。クラスター名と消失するデータを確認し、削除してよいと明示的に判断した場合だけ以下を使います。

```powershell
kind delete cluster --name workboard-lab
```

削除を実施した場合、専用 kubeconfig が残っていれば対象を確認してそのファイルだけを削除してから、構築スクリプトを実行します。他の kubeconfig は削除しません。作り直したクラスターは空の DB で始まります。Compose の volume は残ります。

## 完了条件

- [ ] Node が Ready、Web/API/DB の Deployment と Service が存在する。
- [ ] Deployment → ReplicaSet → Pod と label/selector の関係を説明できる。
- [ ] ブラウザーから CRUD・絞り込み・再読込を確認した。
- [ ] API Pod の削除後に新しい Pod が作られ、Service 経由の操作とデータ保持を確認した。
- [ ] マニフェストの再適用結果を観察した。
- [ ] 一時 DB のデータ寿命と migration の再実行方法を説明できる。
- [ ] 下記に結果・未実施の実験・設計課題への回答を記録した。

## 学習メモ

この表の `未記録` を自分の結果に置き換えます。実行していない実験は「省略」と理由を書きます。

| 項目 | 観察・結果 |
| --- | --- |
| 実行日・OS・シェル | 未記録 |
| kind / kubectl / Kubernetes バージョン | 未記録 |
| Node・Deployment・ReplicaSet・Pod の状態 | 未記録 |
| Service の selector と Pod label | 未記録 |
| 画面の CRUD・絞り込み・再読込 | 未記録 |
| API Pod 削除前後の名前・UID・IP | 未記録 |
| API Pod 削除後の Service とデータ | 未記録 |
| マニフェスト再適用 | 未記録 |
| DB 再作成と migration 再実行 | 未記録 |
| Compose との責任範囲の違い | 未記録 |
| 後片付け・残したクラスター | 未記録 |
| 疑問・未解決事項 | 未記録 |

### 設計課題への回答

1. Pod と Deployment の違い:
2. Service を使う理由:
3. selector と label が不一致の場合:
4. API Pod / DB Pod の削除とデータ:
5. 稼働後の状態を維持する主体:

## 実装時の検証記録

2026-11-08、Windows PowerShell 5.1、Docker Desktop の Linux エンジンで実装担当が確認しました。上の学習メモは学習者自身の記録欄です。

| 確認・コマンド | 結果 |
| --- | --- |
| `scripts/kind-install.ps1` | 公式 kind v0.33.0 を SHA-256 照合後に `.tools/kind.exe` へ導入 |
| PowerShell 3スクリプトの構文解析 | エラーなし、PowerShell 5.1 用 UTF-8 BOM を確認 |
| `scripts/kind-up.ps1` | Node v1.35.8 が Ready、全 Deployment が 1/1、migration が Completed |
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

Linux/macOS/WSL ホストでの実行と、クラスター全削除後の再構築は未実施です。既存 Compose のタスクは移行・削除していません。PVC・StatefulSet・ConfigMap/Secret・Ingress・AWS は今回追加していません。
