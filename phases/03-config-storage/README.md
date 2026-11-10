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

### 1. 適用前に生成結果を読む

新しいターミナルごとに最初の行を実行します。`env.ps1`（Bash は `env.sh`。実行ではなく `source` で読み込みます）はこのシェルだけで Phase 3 用の kubeconfig（`.kube/workboard-phase3.yaml`）を使う設定です。Phase 2 の `env.ps1` / `env.sh` は従来どおり `workboard-lab` を指します。

**Windows (PowerShell):**

```powershell
. .\phases\03-config-storage\scripts\env.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
source phases/03-config-storage/scripts/env.sh
```

```text
kubectl kustomize phases/03-config-storage/kustomize/base
kubectl kustomize phases/03-config-storage/kustomize/overlays/kind
```

Secret の入力は Git 管理外の `phases/03-config-storage/kustomize/overlays/kind/secrets/db.env` です。まだ無い場合、次の「2. 構築」のスクリプトがローカル専用のランダムな値で作成します。自分で用意する場合は、次で例ファイルをコピーして値を変えます（例ファイルはダミー値のみで、実際の値は Git に入れません）。

**Windows (PowerShell):**

```powershell
Copy-Item phases/03-config-storage/kustomize/overlays/kind/secrets/db.env.example phases/03-config-storage/kustomize/overlays/kind/secrets/db.env
```

**Linux / macOS / WSL (Bash):**

```bash
cp phases/03-config-storage/kustomize/overlays/kind/secrets/db.env.example phases/03-config-storage/kustomize/overlays/kind/secrets/db.env
```

観察する点は以下です。

- `base` の出力には Namespace がなく、ConfigMap/Secret も存在しません。Deployment は名前 `workboard-config`・`workboard-db` を参照するだけです。
- `overlay` の出力では、全リソースに `namespace: workboard` が付き、イメージが `workboard-api:kind` 等になり、`imagePullPolicy: Never` が加わります。
- ConfigMap と Secret の名前の末尾にハッシュが付き、Deployment・StatefulSet・Job の参照名も同じハッシュ付きの名前に書き換わっています。
- Secret の `data` は base64 で表示されます。これは暗号化ではなくエンコードです。

### 2. 構築

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File tools/kind-install.ps1
powershell -NoProfile -File phases/03-config-storage/scripts/up.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash tools/kind-install.sh
bash phases/03-config-storage/scripts/up.sh
```

`kind-install.ps1`（Bash は `kind-install.sh`）は導入済みなら何もしません。Bash 版の `up.sh` は、`db.env` を `umask 077`（本人だけが読み書きできる権限）で、BOM なし・LF の1行として生成します。構築スクリプトは次の順で、固定秒数の sleep ではなく実際の状態を待ちます。

1. `workboard-phase3` クラスターの作成（存在しなければ）。同名クラスターのみ・kubeconfig のみ残っている場合は確認のため停止します。`workboard-lab` には何も適用しません。
2. 同じ API/Web Dockerfile のビルドと `kind load docker-image`（`imagePullPolicy: Never` のため投入忘れは `ErrImageNeverPull` になります）。
3. `db.env` が無ければ、ランダムなパスワードを生成して作成（値は表示しません）。既にあれば変更しません。
4. 完了済みの migration Job を削除し、`kubectl apply -k phases/03-config-storage/kustomize/overlays/kind`。
5. StatefulSet の準備完了待ち → migration Job の Complete 待ち → Web/API Deployment の準備完了待ち。

Job を毎回削除する理由は、Job の `spec.template` は作成後に変更できないためです。ConfigMap/Secret の名前はハッシュ付きで、内容を変えると Job の参照名も変わり、そのまま `apply` すると `field is immutable` で失敗します。Alembic の `upgrade head` は何度実行しても同じ結果になるため、削除して作り直しても安全です。Job の初期化コンテナは DB が接続可能になるまで待ち、Job の失敗回数を使い切らないようにしています。

スクリプトは既存のクラスター・PVC・DB を削除しません。再実行しても冪等で、タスクは残ります。

期待結果は、Node が Ready、StatefulSet が 1/1、PVC が Bound、migration Job が Completed、Web/API の Deployment が各 1 Pod です。

### 3. リソースと保存先を観察する

```text
kubectl --context kind-workboard-phase3 get nodes
kubectl --context kind-workboard-phase3 get storageclass
kubectl --context kind-workboard-phase3 -n workboard get pods,sts,deploy,svc,job -o wide
kubectl --context kind-workboard-phase3 get pvc,pv -n workboard
kubectl --context kind-workboard-phase3 -n workboard describe pvc data-workboard-postgres-0
kubectl --context kind-workboard-phase3 -n workboard get statefulset workboard-postgres -o jsonpath='{.spec.volumeClaimTemplates[0].spec}'
```

StorageClass の既定（`default` の表示）、PVC の STATUS が `Bound`、PV が PVC と対応していること、PV の RECLAIM POLICY を確認します。PVC は Namespace に属し、PV はクラスター全体のオブジェクトです（`-n workboard` は PV の一覧には効きません）。マニフェストでは StorageClass を指定していないため、既定の StorageClass が使われます。PVC は StatefulSet の `volumeClaimTemplates` から Pod ごとに作られた名前（`data-workboard-postgres-0`）です。Pod の名前は `workboard-postgres-0` で、Deployment のようなランダムなサフィックスではありません。DB の Service が `CLUSTER-IP: None`（headless）であることも見ます。

### 4. ConfigMap と Secret の参照を確認する

```text
kubectl --context kind-workboard-phase3 -n workboard get configmap,secret
kubectl --context kind-workboard-phase3 -n workboard get configmap -o yaml
kubectl --context kind-workboard-phase3 -n workboard exec deploy/workboard-api -- printenv POSTGRES_HOST POSTGRES_DB POSTGRES_USER
kubectl --context kind-workboard-phase3 -n workboard auth can-i get secrets
kubectl --context kind-workboard-phase3 -n workboard auth can-i get secrets --as=system:serviceaccount:workboard:default
```

非機密値は ConfigMap、パスワードは Secret に分かれています。この kubeconfig の管理者は Secret を読めますが、Namespace の `default` ServiceAccount は読めないことを `can-i` で確認します。Secret を読み取れる主体・`exec` できる主体・Secret を Pod に配る方法は、Secret の保護範囲に関わります。ここではパスワードを画面に出す必要はありません。この kind クラスターに保存時暗号化を設定していないため、etcd での保存時の保護は確認の対象外（未検証）として記録してください。

### 5. ブラウザーで同じアプリを使う

8081 番が使われていないことを確認し、次のコマンドを実行中のまま残してブラウザーを別に開きます。

```text
kubectl --context kind-workboard-phase3 -n workboard port-forward --address 127.0.0.1 svc/workboard-web 8081:80
```

[http://localhost:8081](http://localhost:8081) でダミータスク「永続化の学習」を作ります。別のターミナルで次の確認もできます。

**Windows (PowerShell):**

```powershell
curl.exe -i http://localhost:8081/health/ready
curl.exe -s http://localhost:8081/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -i http://localhost:8081/health/ready
curl -s http://localhost:8081/api/v1/tasks
```

Lab 02 の 8080 はそのまま使えます。8080 は `workboard-lab`、8081 は `workboard-phase3` を指しており、データも別です。

### 6. DB Pod を作り直してもデータが残るか

**Windows (PowerShell):**

```powershell
. .\phases\03-config-storage\scripts\env.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
source phases/03-config-storage/scripts/env.sh
```

```text
kubectl --context kind-workboard-phase3 -n workboard get pod workboard-postgres-0 -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,IP:.status.podIP
kubectl --context kind-workboard-phase3 get pvc,pv -n workboard
kubectl --context kind-workboard-phase3 -n workboard delete pod workboard-postgres-0
kubectl --context kind-workboard-phase3 -n workboard rollout status statefulset/workboard-postgres --timeout=180s
kubectl --context kind-workboard-phase3 -n workboard get pod workboard-postgres-0 -o custom-columns=NAME:.metadata.name,UID:.metadata.uid,IP:.status.podIP
kubectl --context kind-workboard-phase3 get pvc,pv -n workboard
```

**Windows (PowerShell):**

```powershell
curl.exe -s http://localhost:8081/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -s http://localhost:8081/api/v1/tasks
```

Lab 02 では DB Pod の削除でタスクとスキーマが消えました。ここでは Pod の名前と PVC の名前、削除前後の UID、タスクの有無を比較します。API Pod の readiness が一時的に失敗する場合は戻るまで待ち、port-forward が切れたら手順 5 を再実行します。

### 7. ConfigMap の変更が Pod にどう反映されるか

`phases/03-config-storage/kustomize/overlays/kind/kustomization.yaml` の `configMapGenerator` の `literals` に、アプリが読まないダミーの値 `- LAB_NOTE=v2` を追加します。保存前に、変更前の ConfigMap/Pod の状態を記録してください。

```text
kubectl --context kind-workboard-phase3 -n workboard get configmap
kubectl --context kind-workboard-phase3 -n workboard get pods
kubectl --context kind-workboard-phase3 apply -k phases/03-config-storage/kustomize/overlays/kind
```

`apply` は Job の参照名が変わるため、`field is immutable` で Job だけ失敗します。観察したらエラーの文面を記録し、他のリソースがどう更新されたかも確認します。

```text
kubectl --context kind-workboard-phase3 -n workboard delete job workboard-migrate
kubectl --context kind-workboard-phase3 apply -k phases/03-config-storage/kustomize/overlays/kind
kubectl --context kind-workboard-phase3 -n workboard wait --for=condition=complete job/workboard-migrate --timeout=300s
kubectl --context kind-workboard-phase3 -n workboard get configmap
kubectl --context kind-workboard-phase3 -n workboard get pods
```

**Windows (PowerShell):**

```powershell
curl.exe -s http://localhost:8081/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -s http://localhost:8081/api/v1/tasks
```

観察する点は、ConfigMap が新しい名前で作られ旧 ConfigMap が残ること、Pod の名前・作り直し、DB の StatefulSet がどうなったか、タスクが残ること、`LAB_NOTE` が Pod の環境変数として見えるかです（`exec ... -- printenv LAB_NOTE`）。確認後、`- LAB_NOTE=v2` の行を削除して同じ手順（Job を削除してから `apply -k`）で元に戻します。参照されなくなった旧 ConfigMap は自動では消えません。

### 8. 構築スクリプトの再実行（冪等性と migration の再実行）

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/03-config-storage/scripts/up.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/03-config-storage/scripts/up.sh
```

```text
kubectl --context kind-workboard-phase3 -n workboard logs job/workboard-migrate
kubectl --context kind-workboard-phase3 -n workboard get job workboard-migrate
```

**Windows (PowerShell):**

```powershell
curl.exe -s http://localhost:8081/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -s http://localhost:8081/api/v1/tasks
```

スクリプトは既存クラスター・PVC を再利用し、`db.env` を上書きせず、Job を作り直します。再適用時に StatefulSet が `configured` と表示されても、`kubectl -n workboard get controllerrevisions` の件数と DB Pod の AGE が変わらなければ Pod は作り直されていません。Alembic のログから、既に最新版のスキーマのため何も変更しなかったことを読み取れるか確認します。タスクは残ります。アプリのコードを変更した場合は、同じ `:kind` タグを再投入しても Pod が自動で変わらないため、Lab 02 と同様に `kubectl rollout restart deployment/workboard-api deployment/workboard-web` が別途必要です。

## 故障実験

**ダミータスクを失ってよいと確認できた場合だけ実行してください。** 対象は `workboard-phase3` だけで、`workboard-lab` には影響しません。

### A. StatefulSet を削除しても PVC は残る

```text
kubectl --context kind-workboard-phase3 -n workboard delete statefulset workboard-postgres
kubectl --context kind-workboard-phase3 get pvc,pv -n workboard
kubectl --context kind-workboard-phase3 apply -k phases/03-config-storage/kustomize/overlays/kind
kubectl --context kind-workboard-phase3 -n workboard rollout status statefulset/workboard-postgres --timeout=180s
```

**Windows (PowerShell):**

```powershell
curl.exe -s http://localhost:8081/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -s http://localhost:8081/api/v1/tasks
```

StatefulSet の削除中も PVC/PV が残るか、再作成した Pod が同じ PVC を使い、タスクが残るかを確認します。

### B. PVC を削除するとデータはどうなるか

```text
kubectl --context kind-workboard-phase3 -n workboard scale statefulset workboard-postgres --replicas=0
kubectl --context kind-workboard-phase3 -n workboard delete pvc data-workboard-postgres-0
kubectl --context kind-workboard-phase3 get pv
```

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/03-config-storage/scripts/up.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/03-config-storage/scripts/up.sh
```

**Windows (PowerShell):**

```powershell
curl.exe -s http://localhost:8081/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -s http://localhost:8081/api/v1/tasks
```

PV の RECLAIM POLICY と、PVC 削除後の PV の有無を比較します。構築スクリプトが StatefulSet を戻して新しい PVC を作り、migration Job でスキーマだけを復旧します。タスクの復元ではありません。port-forward が切れていたら手順 5 を再実行します。

### C. Secret の値だけを変えるとどうなるか

DB のパスワードは、データ領域を最初に初期化したときの値で決まります。Secret の値を変えても、既存 DB のパスワードは変わりません。変更前に元の内容を保存し、必ず復元します。

**Windows (PowerShell):**

```powershell
$secretFile = 'phases/03-config-storage/kustomize/overlays/kind/secrets/db.env'
$original = [IO.File]::ReadAllText((Resolve-Path $secretFile))
$utf8 = New-Object Text.UTF8Encoding $false
[IO.File]::WriteAllText((Resolve-Path $secretFile), "POSTGRES_PASSWORD=wrong-local-only`n", $utf8)
```

**Linux / macOS / WSL (Bash):**

```bash
secret_file=phases/03-config-storage/kustomize/overlays/kind/secrets/db.env
original=$(<"$secret_file")
printf 'POSTGRES_PASSWORD=wrong-local-only\n' > "$secret_file"
```

```text
kubectl --context kind-workboard-phase3 -n workboard delete job workboard-migrate
kubectl --context kind-workboard-phase3 apply -k phases/03-config-storage/kustomize/overlays/kind
kubectl --context kind-workboard-phase3 -n workboard get pods
kubectl --context kind-workboard-phase3 -n workboard logs job/workboard-migrate -c migrate --tail=5
```

新しい API Pod と migration Job が DB にログインできるか、既存の API Pod が残る間の Service の応答はどうかを観察します。戻すときは次を実行します。

**Windows (PowerShell):**

```powershell
[IO.File]::WriteAllText((Resolve-Path $secretFile), $original, $utf8)
powershell -NoProfile -File phases/03-config-storage/scripts/up.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
printf '%s\n' "$original" > "$secret_file"
bash phases/03-config-storage/scripts/up.sh
```

PowerShell 5.1 の `Set-Content -Encoding UTF8` は BOM を付けるため、このファイルには使いません。

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

```text
kind delete cluster --name workboard-phase3
```

削除後、専用 kubeconfig `.kube/workboard-phase3.yaml` が残っていれば対象を確認してそのファイルだけ削除します。`db.env` は残して再利用できます。**クラスター（PVC）を残したまま `db.env` を消さないでください。** 構築スクリプトが別のパスワードを生成し、初期化済みの DB と一致しなくなります。

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
