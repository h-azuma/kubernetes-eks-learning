# Lab 05: セキュリティ、障害調査、運用

## 学習目標

- Pod Security Standards、securityContext、ServiceAccount、RBAC、NetworkPolicy が、それぞれ何を制限し、何を制限しないかを説明する。
- NetworkPolicy の効果を、対応する CNI を導入したうえで、通信の**許可と拒否の両方**を実測して確認する。
- 非 root 実行・読み取り専用のルートファイルシステム・不要な権限の削除を、WorkBoard の 3 つのワークロードで確かめる。
- 意図的に作った 6 種類の障害を、`kubectl describe` / `logs` / `events` / EndpointSlice / `auth can-i` で調査し、復旧する。
- 調査の手順を Runbook にまとめ、再発防止策を説明する。

## 前提条件

Phase 3 の内容（Namespace・ConfigMap・Secret・StatefulSet・Kustomize）を理解していること。Linux コンテナエンジンが動く Docker（Windows / macOS は Docker Desktop、Linux は Docker Engine または Docker Desktop）、kubectl 1.34〜1.36、kind v0.33.0（導入は Phase 2 と共通の `tools/kind-install.ps1`。Bash は `tools/kind-install.sh`）。ノードは Kubernetes v1.35.8、DB は `postgres:17.11-bookworm`、CNI は Calico v3.33.0（構築スクリプトが導入します。イメージの取得にインターネット接続が必要です）。AWS 費用はありません。

この Lab は **新しい kind クラスター `workboard-phase5`** で行います。ほかの Lab のクラスター（`workboard-lab`、`workboard-phase3` など）とその DB、`.kube/` の既存ファイルは変更しません。この Phase のファイルは `phases/05-security-and-failure/` だけで完結し、kind の `cluster.yaml` やマニフェストは Phase 3 と別に持ちます（内容が重複するのは Phase を独立させるための意図的な重複です）。複数のクラスターを同時に動かすには Docker のメモリ・ディスクの空きが追加で必要です。

ポートは 8080〜8082 と衝突しないよう **8083** を使います。DB はダミーデータ専用で、Compose の DB/volume/`.env` は使いません。

## 設計課題（実装前に考える）

1. Kubernetes の Secret のセキュリティ境界はどこにあるのか？ 誰が値を読め、何が保護されないのか？
2. 誰が Kubernetes API を操作できるべきか？ 人、アプリの Pod、調査用のツールで、必要な権限はどう違うか？
3. k9s のような TUI を使っても、操作できる範囲は何で決まるのか？ RBAC とはどういう関係か？
4. Pod Security Standards の `enforce`・`warn`・`audit` をどう使い分けるか？ `restricted` を `enforce` にする条件は何か？
5. 非 root 実行と読み取り専用のルートファイルシステムで、何が防げて何が防げないのか？ Web イメージを変更するか、マニフェストで補うかをどう判断するか？
6. NetworkPolicy の効果は、どんな条件で、どんな実験によって確かめられるのか？ 対応しない CNI のとき何が起きるか？
7. Pod が Ready なのに通信できないとき、どんな順序で原因を切り分けるか？

## 実装タスク

1. [構成図](architecture.md)、[Runbook](runbook.md)、[ADR-0005](../../docs/adr/0005-kubernetes-ecosystem-tools.md) の k9s の節を読む。
2. `phases/05-security-and-failure/kustomize/base`、`kustomize/components/postgres-local`、`kustomize/overlays/kind` を読み、Phase 3 から何が増えたか（ServiceAccount、securityContext、リソース制限、Role、NetworkPolicy、Namespace のラベル）を書き出す。
3. `kubectl kustomize` で生成結果を確認してから、新しい専用クラスターへ適用する。
4. Pod Security の拒否、RBAC の許可と拒否、NetworkPolicy の許可と拒否を実測する。
5. 故障実験 A〜F を実行し、Runbook に沿って調査・復旧する。
6. 結果を **学習ポータルの学習メモ**（項目は「学習メモ」節）に記録する。

## 検証コマンド・期待結果

すべてリポジトリ直下で実行します。`-n` は Namespace、`--context` は操作対象クラスターの設定名です。この Lab の Kubernetes 操作は `kind-workboard-phase5` を指定します。ほかのクラスターに誤って操作しないよう、毎回 context を確認してください。

### 1. 適用前に生成結果を読む

新しいターミナルごとに最初の行を実行します。`env.ps1`（Bash は `env.sh`。実行ではなく `source` で読み込みます）はこのシェルだけで Phase 5 用の kubeconfig（`.kube/workboard-phase5.yaml`）を使う設定です。

**Windows (PowerShell):**

```powershell
. .\phases\05-security-and-failure\scripts\env.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
source phases/05-security-and-failure/scripts/env.sh
```

```text
kubectl kustomize phases/05-security-and-failure/kustomize/base
kubectl kustomize phases/05-security-and-failure/kustomize/overlays/kind
```

Secret の入力は Git 管理外の `phases/05-security-and-failure/kustomize/overlays/kind/secrets/db.env` です。まだ無い場合、次の「2. 構築」のスクリプトがローカル専用のランダムな値で作成します。自分で用意する場合は、次で例ファイルをコピーして値を変えます（例ファイルはダミー値のみで、実際の値は Git に入れません）。

**Windows (PowerShell):**

```powershell
Copy-Item phases/05-security-and-failure/kustomize/overlays/kind/secrets/db.env.example phases/05-security-and-failure/kustomize/overlays/kind/secrets/db.env
```

**Linux / macOS / WSL (Bash):**

```bash
cp phases/05-security-and-failure/kustomize/overlays/kind/secrets/db.env.example phases/05-security-and-failure/kustomize/overlays/kind/secrets/db.env
```

観察する点は以下です。

- Namespace に `pod-security.kubernetes.io/enforce`・`warn`・`audit` のラベルがあります。
- Web・API・migrate・PostgreSQL ごとに別の ServiceAccount があり、`automountServiceAccountToken: false` です。
- 各コンテナに `securityContext`（`allowPrivilegeEscalation: false`、`capabilities.drop: [ALL]`、`readOnlyRootFilesystem: true`）と `resources` があります。書き込み先は emptyDir です。
- `Role`/`RoleBinding` の `workboard-viewer` に Secret が含まれるか、NetworkPolicy が何を許可しているかを読みます。

### 2. 構築

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File tools/kind-install.ps1
powershell -NoProfile -File phases/05-security-and-failure/scripts/up.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash tools/kind-install.sh
bash phases/05-security-and-failure/scripts/up.sh
```

`kind-install.ps1`（Bash は `kind-install.sh`）は導入済みなら何もしません。構築スクリプトは次の順で、固定秒数の sleep ではなく実際の状態を待ちます。

1. `workboard-phase5` クラスターの作成（存在しなければ）。`cluster.yaml` で kind の既定 CNI を無効にしているため、`--wait` なしで作成します（CNI がないと Node が Ready にならないため）。同名クラスターのみ・kubeconfig のみ残っている場合は確認のため停止します。
2. Calico v3.33.0 の導入（`kubectl create`）と、`calico-node`・`calico-kube-controllers`・Node・CoreDNS の準備完了待ち。
3. API/Web の Dockerfile のビルドと `kind load docker-image`。
4. `db.env` が無ければランダムなパスワードを生成（値は表示しません）。あれば変更しません。
5. 完了済みの migration Job を削除し、`kubectl apply -k phases/05-security-and-failure/kustomize/overlays/kind`。
6. StatefulSet → migration Job → Web/API Deployment の準備完了待ち。

スクリプトは既存のクラスター・PVC・DB を削除しません。再実行しても冪等です。期待結果は、Node が Ready、Calico が Running、StatefulSet が 1/1、migration Job が Completed、Web/API の Deployment が各 1 Pod、NetworkPolicy が 7 個です。

### 3. CNI と実行ユーザーを観察する

```text
kubectl --context kind-workboard-phase5 get nodes
kubectl --context kind-workboard-phase5 -n kube-system get pods -l k8s-app=calico-node
kubectl --context kind-workboard-phase5 -n workboard get pods -o wide
kubectl --context kind-workboard-phase5 -n workboard exec deploy/workboard-web -- id
kubectl --context kind-workboard-phase5 -n workboard exec deploy/workboard-api -- id
kubectl --context kind-workboard-phase5 -n workboard exec statefulset/workboard-postgres -- id
kubectl --context kind-workboard-phase5 -n workboard exec deploy/workboard-web -- sh -c 'touch /usr/share/nginx/html/x'
kubectl --context kind-workboard-phase5 -n workboard exec deploy/workboard-web -- sh -c 'touch /tmp/x && echo written'
kubectl --context kind-workboard-phase5 -n workboard get pod -l app=workboard-api -o jsonpath='{.items[0].spec.automountServiceAccountToken}{"\n"}'
```

Web・API・PostgreSQL が root ではなく、それぞれ異なる UID で動くこと、emptyDir 以外には書き込めないこと、Pod に ServiceAccount のトークンが自動では入っていないことを確認します。`kubectl get ... -o yaml` で `securityContext` の実際の値も読みます。

### 4. Pod Security Standards の拒否を確かめる

```text
kubectl --context kind-workboard-phase5 get namespace workboard --show-labels
kubectl --context kind-workboard-phase5 -n workboard apply -f phases/05-security-and-failure/experiments/violating-pod.yaml
kubectl --context kind-workboard-phase5 -n workboard get pod violating
```

特権コンテナ・root 実行などの違反を含む Pod は `Forbidden: violates PodSecurity "restricted:v1.35"` で作成が拒否され、違反項目がすべて列挙されます。Pod は作られません。同じ内容を Deployment にした場合に何が起きるか（Deployment は受理され、`warn` の警告と ReplicaSet のイベントで気づくか）を、公式資料で確認してから予想し、必要なら自分で試します。

### 5. ServiceAccount と RBAC を確かめる

`workboard-viewer` は Pod には使わず、`--as` で権限を試すための学習用の主体です。

```text
kubectl --context kind-workboard-phase5 -n workboard get role,rolebinding,serviceaccount
kubectl --context kind-workboard-phase5 -n workboard describe role workboard-viewer
kubectl --context kind-workboard-phase5 -n workboard auth can-i get pods --as=system:serviceaccount:workboard:workboard-viewer
kubectl --context kind-workboard-phase5 -n workboard auth can-i get pods/log --as=system:serviceaccount:workboard:workboard-viewer
kubectl --context kind-workboard-phase5 -n workboard auth can-i get secrets --as=system:serviceaccount:workboard:workboard-viewer
kubectl --context kind-workboard-phase5 -n workboard auth can-i delete pods --as=system:serviceaccount:workboard:workboard-viewer
kubectl --context kind-workboard-phase5 -n kube-system auth can-i get pods --as=system:serviceaccount:workboard:workboard-viewer
kubectl --context kind-workboard-phase5 -n workboard auth can-i get pods --as=system:serviceaccount:workboard:default
kubectl --context kind-workboard-phase5 -n workboard get secrets --as=system:serviceaccount:workboard:workboard-viewer
kubectl --context kind-workboard-phase5 -n workboard auth can-i --list --as=system:serviceaccount:workboard:workboard-viewer
```

許可（`yes`）と拒否（`no`）の両方を表にまとめます。拒否は `Forbidden` のエラー文に、主体・動詞・リソース・Namespace が書かれます。Role は Namespace 内だけで、`kube-system` や `default` ServiceAccount には効かないことを確認します。

### 6. NetworkPolicy の許可と拒否を確かめる

最初に、遮断を行うのは NetworkPolicy ではなく CNI であること、この環境の CNI が Calico であることを確認します。

```text
kubectl --context kind-workboard-phase5 -n workboard get networkpolicy
kubectl --context kind-workboard-phase5 -n workboard describe networkpolicy default-deny-all api-traffic postgres-ingress
```

許可されるべき通信（成功する）:

```text
kubectl --context kind-workboard-phase5 -n workboard exec deploy/workboard-web -- wget -qO- -T 3 http://workboard-api:8000/health/ready
kubectl --context kind-workboard-phase5 -n workboard exec deploy/workboard-api -- python -c "import socket;socket.create_connection(('workboard-postgres',5432),3);print('connected')"
```

拒否されるべき通信（失敗する。`Connection refused` ではなくタイムアウトになる点を見ます）:

```text
kubectl --context kind-workboard-phase5 -n workboard exec deploy/workboard-web -- nc -zv -w 3 workboard-postgres 5432
kubectl --context kind-workboard-phase5 -n workboard exec deploy/workboard-api -- python -c "import socket;socket.create_connection(('workboard-web',80),3)"
```

どのポリシーにも一致しない新しい Pod（`probe`）は、名前解決はできるのに DB へ接続できません。

```text
kubectl --context kind-workboard-phase5 -n workboard apply -f phases/05-security-and-failure/experiments/probe-pod.yaml
kubectl --context kind-workboard-phase5 -n workboard wait --for=condition=Ready pod/probe --timeout=90s
kubectl --context kind-workboard-phase5 -n workboard exec probe -- getent hosts workboard-postgres
kubectl --context kind-workboard-phase5 -n workboard exec probe -- pg_isready -h workboard-postgres -p 5432 -t 3
```

許可された通信が成功し、許可されていない通信が失敗したときだけ、NetworkPolicy が効いていると判断します。作成に成功しただけでは判断できません。確認後の `probe` は `kubectl -n workboard delete pod probe` で削除します。

### 7. ブラウザーで同じアプリを使う

8083 番が使われていないことを確認し、次のコマンドを実行中のまま残してブラウザーを別に開きます。

```text
kubectl --context kind-workboard-phase5 -n workboard port-forward --address 127.0.0.1 svc/workboard-web 8083:80
```

[http://localhost:8083](http://localhost:8083) でダミータスクを作ります。別のターミナルで次の確認もできます。

**Windows (PowerShell):**

```powershell
curl.exe -i http://localhost:8083/health/ready
curl.exe -s http://localhost:8083/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -i http://localhost:8083/health/ready
curl -s http://localhost:8083/api/v1/tasks
```

default deny の NetworkPolicy があっても port-forward で画面を開けること、その理由を考えます。

### 8. 安全なダミー負荷を生成する

`experiments/loadgen-job.yaml` は、同じ Namespace の `workboard-web` だけに、2 並列 × 50 回（計 100 回）の GET を間隔 0.2 秒で送る Job です。回数・並列度は固定で、外部には送りません。

```text
kubectl --context kind-workboard-phase5 -n workboard apply -f phases/05-security-and-failure/experiments/loadgen-job.yaml
kubectl --context kind-workboard-phase5 -n workboard wait --for=condition=complete job/workboard-loadgen --timeout=120s
kubectl --context kind-workboard-phase5 -n workboard logs job/workboard-loadgen
kubectl --context kind-workboard-phase5 -n workboard delete job workboard-loadgen
```

2 つの Pod のログに `success=50 failure=0` が出ます。この負荷の Pod だけが、NetworkPolicy で Web への通信を許可されています。同じ Job を再実行する前に、必ず Job を削除します。

## 故障実験

**ダミータスクを失ってよいと確認できた場合だけ実行してください。** 対象は `workboard-phase5` だけです。各実験は「注入 → 観察 → 復旧」の順で、観察の観点と読み方は [Runbook](runbook.md) の対応する節にあります。**Runbook を見る前に、まず自分で `describe` / `logs` / `get events` から原因を推測してください。**

復旧は、特に指定がなければ次の 1 コマンドです（`apply` は、注入した差分を元の定義に戻します）。

```text
kubectl --context kind-workboard-phase5 apply -k phases/05-security-and-failure/kustomize/overlays/kind
```

### A. 存在しない image tag

```text
kubectl --context kind-workboard-phase5 apply -k phases/05-security-and-failure/experiments/bad-image-tag
kubectl --context kind-workboard-phase5 -n workboard get pods -l app=workboard-web
```

### B. 誤った Service selector

```text
kubectl --context kind-workboard-phase5 apply -k phases/05-security-and-failure/experiments/wrong-selector
kubectl --context kind-workboard-phase5 -n workboard get endpointslices -l kubernetes.io/service-name=workboard-api
```

### C. DB の DNS 名のミス

```text
kubectl --context kind-workboard-phase5 apply -k phases/05-security-and-failure/experiments/wrong-db-host
kubectl --context kind-workboard-phase5 -n workboard get pods -l app=workboard-api
```

### D. 権限不足（RBAC）

```text
kubectl --context kind-workboard-phase5 -n workboard delete rolebinding workboard-viewer
kubectl --context kind-workboard-phase5 -n workboard get pods --as=system:serviceaccount:workboard:workboard-viewer
```

### E. memory limit による OOMKilled

```text
kubectl --context kind-workboard-phase5 apply -k phases/05-security-and-failure/experiments/low-memory-limit
kubectl --context kind-workboard-phase5 -n workboard get pods -l app=workboard-api
```

### F. NetworkPolicy による遮断

```text
kubectl --context kind-workboard-phase5 -n workboard delete networkpolicy api-traffic
kubectl --context kind-workboard-phase5 -n workboard get pods
```

画面（8083）の操作や `exec` による通信確認で、何が起きるかを観察します。各実験の後は必ず復旧し、`kubectl get pods`・`get endpointslices`・`auth can-i`・画面の操作で復旧を確認してから次に進みます。

## 失敗時に確認すること

- `kubectl kustomize` が `secrets/db.env` を読めない: ファイルがあるか。`scripts/up.ps1` で生成するか、例ファイルからコピーしたか。
- 接続先が違う: `. .\phases\05-security-and-failure\scripts\env.ps1`（Bash は `source phases/05-security-and-failure/scripts/env.sh`）を読み込んだか。context が `kind-workboard-phase5` か。
- クラスター作成が止まる / Node が `NotReady`: `kubectl get pods -n kube-system` で `calico-node` が Running か。Calico のイメージ（quay.io）を取得できているか（`describe pod` の Events）。
- Pod が `CreateContainerConfigError`: `describe pod` のメッセージ。`runAsNonRoot` なのにイメージの USER が名前（数値でない）だと、`runAsUser` の指定が必要。
- Pod が作られない: `describe replicaset` の `FailedCreate`。PodSecurity の違反項目が列挙される。
- 起動直後にクラッシュ: `logs --previous` に `Read-only file system` がないか。書き込み先を emptyDir にしているか。
- `ErrImageNeverPull`: `kind load docker-image ... --name workboard-phase5` が成功したか。
- 通信が通らない: `getent hosts` で名前解決、EndpointSlice で宛先、`kubectl get networkpolicy` でポリシーを順に見る。タイムアウトか `refused` かを区別する。
- 8083 が使えない: 他のプロセスが使用中でないか確認し、解放できる場合だけ解放する。

## Linux / macOS / WSL での前提

スクリプトは PowerShell 版と同じ処理の Bash 版（`phases/05-security-and-failure/scripts/env.sh`・`up.sh`、導入は Phase 2 と共通の `tools/kind-install.sh`）があり、上の手順の「Linux / macOS / WSL (Bash)」に従います。Bash 4 以降、Docker（WSL は Docker Desktop の WSL 統合）、kubectl 1.34〜1.36 の条件は Phase 2 の「Linux / macOS / WSL での前提」と同じです。

## 後片付け・再構築

port-forward を実行しているターミナルで `Ctrl+C` を押すと入口だけが閉じます。クラスターとアプリは動き続けます。

`workboard-phase5` を削除すると、DB のデータも失われます。クラスター名と消えるデータを確認し、削除してよいと明示的に判断した場合だけ以下を使います。ほかのクラスターは対象外です。

```text
kind delete cluster --name workboard-phase5
```

削除後、専用 kubeconfig `.kube/workboard-phase5.yaml` が残っていれば対象を確認してそのファイルだけ削除します。`db.env` は残して再利用できます。**クラスター（PVC）を残したまま `db.env` を消さないでください。** 構築スクリプトが別のパスワードを生成し、初期化済みの DB と一致しなくなります。

## 完了条件

- [ ] `kubectl kustomize` の生成結果で、Namespace のラベル、ServiceAccount、securityContext、Role、NetworkPolicy を確認した。
- [ ] Calico が Running で、Web・API・PostgreSQL が非 root で動き、ルートファイルシステムが読み取り専用であることを確認した。
- [ ] Restricted に違反する Pod が拒否されることを確認した。
- [ ] `auth can-i` で、許可される操作と拒否される操作の両方を確認した。
- [ ] NetworkPolicy で、許可された通信が成功し、許可されていない通信が失敗することを確認した。
- [ ] 故障実験 A〜F を再現し、原因を自分の手順で特定して復旧した（省略した実験は理由を記録した）。
- [ ] [Runbook](runbook.md) を読んで、自分の調査手順と比べた。
- [ ] 下記に結果・未実施の実験を、学習ポータルに設計課題への回答を記録した。
- [ ] 設計課題に答えた**後で** [ADR-0010（提案）](decisions/0010-security-and-troubleshooting.md) を読み、自分の回答と比べた。納得できたら ADR の Status を「採用」に変更し、異なる判断をした点は理由を学習ポータルの学習メモに残した。

## 学習メモ

観察結果と設計課題への回答は、この README ではなく**学習ポータルに入力します**（各自の PC の Git 管理外 `learning-portal/.data` にだけ保存され、リポジトリには残りません）。実行していない実験は「省略」と理由を書きます。記録する項目は次のとおりです。

- 実行日・OS・シェル
- kind / kubectl / Kubernetes / Calico バージョン
- Pod Security のラベルと、違反 Pod の拒否メッセージ
- Web・API・PostgreSQL の実行ユーザーと書き込み可能な場所
- RBAC の許可と拒否の一覧
- NetworkPolicy の許可された通信と拒否された通信（成功・失敗の様子）
- ダミー負荷の結果
- 故障実験 A〜F の症状・原因を特定した手がかり・復旧結果
- Secret の保護範囲について分かったこと・未検証の点
- 後片付け・残したクラスター
- 疑問・未解決事項

## 実装時の検証記録

2026-11-10、Windows PowerShell 5.1、Docker Desktop の Linux エンジン、kubectl v1.34.1（Kustomize v5.7.1）で実装担当が確認しました。学習者自身の記録は README ではなく学習ポータルに残します。

| 確認・コマンド | 結果 |
| --- | --- |
| `kubectl kustomize phases/05-security-and-failure/kustomize/overlays/kind` | 成功 |
| `phases/05-security-and-failure/scripts/up.ps1`（新規） | `workboard-phase5` を作成。Calico v3.33.0 を導入し、Node Ready、CoreDNS Running を確認してからアプリを適用。StatefulSet 1/1、migration Job Complete、Web/API 1/1、NetworkPolicy 7 個。`db.env` はランダム値を自動生成（値は出力しない） |
| 初回の構築で判明した修正 | API のイメージの `USER` が名前（`workboard`）のため、`runAsNonRoot` だけでは `CreateContainerConfigError`。`runAsUser: 10001` を明示して解消 |
| 実行ユーザー | Web `uid=101(nginx)`、API `uid=10001(workboard)`。いずれも読み取り専用ルート、emptyDir のみ書き込み可。PostgreSQL（UID 999）も 1/1 で稼働 |
| Pod Security | `violating-pod.yaml` は `Forbidden: violates PodSecurity "restricted:v1.35"` で拒否（privileged、allowPrivilegeEscalation、capabilities、runAsNonRoot、runAsUser=0、seccompProfile を列挙） |
| `auth can-i`（`workboard-viewer`） | get pods / pods/log / endpointslices は yes。get secrets / delete pods / create deployments / kube-system の get pods は no。`default` ServiceAccount の get pods は no。`get secrets --as=…` は Forbidden |
| NetworkPolicy（許可） | Web→API の `/health/ready` は `{"status":"ready"}`。API→DB は接続成功。migration Job は完了 |
| NetworkPolicy（拒否） | Web→DB（`nc`）はタイムアウト。API→Web も失敗。`probe` Pod は名前解決に成功するが `pg_isready` は `no response` |
| ダミー負荷 | 2 Pod とも `success=50 failure=0` で Completed |
| port-forward 8083 | health ready は 200。タスクの作成と取得に成功（default deny でも port-forward は通る） |
| 故障 A | 新 Pod が `ImagePullBackOff`（`not found`）、旧 Pod は 1/1 のまま。`apply -k` で復旧 |
| 故障 B | EndpointSlice の `ENDPOINTS` が `<unset>`、Web→API は `download timed out`。復旧後に Endpoints が戻った |
| 故障 C | 新 API Pod が `0/1 Running`、Events に readiness の timeout / refused。ログは起動メッセージのみで DB エラーなし。`printenv POSTGRES_HOST` は `workboard-postgress`。復旧後に rollout 完了 |
| 故障 D | RoleBinding 削除で `can-i` が no、`get pods --as=…` は Forbidden。`apply -k` で RoleBinding が再作成され yes に復旧 |
| 故障 E | 新 API Pod が `CrashLoopBackOff`、`Last State: Terminated`、`Reason: OOMKilled`、`Exit Code: 137`、limit 20Mi。復旧で正常化 |
| 故障 F | `api-traffic` を削除すると、Pod は Ready のまま画面経由の API が 504。復旧で 200 |
| ポリシー削除の追加観察 | `postgres-ingress` と `default-deny-all` を削除しても Web→DB は届かない（`web-traffic` と `allow-dns-egress` が egress を制限しているため）。復旧は `apply -k` |
| `apply -k` の StatefulSet 表示 | 毎回 `configured` と表示されるが、DB Pod は再作成されなかった（表示の原因は未特定。Phase 3 でも同様） |

k9s は導入していないため、Runbook の k9s の節は未検証です。保存時暗号化、監査ログ、Calico のログ、Linux ネイティブ・macOS・Docker Engine 単独での実行、複数ノード、クラスター全削除後の再構築は未実施です。`app/web` は変更していません。AWS は使用していません。
