# Lab 03: 設定、機密情報、永続化

## 学習目標

- Namespace・ConfigMap・Secret で、環境依存の値をアプリのイメージとマニフェスト本体から分離する。
- Kustomize の base・component・overlay の役割を、`kubectl kustomize` の生成結果で確認する。
- StatefulSet・PVC・PV・StorageClass の関係を観察し、Pod を作り直した後のデータの残り方を確かめる。
- Secret が守る範囲と守らない範囲を、実際に読める経路から説明する。
- ConfigMap/Secret の変更が Pod にどう反映されるか、migration Job を安全に再実行する方法を説明する。

## 前提条件

Phase 2 の内容（Pod・Deployment・Service・Job）を理解していること。Linux コンテナエンジンが動く Docker（Windows / macOS は Docker Desktop、Linux は Docker Engine または Docker Desktop）、kubectl 1.34〜1.36、kind v0.33.0（導入は Phase 2 と共通の `tools/kind-install.ps1`。Bash は `tools/kind-install.sh`）。ノードは Kubernetes v1.35.8、DB は `postgres:17.11-bookworm` で、Phase 2 と同じ版です。AWS 費用はありません。

この Lab は **新しい kind クラスター `workboard-phase3`** で行います。Phase 2 の `workboard-lab`、その DB、`.kube/workboard-kind.yaml` は変更しません。この Phase のファイルは `phases/03-config-storage/` だけで完結し、kind のクラスター設定 `cluster.yaml` も Phase 2 のものとは別に持ちます（内容が同じなのは Phase を独立させるための意図的な重複です）。2 つのクラスターを同時に動かせますが、Docker のメモリ・ディスクの空きが追加で必要です。

ポートは Phase 2 の 8080 と衝突しないよう **8081** を使います。DB はダミーデータ専用で、Compose の DB/volume/`.env` は使いません。

## 設計課題（実装前に考える）

1. PostgreSQL をなぜ Deployment ではなく StatefulSet にするのか？
2. PVC は何を守り、何を守らないのか？
3. Kustomize の overlay は何を変え、何を生成しないのか？ テンプレートエンジンとは何が違うか？
4. Secret に値を置いただけで、何が保護され、何が保護されないのか？
5. ConfigMap/Secret の値を変更したとき、それを使う Pod はいつ新しい値を使い始めるのか？

## 実装タスク

1. [構成図](architecture.md)、[ADR-0005](../../docs/adr/0005-kubernetes-ecosystem-tools.md) の Kustomize の節を読む。
2. `phases/03-config-storage/kustomize/base`、`phases/03-config-storage/kustomize/components/postgres-local`、`phases/03-config-storage/kustomize/overlays/kind` を読み、どのファイルが何を担当しているかを書き出す。
3. `kubectl kustomize` で生成結果を確認してから、新しい専用クラスターへ適用する。
4. DB Pod を作り直してデータの残り方を観察し、設定変更と migration の再実行を試す。
5. 結果を **学習ポータルの学習メモ**（項目は「学習メモ」節）に記録する。

## 検証コマンド・期待結果

すべてリポジトリ直下で実行します。`-n` は Namespace、`--context` は操作対象クラスターの設定名です。この Lab の Kubernetes 操作は `kind-workboard-phase3` を指定します。`kind-workboard-lab`（Lab 02）に誤って操作しないよう、毎回 context を確認してください。

各コマンドは 1 つずつ実行します。コマンドの直前の「目的」で何のために打つかを、直後の「確認」で出力のどこを見るかを確かめてから、次のコマンドへ進みます。

### 1. 適用前に生成結果を読む

新しいターミナルごとに最初の行を実行します。`env.ps1`（Bash は `env.sh`。実行ではなく `source` で読み込みます）はこのシェルだけで Phase 3 用の kubeconfig（`.kube/workboard-phase3.yaml`）を使う設定です。Phase 2 の `env.ps1` / `env.sh` は従来どおり `workboard-lab` を指します。

目的：このシェルだけで Phase 3 用の kubeconfig を使う設定にして、以降の `kubectl` が `workboard-phase3` を向くようにします。

**Windows (PowerShell):**

```powershell
. .\phases\03-config-storage\scripts\env.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
source phases/03-config-storage/scripts/env.sh
```

確認：画面に出力は想定していません。エラーが出なければ設定済みです。Bash で `source` を付けずに実行すると `env.sh` は読み込み方を案内して終了します。その場合は `source` で読み込み直してください。

目的：`base` だけを生成して、環境に依存しない共通部分を適用前に読みます。

```text
kubectl kustomize phases/03-config-storage/kustomize/base
```

確認：出力に Namespace がなく、ConfigMap と Secret も存在しないことを見ます。Deployment は名前 `workboard-config`・`workboard-db` を参照するだけになっています。

目的：`overlay`（kind 用）を生成して、`base` に差分が重なった適用前の最終形を読みます。

```text
kubectl kustomize phases/03-config-storage/kustomize/overlays/kind
```

確認：`base` の出力と次の違いがあることを見ます。全リソースに `namespace: workboard` が付き、イメージが `workboard-api:kind` 等になり、`imagePullPolicy: Never` が加わります。ConfigMap と Secret の名前の末尾にハッシュが付き、Deployment・StatefulSet・Job の参照名も同じハッシュ付きの名前に書き換わっています。Secret の `data` は base64 で表示され、これは暗号化ではなくエンコードです。`secrets/db.env` が無いとここで読み込みに失敗します（次のコピーか、「2. 構築」のスクリプトで用意できます）。

目的：Secret の入力は Git 管理外の `phases/03-config-storage/kustomize/overlays/kind/secrets/db.env` です。まだ無い場合は「2. 構築」のスクリプトがローカル専用のランダムな値で作成しますが、自分で用意する場合は、このコマンドで例ファイルをコピーしてから値を変えます（例ファイルはダミー値のみで、実際の値は Git に入れません）。

**Windows (PowerShell):**

```powershell
Copy-Item phases/03-config-storage/kustomize/overlays/kind/secrets/db.env.example phases/03-config-storage/kustomize/overlays/kind/secrets/db.env
```

**Linux / macOS / WSL (Bash):**

```bash
cp phases/03-config-storage/kustomize/overlays/kind/secrets/db.env.example phases/03-config-storage/kustomize/overlays/kind/secrets/db.env
```

確認：エラーが出なければ `db.env` が作られています。コピーしただけではダミー値のままなので、エディターで自分の値に変えます。`db.env` は Git に入れません。

### 2. 構築

`kind-install.ps1`（Bash は `kind-install.sh`）は導入済みなら何もしません。Bash 版の `up.sh` は、`db.env` を `umask 077`（本人だけが読み書きできる権限）で、BOM なし・LF の1行として生成します。構築スクリプトは次の順で、固定秒数の sleep ではなく実際の状態を待ちます。

1. `workboard-phase3` クラスターの作成（存在しなければ）。同名クラスターのみ・kubeconfig のみ残っている場合は確認のため停止します。`workboard-lab` には何も適用しません。
2. 同じ API/Web Dockerfile のビルドと `kind load docker-image`（`imagePullPolicy: Never` のため投入忘れは `ErrImageNeverPull` になります）。
3. `db.env` が無ければ、ランダムなパスワードを生成して作成（値は表示しません）。既にあれば変更しません。
4. 完了済みの migration Job を削除し、`kubectl apply -k phases/03-config-storage/kustomize/overlays/kind`。
5. StatefulSet の準備完了待ち → migration Job の Complete 待ち → Web/API Deployment の準備完了待ち。

Job を毎回削除する理由は、Job の `spec.template` は作成後に変更できないためです。ConfigMap/Secret の名前はハッシュ付きで、内容を変えると Job の参照名も変わり、そのまま `apply` すると `field is immutable` で失敗します。Alembic の `upgrade head` は何度実行しても同じ結果になるため、削除して作り直しても安全です。Job の初期化コンテナは DB が接続可能になるまで待ち、Job の失敗回数を使い切らないようにしています。

スクリプトは既存のクラスター・PVC・DB を削除しません。再実行しても冪等で、タスクは残ります。

目的：kind が未導入なら導入します（導入済みなら何もしません）。Phase 2 と共通のスクリプトです。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File tools/kind-install.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash tools/kind-install.sh
```

確認：エラーが出ずに終了すれば完了です。導入済みの場合は何も変更されません。

目的：上の 1〜5 の構築（クラスター作成、イメージ投入、`apply -k`、準備完了待ち）を実行して、`workboard-phase3` に WorkBoard を作ります。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/03-config-storage/scripts/up.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/03-config-storage/scripts/up.sh
```

確認：エラーなく終了することを見ます。期待結果は、Node が Ready、StatefulSet が 1/1、PVC が Bound、migration Job が Completed、Web/API の Deployment が各 1 Pod です。Bash 版の `up.sh` は最後に Node と Pod などの一覧を表示し、「構築完了。」と出力します。

### 3. リソースと保存先を観察する

目的：Node が Ready か確認します。

```text
kubectl --context kind-workboard-phase3 get nodes
```

確認：STATUS が `Ready` であることを見ます。

目的：StorageClass の既定を確認します。マニフェストでは StorageClass を指定していないため、既定の StorageClass が使われます。

```text
kubectl --context kind-workboard-phase3 get storageclass
```

確認：既定の StorageClass に `default` の表示が付いていることを見ます。

目的：Phase 3 のリソース全体（Pod・StatefulSet・Deployment・Service・Job）の状態を一覧します。

```text
kubectl --context kind-workboard-phase3 -n workboard get pods,sts,deploy,svc,job -o wide
```

確認：DB の Pod 名が `workboard-postgres-0` で、Deployment のようなランダムなサフィックスではないことを見ます。StatefulSet が 1/1、Web/API の Deployment が各 1 Pod、migration Job が Completed であることも見ます。DB の Service が `CLUSTER-IP: None`（headless）であることも確認します。

目的：PVC と PV の状態と対応を確認します。PVC は Namespace に属し、PV はクラスター全体のオブジェクトです。

```text
kubectl --context kind-workboard-phase3 get pvc,pv -n workboard
```

確認：PVC の STATUS が `Bound` で、PV が PVC と対応していること、PV の RECLAIM POLICY を見ます。`-n workboard` は PV の一覧には効きません。

目的：PVC の詳細（StorageClass、バインド先の PV、イベント）を読みます。

```text
kubectl --context kind-workboard-phase3 -n workboard describe pvc data-workboard-postgres-0
```

確認：PVC の名前 `data-workboard-postgres-0` は、StatefulSet の `volumeClaimTemplates` から Pod ごとに作られた名前です。StorageClass が既定のものであること、Status が `Bound` であることを見ます。

目的：StatefulSet が PVC を作るときの元になる `volumeClaimTemplates` の定義を読みます。

```text
kubectl --context kind-workboard-phase3 -n workboard get statefulset workboard-postgres -o jsonpath='{.spec.volumeClaimTemplates[0].spec}'
```

確認：JSON が 1 行で表示されます。StorageClass を指定していない（既定が使われる）ことを、出力に StorageClass の指定が無いことで確かめます。

### 4. ConfigMap と Secret の参照を確認する

目的：ConfigMap と Secret が分かれて存在し、名前にハッシュが付いていることを確認します。

```text
kubectl --context kind-workboard-phase3 -n workboard get configmap,secret
```

確認：非機密値は ConfigMap、パスワードは Secret に分かれていること、どちらも名前の末尾にハッシュが付いていることを見ます。名前とハッシュは学習メモ用に控えます。

目的：ConfigMap の中身が非機密値だけであることを確認します。

```text
kubectl --context kind-workboard-phase3 -n workboard get configmap -o yaml
```

確認：`data` に `POSTGRES_HOST` などの接続先の値があり、パスワードが含まれていないことを見ます。

目的：API コンテナが ConfigMap の値を環境変数として受け取っているか確認します。ここではパスワードを画面に出す必要はないため、非機密の 3 つだけを指定します。

```text
kubectl --context kind-workboard-phase3 -n workboard exec deploy/workboard-api -- printenv POSTGRES_HOST POSTGRES_DB POSTGRES_USER
```

確認：3 つの値が 1 行ずつ表示されることを見ます。

目的：この kubeconfig の管理者が Secret を読めるか確認します。

```text
kubectl --context kind-workboard-phase3 -n workboard auth can-i get secrets
```

確認：`yes` と表示されることを見ます。Secret を読み取れる主体・`exec` できる主体・Secret を Pod に配る方法は、Secret の保護範囲に関わります。

目的：Namespace の `default` ServiceAccount が Secret を読めないことを確認します。

```text
kubectl --context kind-workboard-phase3 -n workboard auth can-i get secrets --as=system:serviceaccount:workboard:default
```

確認：`no` と表示されることを見ます。この kind クラスターに保存時暗号化を設定していないため、etcd での保存時の保護は確認の対象外（未検証）として記録してください。

### 5. ブラウザーで同じアプリを使う

目的：Web Service をホストの 8081 番へ転送して、ブラウザーから WorkBoard を使えるようにします。実行前に 8081 番が使われていないことを確認し、このコマンドは実行中のまま残して、ブラウザーと次の確認コマンドは別のターミナルで操作します。

```text
kubectl --context kind-workboard-phase3 -n workboard port-forward --address 127.0.0.1 svc/workboard-web 8081:80
```

確認：コマンドは終了せずに待機し続けます。[http://localhost:8081](http://localhost:8081) でダミータスク「永続化の学習」を作ります。Lab 02 の 8080 はそのまま使えます。8080 は `workboard-lab`、8081 は `workboard-phase3` を指しており、データも別です。

目的：別のターミナルで、Web 経由の API が準備完了か確認します。

**Windows (PowerShell):**

```powershell
curl.exe -i http://localhost:8081/health/ready
```

**Linux / macOS / WSL (Bash):**

```bash
curl -i http://localhost:8081/health/ready
```

確認：ステータス行が `200` であることを見ます。

目的：作成したタスクが API から返ることを確認します。

**Windows (PowerShell):**

```powershell
curl.exe -s http://localhost:8081/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -s http://localhost:8081/api/v1/tasks
```

確認：JSON に、作成したタスク「永続化の学習」が含まれることを見ます。

### 6. DB Pod を作り直してもデータが残るか

目的：新しいターミナルで作業する場合に備えて、このシェルが Phase 3 の kubeconfig を使うようにします。

**Windows (PowerShell):**

```powershell
. .\phases\03-config-storage\scripts\env.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
source phases/03-config-storage/scripts/env.sh
```

確認：画面に出力は想定していません。エラーが出なければよいです。

目的：削除する前の DB Pod の名前・UID・IP を記録します。

```text
kubectl --context kind-workboard-phase3 -n workboard get pod workboard-postgres-0 -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,IP:.status.podIP
```

確認：NAME が `workboard-postgres-0` であることを見て、UID と IP を控えます。削除後に比べるための値です。

目的：削除する前の PVC と PV の名前と状態を記録します。

```text
kubectl --context kind-workboard-phase3 get pvc,pv -n workboard
```

確認：PVC `data-workboard-postgres-0` が `Bound` であることを見て、PV の名前を控えます。

目的：DB Pod を削除して、StatefulSet に作り直させます。Lab 02 ではこの操作でタスクとスキーマが消えました。

```text
kubectl --context kind-workboard-phase3 -n workboard delete pod workboard-postgres-0
```

確認：`pod "workboard-postgres-0" deleted` と表示されます。削除すると元の UID を取得できなくなるため、直前の 2 つのコマンドの出力を必ず記録してから実行してください。

目的：StatefulSet が新しい Pod の準備完了まで進むのを待ちます。

```text
kubectl --context kind-workboard-phase3 -n workboard rollout status statefulset/workboard-postgres --timeout=180s
```

確認：待機が終わり、180 秒のタイムアウトで失敗しないことを見ます。

目的：作り直された DB Pod の名前・UID・IP を、削除前の記録と比べます。

```text
kubectl --context kind-workboard-phase3 -n workboard get pod workboard-postgres-0 -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,IP:.status.podIP
```

確認：名前は同じ `workboard-postgres-0` で、UID が削除前と変わっている（新しい Pod になった）ことを見ます。

目的：作り直し後の PVC と PV が削除前と同じか比べます。

```text
kubectl --context kind-workboard-phase3 get pvc,pv -n workboard
```

確認：PVC の名前と PV の名前が削除前と同じで、`Bound` のままであることを見ます。

目的：Pod を作り直してもタスクが残っているか確認します。

**Windows (PowerShell):**

```powershell
curl.exe -s http://localhost:8081/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -s http://localhost:8081/api/v1/tasks
```

確認：手順 5 で作ったタスクが返ることを見ます（Lab 02 では消えました）。API Pod の readiness が一時的に失敗する場合は戻るまで待ちます。port-forward が切れたら手順 5 を再実行します。

### 7. ConfigMap の変更が Pod にどう反映されるか

`phases/03-config-storage/kustomize/overlays/kind/kustomization.yaml` の `configMapGenerator` の `literals` に、アプリが読まないダミーの値 `- LAB_NOTE=v2` を追加します。保存前に、変更前の ConfigMap/Pod の状態を記録してください。

目的：変更前の ConfigMap の名前（ハッシュ）を記録します。

```text
kubectl --context kind-workboard-phase3 -n workboard get configmap
```

確認：現在の ConfigMap の名前を控えます。変更後に新しい名前と比べます。

目的：変更前の Pod の名前と AGE を記録します。

```text
kubectl --context kind-workboard-phase3 -n workboard get pods
```

確認：Pod の名前と AGE を控えます。変更後にどの Pod が作り直されたか比べます。

目的：`LAB_NOTE=v2` を追加して保存した状態の overlay を適用し、変更がどこへ波及するか観察します。

```text
kubectl --context kind-workboard-phase3 apply -k phases/03-config-storage/kustomize/overlays/kind
```

確認：Job の参照名が変わるため、`field is immutable` で Job だけ失敗します。エラーの文面を記録し、他のリソースがどう更新されたか（`created` / `configured` などの表示）も確認します。

目的：参照名が変わって更新できない migration Job を削除します。Alembic の `upgrade head` は何度実行しても同じ結果になるため、削除して作り直しても安全です。

```text
kubectl --context kind-workboard-phase3 -n workboard delete job workboard-migrate
```

確認：`job.batch "workboard-migrate" deleted` と表示されます。削除されるのは migration Job だけです。

目的：Job を作り直すため、もう一度 overlay を適用します。

```text
kubectl --context kind-workboard-phase3 apply -k phases/03-config-storage/kustomize/overlays/kind
```

確認：今度は `field is immutable` のエラーが出ず、Job が作られる（`created`）ことを見ます。

目的：作り直した migration Job が完了するまで待ちます。

```text
kubectl --context kind-workboard-phase3 -n workboard wait --for=condition=complete job/workboard-migrate --timeout=300s
```

確認：`condition met` と表示され、300 秒のタイムアウトで失敗しないことを見ます。

目的：変更後の ConfigMap の名前を、変更前の記録と比べます。

```text
kubectl --context kind-workboard-phase3 -n workboard get configmap
```

確認：新しい名前の ConfigMap が作られ、旧 ConfigMap が残っていることを見ます。参照されなくなった旧 ConfigMap は自動では消えません。

目的：変更後の Pod の名前と AGE を、変更前の記録と比べます。

```text
kubectl --context kind-workboard-phase3 -n workboard get pods
```

確認：Pod の名前が変わったか（作り直されたか）、DB の StatefulSet の Pod がどうなったかを見ます。`LAB_NOTE` が Pod の環境変数として見えるかは `exec ... -- printenv LAB_NOTE` で確かめます。

目的：ConfigMap の変更後もタスクが残っているか確認します。

**Windows (PowerShell):**

```powershell
curl.exe -s http://localhost:8081/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -s http://localhost:8081/api/v1/tasks
```

確認：タスクが返ることを見ます。観察が終わったら、`- LAB_NOTE=v2` の行を削除して同じ手順（Job を削除してから `apply -k`）で元に戻します。

### 8. 構築スクリプトの再実行（冪等性と migration の再実行）

目的：構築スクリプトを既存の環境に再実行して、冪等であること（既存クラスター・PVC を再利用し、`db.env` を上書きせず、Job を作り直す）を確かめます。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/03-config-storage/scripts/up.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/03-config-storage/scripts/up.sh
```

確認：エラーなく終了することを見ます。再適用時に StatefulSet が `configured` と表示されても、`kubectl -n workboard get controllerrevisions` の件数と DB Pod の AGE が変わらなければ Pod は作り直されていません。アプリのコードを変更した場合は、同じ `:kind` タグを再投入しても Pod が自動で変わらないため、Lab 02 と同様に `kubectl rollout restart deployment/workboard-api deployment/workboard-web` が別途必要です。

目的：作り直された migration Job の Alembic のログを読みます。

```text
kubectl --context kind-workboard-phase3 -n workboard logs job/workboard-migrate
```

確認：既に最新版のスキーマのため何も変更しなかったことを、ログから読み取れるか確認します。

目的：migration Job の状態を確認します。

```text
kubectl --context kind-workboard-phase3 -n workboard get job workboard-migrate
```

確認：Job が完了（Complete）していることを見ます。

目的：再実行後もタスクが残っているか確認します。

**Windows (PowerShell):**

```powershell
curl.exe -s http://localhost:8081/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -s http://localhost:8081/api/v1/tasks
```

確認：タスクが返ることを見ます。スクリプトは既存クラスター・PVC を再利用するため、タスクは残ります。

## 故障実験

**ダミータスクを失ってよいと確認できた場合だけ実行してください。** 対象は `workboard-phase3` だけで、`workboard-lab` には影響しません。

### A. StatefulSet を削除しても PVC は残る

目的：StatefulSet を削除して、PVC が StatefulSet とは独立して残るか確かめます。DB Pod も消えるため、DB はいったん使えなくなります。

```text
kubectl --context kind-workboard-phase3 -n workboard delete statefulset workboard-postgres
```

確認：`statefulset.apps "workboard-postgres" deleted` と表示されます。

目的：StatefulSet の削除中も PVC と PV が残っているか確認します。

```text
kubectl --context kind-workboard-phase3 get pvc,pv -n workboard
```

確認：PVC `data-workboard-postgres-0` と対応する PV が残り、`Bound` のままであることを見ます。

目的：overlay を再適用して、削除した StatefulSet を作り直します。

```text
kubectl --context kind-workboard-phase3 apply -k phases/03-config-storage/kustomize/overlays/kind
```

確認：StatefulSet が `created` と表示されることを見ます。

目的：再作成した StatefulSet の Pod が準備完了になるまで待ちます。

```text
kubectl --context kind-workboard-phase3 -n workboard rollout status statefulset/workboard-postgres --timeout=180s
```

確認：待機が終わり、180 秒のタイムアウトで失敗しないことを見ます。

目的：再作成した Pod が同じ PVC を使い、タスクが残っているか確認します。

**Windows (PowerShell):**

```powershell
curl.exe -s http://localhost:8081/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -s http://localhost:8081/api/v1/tasks
```

確認：削除前に作ったタスクが返ることを見ます。返れば、再作成した Pod が同じ PVC を使っています。

### B. PVC を削除するとデータはどうなるか

目的：PVC を削除する前に、PVC を使っている DB Pod を止めます。StatefulSet のレプリカ数を 0 にします。

```text
kubectl --context kind-workboard-phase3 -n workboard scale statefulset workboard-postgres --replicas=0
```

確認：`statefulset.apps/workboard-postgres scaled` と表示されます。

目的：PVC を削除して、DB のデータの保存先を失わせます。破壊的な操作で、ダミータスクが消えます。

```text
kubectl --context kind-workboard-phase3 -n workboard delete pvc data-workboard-postgres-0
```

確認：`persistentvolumeclaim "data-workboard-postgres-0" deleted` と表示されます。比較のため、削除前の PV の名前と RECLAIM POLICY（上の `get pvc,pv` の出力）を控えておきます。

目的：PVC を削除した後に、PV がどうなったかを確認します。

```text
kubectl --context kind-workboard-phase3 get pv
```

確認：PV の RECLAIM POLICY と、PVC 削除後の PV の有無を、削除前の記録と比べます。実装時の検証では、RECLAIM POLICY が `Delete` の PV は一時 `Released` になった後に消えました。

目的：構築スクリプトで StatefulSet を戻し、新しい PVC を作り、migration Job でスキーマだけを復旧します。タスクの復元ではありません。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/03-config-storage/scripts/up.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/03-config-storage/scripts/up.sh
```

確認：エラーなく終了し、新しい PVC と PV が作られて `Bound` になることを見ます。

目的：PVC を作り直した後のタスクの有無を確認します。

**Windows (PowerShell):**

```powershell
curl.exe -s http://localhost:8081/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -s http://localhost:8081/api/v1/tasks
```

確認：タスクが空であることを見ます（データは復元されません）。port-forward が切れていたら手順 5 を再実行します。

### C. Secret の値だけを変えるとどうなるか

DB のパスワードは、データ領域を最初に初期化したときの値で決まります。Secret の値を変えても、既存 DB のパスワードは変わりません。変更前に元の内容を保存し、必ず復元します。

目的：`db.env` のパスワードを書き換える対象のパスを、変数に入れます。

**Windows (PowerShell):**

```powershell
$secretFile = 'phases/03-config-storage/kustomize/overlays/kind/secrets/db.env'
```

**Linux / macOS / WSL (Bash):**

```bash
secret_file=phases/03-config-storage/kustomize/overlays/kind/secrets/db.env
```

確認：画面に出力は想定していません。エラーが出なければよいです。

目的：書き換える前の `db.env` の内容を変数に保存します。後で必ず復元するための控えです。

**Windows (PowerShell):**

```powershell
$original = [IO.File]::ReadAllText((Resolve-Path $secretFile))
```

**Linux / macOS / WSL (Bash):**

```bash
original=$(<"$secret_file")
```

確認：画面に出力は想定していません。エラーが出なければ、元の内容が変数に入っています。この変数が復元に必要なので、同じシェルを閉じないでください。

目的：BOM なしの UTF-8 を指定するエンコーディングを用意します。PowerShell 専用の準備で、Bash では不要です（`printf` は BOM を付けません）。PowerShell 5.1 の `Set-Content -Encoding UTF8` は BOM を付けるため、このファイルには使いません。

```powershell
$utf8 = New-Object Text.UTF8Encoding $false
```

確認：画面に出力は想定していません。エラーが出なければよいです。

目的：`db.env` を誤ったパスワードに書き換えます。ローカル専用のダミー値で、この後の手順で必ず復元します。

**Windows (PowerShell):**

```powershell
[IO.File]::WriteAllText((Resolve-Path $secretFile), "POSTGRES_PASSWORD=wrong-local-only`n", $utf8)
```

**Linux / macOS / WSL (Bash):**

```bash
printf 'POSTGRES_PASSWORD=wrong-local-only\n' > "$secret_file"
```

確認：画面に出力は想定していません。エラーが出なければ書き換わっています。復元用の `original` を失う前に、必ず後の復元手順まで進めてください。

目的：Secret の名前が変わると Job の参照名も変わるため、migration Job を先に削除します。

```text
kubectl --context kind-workboard-phase3 -n workboard delete job workboard-migrate
```

確認：`job.batch "workboard-migrate" deleted` と表示されます。

目的：誤った値の Secret を適用して、新しい Pod と Job の挙動を観察します。

```text
kubectl --context kind-workboard-phase3 apply -k phases/03-config-storage/kustomize/overlays/kind
```

確認：新しい名前の Secret が作られ、Deployment と Job がその Secret を参照するように更新されることを見ます。

目的：新しい API Pod の状態と、既存の API Pod が残っているか確認します。

```text
kubectl --context kind-workboard-phase3 -n workboard get pods
```

確認：新しい API Pod が DB にログインできるか、既存の API Pod が残る間の Service の応答はどうかを観察します。実装時の検証では、新しい API Pod は Ready にならず、旧 API Pod が応答を続けました。

目的：migration Job が DB にログインできるかをログで確認します。

```text
kubectl --context kind-workboard-phase3 -n workboard logs job/workboard-migrate -c migrate --tail=5
```

確認：`password authentication failed` が出ていれば、新しい値で DB にログインできていません（実装時の検証で確認した結果です）。

目的：`db.env` を元の内容に戻します。ここから先は復元の手順です。

**Windows (PowerShell):**

```powershell
[IO.File]::WriteAllText((Resolve-Path $secretFile), $original, $utf8)
```

**Linux / macOS / WSL (Bash):**

```bash
printf '%s\n' "$original" > "$secret_file"
```

確認：画面に出力は想定していません。エラーが出なければ、`db.env` が元の内容に戻っています。

目的：元の値で構築スクリプトを再実行して、Secret・Job・Pod を正常な状態に戻します。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/03-config-storage/scripts/up.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/03-config-storage/scripts/up.sh
```

確認：エラーなく終了し、API Pod が Ready に戻り、migration Job が Complete になることを見ます。

## 失敗時に確認すること

- `kubectl kustomize` が `secrets/db.env` を読めない: ファイルがあるか。`scripts/up.ps1` で生成するか、例ファイルからコピーしたか。
- 接続先が違う: `. .\phases\03-config-storage\scripts\env.ps1`（Bash は `source phases/03-config-storage/scripts/env.sh`）を読み込んだか。context が `kind-workboard-phase3` か。Phase 2 は `phases/02-kind-basics/scripts/` の `env.ps1` / `env.sh` を読み込む。
- PVC が `Pending`: `kubectl get storageclass` に既定の StorageClass があるか。`describe pvc` のイベントを読む。
- `ErrImageNeverPull`: `kind load docker-image ... --name workboard-phase3` が成功したか。
- Job の `Init` が終わらない: DB Pod が Ready か。`logs job/workboard-migrate -c wait-for-db` と Service 名・ConfigMap の `POSTGRES_HOST` を確認する。
- Job が `field is immutable` で更新できない: Job を削除してから `apply -k` する。
- API が Ready にならない: `logs deployment/workboard-api` の認証エラー。`db.env` が DB を初期化した値と一致しているか。
- Web から 502: Web の `API_HOST`（ConfigMap）と API Pod の準備状態を確認する。
- 8081 が使えない: 他のプロセスが使用中でないか確認し、解放できる場合だけ解放する。

## Linux / macOS / WSL での前提

スクリプトは PowerShell 版と同じ処理の Bash 版（`phases/03-config-storage/scripts/env.sh`・`up.sh`、導入は Phase 2 と共通の `tools/kind-install.sh`）があり、上の手順の「Linux / macOS / WSL (Bash)」に従います。Bash 4 以降、Docker（WSL は Docker Desktop の WSL 統合）、kubectl 1.34〜1.36 の条件は Phase 2 の「Linux / macOS / WSL での前提」と同じです。

## 後片付け・再構築

port-forward を実行しているターミナルで `Ctrl+C` を押すと入口だけが閉じます。クラスターとアプリは動き続けます。

`workboard-phase3` を削除すると、PVC/PV に保存した DB のデータも失われます。クラスター名と消えるデータを確認し、削除してよいと明示的に判断した場合だけ以下を使います。`workboard-lab` は対象外です。

目的：`workboard-phase3` クラスターを削除します。DB のデータも失われる破壊的な操作です。

```text
kind delete cluster --name workboard-phase3
```

確認：クラスター削除の完了メッセージが表示されます。削除後、専用 kubeconfig `.kube/workboard-phase3.yaml` が残っていれば対象を確認してそのファイルだけ削除します。`db.env` は残して再利用できます。**クラスター（PVC）を残したまま `db.env` を消さないでください。** 構築スクリプトが別のパスワードを生成し、初期化済みの DB と一致しなくなります。

## 完了条件

- [ ] `kubectl kustomize` の生成結果で、ハッシュ付きの名前、Namespace、イメージの変更、Secret の base64 を確認した。
- [ ] `workboard-phase3` で StatefulSet が 1/1、PVC が Bound、PV が対応し、migration Job が Completed になった。
- [ ] DB Pod の再作成後、同じ PVC を使い、ダミータスクが残ることを確認した。
- [ ] ConfigMap の変更が Pod に与える影響と、migration Job の再実行方法を観察した。
- [ ] Secret の保護範囲、確認できなかった点（保存時の保護など）を説明できる。
- [ ] 故障実験の実施・省略を記録した。
- [ ] 下記に結果・未実施の実験・設計課題への回答を記録した。
- [ ] 設計課題に答えた**後で** [ADR-0006（提案）](decisions/0006-kind-configuration-and-persistence.md) を読み、自分の回答と比べた。納得できたら ADR の Status を「採用」に変更し、異なる判断をした点は理由を学習ポータルの学習メモに残した。

## 学習メモ

観察結果と設計課題への回答は、この README ではなく**学習ポータルに入力します**（各自の PC の Git 管理外 `learning-portal/.data` にだけ保存され、リポジトリには残りません）。実行していない実験は「省略」と理由を書きます。記録する項目は次のとおりです。

- 実行日・OS・シェル
- kind / kubectl / Kubernetes バージョン
- kustomize の base と overlay の出力の違い
- ConfigMap / Secret の名前とハッシュ
- StorageClass・PVC・PV の状態
- DB Pod 再作成前後の名前・UID・PVC
- 再作成後のタスクの有無
- ConfigMap 変更時の Pod と Job の挙動
- 構築スクリプト再実行の結果
- 故障実験 A〜C の結果
- Secret の確認で分かったこと・未検証の点
- 後片付け・残したクラスター
- 疑問・未解決事項

## 実装時の検証記録

2026-11-10、Windows PowerShell 5.1、Docker Desktop の Linux エンジン、kubectl v1.34.1（Kustomize v5.7.1）で実装担当が確認しました。学習者自身の記録は README ではなく学習ポータルに残します。

| 確認・コマンド | 結果 |
| --- | --- |
| PowerShell 3スクリプトの構文解析 | エラーなし、UTF-8 BOM を維持 |
| `. .\phases\02-kind-basics\scripts\env.ps1` | KUBECONFIG は `.kube/workboard-kind.yaml`、クラスターは `workboard-lab`（従来どおり） |
| `kubectl kustomize phases/03-config-storage/kustomize/overlays/kind` | 成功。ConfigMap・Secret にハッシュ付き名、全リソースに namespace、`workboard-api:kind`、`imagePullPolicy: Never`（Postgres は `IfNotPresent`） |
| `phases/03-config-storage/scripts/up.ps1` | 新規に `workboard-phase3` を作成。Node Ready、StatefulSet 1/1、PVC Bound（StorageClass `standard`、RECLAIM `Delete`）、migration Job Complete、Web/API 1/1。`db.env` はランダム値を自動生成（値は出力しない） |
| DB Pod の削除 | `workboard-postgres-0` の UID が変わり、PVC/PV は同じ。作成したダミータスクは残った |
| 構築スクリプトの再実行 | 終了コード0。`db.env` は不変、Job を削除して再作成、タスクは残った。StatefulSet は `configured` と表示されたが ControllerRevision は増えず Pod は維持（表示の原因は未特定） |
| ConfigMap に `LAB_NOTE=v2` を追加して `apply -k` | 新しい名前の ConfigMap が作られ旧 ConfigMap は残存。Deployment・StatefulSet は新 Pod へ置換（DB Pod も再作成、ControllerRevision 2）。Job は `field is immutable` で失敗。Job 削除後に再適用で成功、タスクは残り `LAB_NOTE=v2` が Pod に反映 |
| 故障実験 A | StatefulSet 削除後も PVC/PV は Bound のまま。`apply -k` で同じ PVC を使い、タスクが残った |
| 故障実験 B | `scale --replicas=0` と PVC 削除で PV は一時 Released の後に消失。スクリプト再実行で新しい PVC/PV と migration、タスクは空 |
| 故障実験 C | 誤った値で新しい Secret 名が作られ、migration Job は `password authentication failed`。新 API Pod は Ready にならず、旧 API Pod が応答を継続。元の値へ戻して再実行で復旧 |
| `auth can-i get secrets` | 管理者 context は yes、`workboard:default` ServiceAccount は no |
| port-forward 8081 | health ready は 200。Lab 02 の 8080 とは別ポートで検証 |

保存時暗号化、etcd の保護、監査は検証していません（Secret の保護範囲として設計課題 4 の確認観点）。ネイティブ Linux、macOS、Docker Engine 単独での実行、クラスター全削除後の再構築、複数ノード、Lab 02 クラスター `workboard-lab` との同時稼働は未実施です。`workboard-lab` は検証開始時点で存在しなかったため、Phase 2 の既定パスは実行確認ではなくコード差分の確認のみです。AWS は使用していません。

2026-11-10、WSL2 Ubuntu（Docker Desktop の WSL 統合）で、既存の `workboard-phase3` に対し `phases/03-config-storage/scripts/up.sh` を実行して冪等に成功しました（クラスターと PVC は維持、DB Pod は再作成されず、migration Job は Complete、API/Web は 1/1）。
