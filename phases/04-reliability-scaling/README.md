# Lab 04: 可用性、更新、スケーリング

## 学習目標

- Startup・Liveness・Readiness の 3 つの Probe を使い分け、DB 障害時にどの Probe が何を引き起こすかを説明する。
- requests と limits の意味、QoS、HPA が使う CPU 使用率の基準を、実測値と合わせて説明する。
- Rolling Update の `maxSurge` / `maxUnavailable`、新しい Pod が Ready にならない場合の挙動、`kubectl rollout undo` の効果を観察する。
- HPA と metrics-server で CPU 負荷に応じた増減を観察し、増やせる範囲を決めるものを説明する。
- 複数ノードで `topologySpreadConstraints` と PodDisruptionBudget の効果を観察し、レプリカ数が多くても残る単一障害点を説明する。
- 障害前後の Pod 数・HTTP 応答・イベント・復旧時間を記録する。

## 前提条件

Phase 3 の内容（Kustomize、StatefulSet、PVC、ConfigMap/Secret）を理解していること。Linux コンテナエンジンが動く Docker（Windows / macOS は Docker Desktop、Linux は Docker Engine または Docker Desktop）、kubectl 1.34〜1.36、kind v0.33.0（導入は Phase 2 と共通の `tools/kind-install.ps1`。Bash は `tools/kind-install.sh`）。ノードは Kubernetes v1.35.8、DB は `postgres:17.11-bookworm`、metrics-server は v0.9.1 です。AWS 費用はありません。

この Lab は **新しい kind クラスター `workboard-phase4`**（control-plane 1 台と worker 2 台）で行います。Phase 2 の `workboard-lab`、Phase 3 の `workboard-phase3`、それぞれの kubeconfig は変更しません。この Phase のファイルは `phases/04-reliability-scaling/` だけで完結し、Web/API の定義や `cluster.yaml` は Phase 3 と重複して存在します（Phase を独立させるための意図的な重複です。[ADR-0007](../../docs/adr/0007-phase-directory-layout.md)）。ノードが 3 台あるため、他のクラスターと同時に動かすと Docker のメモリ（目安として 4 GiB 以上の空き）と CPU が必要です。

ポートは **8082** を使います（8080 は Phase 2、8081 は Phase 3）。DB はダミーデータ専用です。

API には Prometheus 形式の `GET /metrics` が加わりました（`workboard_http_requests_total` と `workboard_http_request_duration_seconds`）。この Phase では確認だけを行い、収集と可視化は Phase 8 で扱います。

## 設計課題（実装前に考える）

1. API のレプリカを 3 つにしても、ノードが 1 つだけなら何が単一障害点になるのか？ ノード 2 台のこのクラスターでも、まだ残る単一障害点は何か？
2. HPA は Node の台数まで Pod を増やすのか？ 増やせる最大数は何で決まり、Pod が置けない場合は何が起きるか？
3. Startup・Liveness・Readiness の Probe は、それぞれ何を確認すべきか？ DB が止まったとき、各 Probe が失敗すると Pod はどうなるか？
4. requests と limits は何を根拠に決めるか？ CPU と memory で、limits を超えたときの挙動はどう違うか？ HPA の CPU 使用率は何に対する割合か？
5. PodDisruptionBudget は何を守り、何を守らないのか？
6. `maxSurge` と `maxUnavailable` は何を基準に決めるか？ 新しい Pod が Ready にならないとき、更新は進むか？ `rollout undo` で戻るもの・戻らないものは何か？
7. `topologySpreadConstraints` の `whenUnsatisfiable` に `DoNotSchedule` と `ScheduleAnyway` のどちらを使うか？ それぞれ、Pod が置けない状況で何が起きるか？

## 実装タスク

1. [構成図](architecture.md)を読み、Web・API・DB のうち可用性を上げた対象と、上げていない対象を書き出す。
2. `kustomize/base/api.yaml`、`kustomize/base/web.yaml`、`kustomize/metrics-server/`、`load/load-generator.yaml` を読み、Probe・resources・更新戦略・分散・PDB・HPA がどのファイルのどの項目かを対応づける。
3. `kubectl kustomize` で生成結果を確認してから、専用クラスターへ適用する。
4. 障害前の状態（Pod 数・配置・HTTP 応答・使用量）を記録する。
5. 故障実験で Pod 数・HTTP 応答・イベント・復旧時間を記録する。
6. 結果を **学習ポータルの学習メモ**（項目は「学習メモ」節）に記録する。

## 検証コマンド・期待結果

すべてリポジトリ直下で実行します。この Lab の Kubernetes 操作は `--context kind-workboard-phase4` を指定します。他の Lab のクラスターを操作しないよう、毎回 context を確認してください。

### 1. 適用前に生成結果を読む

新しいターミナルごとに最初の行を実行します。`env.ps1`（Bash は `env.sh`。実行ではなく `source` で読み込みます）はこのシェルだけで Phase 4 用の kubeconfig（`.kube/workboard-phase4.yaml`）を使う設定です。

**Windows (PowerShell):**

```powershell
. .\phases\04-reliability-scaling\scripts\env.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
source phases/04-reliability-scaling/scripts/env.sh
```

```text
kubectl kustomize phases/04-reliability-scaling/kustomize/base
kubectl kustomize phases/04-reliability-scaling/kustomize/overlays/kind
kubectl kustomize phases/04-reliability-scaling/kustomize/metrics-server
```

Secret の入力は Git 管理外の `phases/04-reliability-scaling/kustomize/overlays/kind/secrets/db.env` です。まだ無い場合、次の「2. 構築」のスクリプトがローカル専用のランダムな値で作成します。自分で用意する場合は、例ファイル（ダミー値のみ）をコピーして値を変えます。

**Windows (PowerShell):**

```powershell
Copy-Item phases/04-reliability-scaling/kustomize/overlays/kind/secrets/db.env.example phases/04-reliability-scaling/kustomize/overlays/kind/secrets/db.env
```

**Linux / macOS / WSL (Bash):**

```bash
cp phases/04-reliability-scaling/kustomize/overlays/kind/secrets/db.env.example phases/04-reliability-scaling/kustomize/overlays/kind/secrets/db.env
```

観察する点は以下です。

- API の Deployment に `replicas`、`strategy`、`topologySpreadConstraints`、3 つの Probe、`resources`、`lifecycle` があること。
- `overlay` の出力に PodDisruptionBudget と HorizontalPodAutoscaler が含まれること。
- `metrics-server` の出力は `kube-system` 用で、`workboard` の overlay とは別の適用単位になっていること。`--kubelet-insecure-tls` が引数に追加されていること。

### 2. 構築

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File tools/kind-install.ps1
powershell -NoProfile -File phases/04-reliability-scaling/scripts/up.ps1
```

**Linux / macOS / WSL (Bash):**

```bash
bash tools/kind-install.sh
bash phases/04-reliability-scaling/scripts/up.sh
```

`kind-install` は導入済みなら何もしません。構築スクリプトは次の順で、固定秒数の sleep ではなく実際の状態を待ちます。

1. `workboard-phase4` クラスターの作成（存在しなければ）。同名クラスターのみ・kubeconfig のみ残っている場合は確認のため停止します。他のクラスターには何も適用しません。
2. API/Web イメージのビルドと `kind load docker-image`（`imagePullPolicy: Never` のため投入忘れは `ErrImageNeverPull` になります）。
3. `db.env` が無ければランダムなパスワードを生成して作成（値は表示しません）。既にあれば変更しません。
4. metrics-server を `kube-system` に適用。
5. 完了済みの migration Job を削除し、overlay を `kubectl apply -k`。
6. StatefulSet・migration Job・Web/API・metrics-server の準備完了待ち、メトリクス API（APIService）が Available になるまで待機。

metrics-server のイメージはノードが `registry.k8s.io` から取得します。ネットワークに接続できる環境が必要です。

期待結果は、Node が 3 台とも Ready、API が 3/3、Web が 2/2、StatefulSet が 1/1、PVC が Bound、migration Job が Completed、`hpa` の TARGETS が `cpu: 数値%/50%`（数値が `<unknown>` の間は metrics-server の準備待ちです）です。

### 3. 配置・Probe・resources を観察する

```text
kubectl --context kind-workboard-phase4 get nodes
kubectl --context kind-workboard-phase4 -n workboard get pods -o wide
kubectl --context kind-workboard-phase4 -n workboard describe deployment workboard-api
kubectl --context kind-workboard-phase4 -n workboard get pod -l app=workboard-api -o custom-columns=NAME:.metadata.name,NODE:.spec.nodeName,QOS:.status.qosClass
kubectl --context kind-workboard-phase4 -n workboard get pdb,hpa
```

API Pod が 2 台の worker にどう配置されているか、control-plane に Pod が載っていないか、QoS クラス、PDB の `ALLOWED DISRUPTIONS` を確認します。`describe` の `Liveness` / `Readiness` / `Startup` の行で、それぞれの確認先とパラメーターを読みます。Web や PostgreSQL の配置・QoS も同じコマンドの出力から比べます。

### 4. metrics-server と使用量

```text
kubectl --context kind-workboard-phase4 get apiservice v1beta1.metrics.k8s.io
kubectl --context kind-workboard-phase4 top nodes
kubectl --context kind-workboard-phase4 -n workboard top pods
kubectl --context kind-workboard-phase4 -n workboard get hpa workboard-api
kubectl --context kind-workboard-phase4 -n workboard describe hpa workboard-api
```

APIService が `True` で、`top` が値を返すことを確認します。構築直後に `top` が `Metrics not available` を返す場合は、数十秒待って再実行します。アイドル時の API Pod の CPU とメモリを記録し、`requests` / `limits` を決めた値と比べます。

### 5. ブラウザーで同じアプリを使う

8082 番が使われていないことを確認し、次のコマンドを実行中のまま残してブラウザーを別に開きます。

```text
kubectl --context kind-workboard-phase4 -n workboard port-forward --address 127.0.0.1 svc/workboard-web 8082:80
```

[http://localhost:8082](http://localhost:8082) でダミータスクを作ります。別のターミナルで次の確認もできます。

**Windows (PowerShell):**

```powershell
curl.exe -i http://localhost:8082/health/ready
curl.exe -s http://localhost:8082/api/v1/tasks
```

**Linux / macOS / WSL (Bash):**

```bash
curl -i http://localhost:8082/health/ready
curl -s http://localhost:8082/api/v1/tasks
```

`port-forward` は Service を指定しても、起動時に選ばれた **1 つの Web Pod** にだけつながります。その Pod が削除・退避されると接続が切れます（`curl` が失敗する、`port-forward` のコマンドが終了する）。実験中に応答が止まったら、まず Web Pod が消えていないかを確認し、このコマンドを再実行します。

`/metrics` は Web（Nginx）を経由せず、API Pod の中から確認します。

```text
kubectl --context kind-workboard-phase4 -n workboard exec deploy/workboard-api -- python -c "import urllib.request; print(urllib.request.urlopen('http://localhost:8000/metrics').read().decode())"
```

`workboard_http_requests_total` の `route` ラベルが、実際の ID ではなく `/api/v1/tasks/{task_id}` のようなテンプレートになっていることを確認します。

### 6. HTTP 応答を記録しながら Rolling Update を観察する

別のターミナルで、8082 番への応答を 0.5 秒ごとに記録します（時刻・HTTP ステータス・所要秒数。接続できないとステータスは `000`）。止めるときは `Ctrl+C` です。

**Windows (PowerShell):**

```powershell
powershell -NoProfile -File phases/04-reliability-scaling/scripts/watch-http.ps1 http://localhost:8082/api/v1/tasks 0.5
```

**Linux / macOS / WSL (Bash):**

```bash
bash phases/04-reliability-scaling/scripts/watch-http.sh http://localhost:8082/api/v1/tasks 0.5
```

この記録を流したまま、API の Pod を順に入れ替えます。

```text
kubectl --context kind-workboard-phase4 -n workboard rollout restart deployment/workboard-api
kubectl --context kind-workboard-phase4 -n workboard rollout status deployment/workboard-api --timeout=120s
kubectl --context kind-workboard-phase4 -n workboard get replicaset -l app=workboard-api
kubectl --context kind-workboard-phase4 -n workboard rollout history deployment/workboard-api
```

更新中の Pod 数の変化（`maxSurge` / `maxUnavailable` の効果）、ReplicaSet が新旧 2 世代あること、記録の中にステータスが 200 以外のものがないかを確認します。

## 故障実験

**ダミータスクを失ってよいと確認できた場合だけ実行してください。** 対象は `workboard-phase4` だけで、他のクラスターには影響しません。各実験の前後で、6 の `watch-http` を別ターミナルで流しておき、実験を始めた時刻と HTTP ステータスが変化・復旧した時刻を記録します。復旧時間は、変化から 200 が連続して戻るまでの差で測ります。

### A. API Pod を削除する

```text
kubectl --context kind-workboard-phase4 -n workboard get pods -l app=workboard-api -o wide
kubectl --context kind-workboard-phase4 -n workboard delete pod <API Pod の名前>
kubectl --context kind-workboard-phase4 -n workboard get pods -l app=workboard-api -w
kubectl --context kind-workboard-phase4 -n workboard get events --sort-by=.lastTimestamp
```

Pod 数の推移、新しい Pod がどのノードに置かれるか（分散が保たれるか）、`watch-http` の応答の変化、新しい Pod が Ready になるまでの時間、`Startup probe failed` などのイベントを記録します。`-w` は `Ctrl+C` で止めます。

### B. DB を一時停止する

```text
kubectl --context kind-workboard-phase4 -n workboard scale statefulset workboard-postgres --replicas=0
kubectl --context kind-workboard-phase4 -n workboard get pods -l app=workboard-api
kubectl --context kind-workboard-phase4 -n workboard get endpoints workboard-api
kubectl --context kind-workboard-phase4 -n workboard scale statefulset workboard-postgres --replicas=1
kubectl --context kind-workboard-phase4 -n workboard rollout status statefulset/workboard-postgres --timeout=120s
kubectl --context kind-workboard-phase4 -n workboard get pods -l app=workboard-api -o custom-columns=NAME:.metadata.name,READY:.status.containerStatuses[0].ready,RESTARTS:.status.containerStatuses[0].restartCount
```

DB が止まっている間の API Pod の READY と RESTARTS、Service の宛先（endpoints）、HTTP ステータスの変化（とその順序）、DB が戻ってから 200 に戻るまでの時間を記録します。Liveness と Readiness のどちらが、どの動作を引き起こしたかを説明できるか確認します。PVC は残るため、タスクは残ります。

### C. Readiness が失敗する更新を適用する

Readiness Probe の確認先を存在しないパスに変え、更新が進むかを観察します。

```text
kubectl --context kind-workboard-phase4 -n workboard patch deployment workboard-api --type=json -p '[{"op":"replace","path":"/spec/template/spec/containers/0/readinessProbe/httpGet/path","value":"/health/nope"}]'
kubectl --context kind-workboard-phase4 -n workboard rollout status deployment/workboard-api --timeout=30s
kubectl --context kind-workboard-phase4 -n workboard get pods -l app=workboard-api
kubectl --context kind-workboard-phase4 -n workboard get deployment workboard-api
kubectl --context kind-workboard-phase4 -n workboard describe pod -l app=workboard-api
```

新旧の Pod 数、`READY` の列、Deployment の `AVAILABLE`、`describe` のイベントを記録します。`watch-http` の応答が途切れるかも確認します。戻すときは次を実行します。

```text
kubectl --context kind-workboard-phase4 -n workboard rollout undo deployment/workboard-api
kubectl --context kind-workboard-phase4 -n workboard rollout status deployment/workboard-api --timeout=120s
```

### D. CPU 負荷を与えて HPA を観察する

負荷生成用の Deployment `workboard-load` は、同じクラスター内の Service `workboard-api` だけを繰り返し呼び出します。別のターミナルで HPA の状態を流しておきます。

```text
kubectl --context kind-workboard-phase4 -n workboard get hpa workboard-api -w
```

```text
kubectl --context kind-workboard-phase4 apply -f phases/04-reliability-scaling/load/load-generator.yaml
kubectl --context kind-workboard-phase4 -n workboard top pods
kubectl --context kind-workboard-phase4 -n workboard get pods -l app=workboard-api -o wide
kubectl --context kind-workboard-phase4 -n workboard describe hpa workboard-api
```

負荷の開始時刻、`TARGETS` の値と `REPLICAS` の推移、増えた Pod の配置（ノードごとの数）、`describe hpa` のイベント（`SuccessfulRescale` の理由と上限）を記録します。次に負荷を止め、レプリカ数が戻るまでの時間を測ります。

```text
kubectl --context kind-workboard-phase4 delete -f phases/04-reliability-scaling/load/load-generator.yaml
kubectl --context kind-workboard-phase4 -n workboard get hpa workboard-api -w
```

### E. 存在しないイメージで更新し、rollback する

```text
kubectl --context kind-workboard-phase4 -n workboard set image deployment/workboard-api api=workboard-api:does-not-exist
kubectl --context kind-workboard-phase4 -n workboard get pods -l app=workboard-api
kubectl --context kind-workboard-phase4 -n workboard get replicaset -l app=workboard-api
kubectl --context kind-workboard-phase4 -n workboard rollout status deployment/workboard-api --timeout=30s
kubectl --context kind-workboard-phase4 -n workboard rollout history deployment/workboard-api
kubectl --context kind-workboard-phase4 -n workboard rollout undo deployment/workboard-api
kubectl --context kind-workboard-phase4 -n workboard rollout status deployment/workboard-api --timeout=120s
kubectl --context kind-workboard-phase4 -n workboard get deployment workboard-api -o jsonpath='{.spec.template.spec.containers[0].image}'
```

新しい Pod の STATUS（kind では `imagePullPolicy: Never` のため `ErrImageNeverPull`）、旧 ReplicaSet の Pod が残るか、HTTP 応答が途切れるか、`rollout status` が終わらない理由を記録します。undo 後のイメージ名とリビジョン番号の変化も確認します。`set image` で変えた内容は Git のマニフェストには反映されません。構築スクリプトの再実行（`apply -k`）で、マニフェストの内容へ戻ります。

### F. ノードを drain し、PDB の効果を見る

**先に PostgreSQL がどのノードにいるかを確認します。** kind の PV はそのノード内のディレクトリで、Pod はそのノードに固定されます。

```text
kubectl --context kind-workboard-phase4 -n workboard get pods -o wide
```

PostgreSQL がいない worker を drain の対象にします（以下は `workboard-phase4-worker2` の例。違う場合は読み替えます）。

```text
kubectl --context kind-workboard-phase4 -n workboard get pdb
kubectl --context kind-workboard-phase4 drain workboard-phase4-worker2 --ignore-daemonsets --delete-emptydir-data --timeout=120s
kubectl --context kind-workboard-phase4 -n workboard get pods -o wide
kubectl --context kind-workboard-phase4 -n workboard get pdb
kubectl --context kind-workboard-phase4 get nodes
```

追い出された Pod の種類と数、移動先、drain にかかった時間、`ALLOWED DISRUPTIONS` を記録します。この時点では `port-forward` の接続先 Web Pod が退避された場合に応答が止まるため、必要なら手順 5 を再実行します。

次に、残った worker も drain して、PDB が何を止めるかを確認します（PostgreSQL も追い出され、DB が停止します。ダミーデータで行います）。

```text
kubectl --context kind-workboard-phase4 drain workboard-phase4-worker --ignore-daemonsets --delete-emptydir-data --timeout=40s
kubectl --context kind-workboard-phase4 -n workboard get pods -o wide
kubectl --context kind-workboard-phase4 -n workboard get pdb
```

drain のメッセージ（どの Pod の何が拒否されるか）、Pending の Pod とその理由（`describe pod` のイベント）、PostgreSQL の状態を記録します。最後に必ず元へ戻します。

```text
kubectl --context kind-workboard-phase4 uncordon workboard-phase4-worker workboard-phase4-worker2
kubectl --context kind-workboard-phase4 -n workboard rollout status deployment/workboard-api --timeout=120s
kubectl --context kind-workboard-phase4 -n workboard rollout status statefulset/workboard-postgres --timeout=120s
kubectl --context kind-workboard-phase4 get nodes
```

## 失敗時に確認すること

- 接続先が違う: `. .\phases\04-reliability-scaling\scripts\env.ps1`（Bash は `source phases/04-reliability-scaling/scripts/env.sh`）を読み込んだか。context が `kind-workboard-phase4` か。
- API Pod が 3 つ揃わず Pending: `describe pod` のイベントで `didn't match pod topology spread constraints` や `untolerated taint` を読む。`kubectl get nodes` の台数と、`topologySpreadConstraints` の `nodeTaintsPolicy` を確認する。
- `kubectl top` が `Metrics API not available`: `kubectl -n kube-system get pods` で metrics-server が Ready か。`logs deployment/metrics-server -n kube-system` に証明書の検証エラー（`x509`）が出ていないか。出る場合は `--kubelet-insecure-tls` の引数がパッチで入っているか確認する。
- HPA の TARGETS が `<unknown>`: metrics-server が起動していない、または対象 Pod に `requests.cpu` が無い。`describe hpa` のイベントを読む。
- `ErrImageNeverPull`: `kind load docker-image ... --name workboard-phase4` が成功したか（`up` を再実行する）。故障実験 E では意図した動作。
- Pod が `Pending`（drain 後）: `kubectl get nodes` に `SchedulingDisabled` が残っていないか。`uncordon` したか。
- API が Ready にならない: `logs deployment/workboard-api` の認証エラー。`db.env` が DB を初期化した値と一致しているか。
- 応答が止まる / `curl` が失敗する: `port-forward` が選んだ Web Pod が削除・退避されていないか。手順 5 を再実行する。
- Web から 502: API の Pod が全て NotReady（宛先なし）でないか。`get endpoints workboard-api` を確認する。
- 8082 が使えない: 他のプロセスが使用中でないか確認し、解放できる場合だけ解放する。

## Linux / macOS / WSL での前提

スクリプトは PowerShell 版と同じ処理の Bash 版（`phases/04-reliability-scaling/scripts/` の `env.sh`・`up.sh`・`watch-http.sh`、導入は Phase 2 と共通の `tools/kind-install.sh`）があり、上の手順の「Linux / macOS / WSL (Bash)」に従います。Bash 4 以降、Docker（WSL は Docker Desktop の WSL 統合）、kubectl 1.34〜1.36、`curl` が必要です。その他の条件は Phase 2 の「Linux / macOS / WSL での前提」と同じです。

## 後片付け・再構築

port-forward を実行しているターミナルで `Ctrl+C` を押すと入口だけが閉じます。クラスターとアプリは動き続けます。負荷生成の Deployment が残っている場合は、実験 D の `delete -f` で削除します。

`workboard-phase4` を削除すると、PVC/PV に保存した DB のデータも失われます。クラスター名と消えるデータを確認し、削除してよいと明示的に判断した場合だけ以下を使います。他のクラスターは対象外です。

```text
kind delete cluster --name workboard-phase4
```

削除後、専用 kubeconfig `.kube/workboard-phase4.yaml` が残っていれば対象を確認してそのファイルだけ削除します。`db.env` は残して再利用できます。**クラスター（PVC）を残したまま `db.env` を消さないでください。** 構築スクリプトが別のパスワードを生成し、初期化済みの DB と一致しなくなります。

## 完了条件

- [ ] `kubectl kustomize` の生成結果で、Probe・resources・更新戦略・topology spread・PDB・HPA を確認した。
- [ ] `workboard-phase4` で Node 3 台が Ready、API が 3 Pod で 2 台の worker に分散し、`kubectl top` が値を返し、HPA の TARGETS に数値が出た。
- [ ] Rolling Update 中の HTTP 応答と Pod 数の変化を記録した。
- [ ] 故障実験 A〜F の障害前後の Pod 数・HTTP 応答・イベント・復旧時間を記録した（省略した実験は理由を書いた）。
- [ ] Liveness と Readiness の違い、requests/limits の根拠、HPA の増やせる範囲、PDB が守る範囲を、観察結果を使って説明できる。
- [ ] 単一障害点が何か（Pod・ノード・DB・`port-forward`）を、このクラスターについて説明できる。
- [ ] 下記に結果・未実施の実験・設計課題への回答を記録した。
- [ ] 設計課題に答えた**後で** [ADR-0009（提案）](decisions/0009-reliability-and-scaling.md) を読み、自分の回答と比べた。納得できたら ADR の Status を「採用」に変更し、異なる判断をした点は理由を学習ポータルの学習メモに残した。

## 学習メモ

観察結果と設計課題への回答は、この README ではなく**学習ポータルに入力します**（各自の PC の Git 管理外 `learning-portal/.data` にだけ保存され、リポジトリには残りません）。実行していない実験は「省略」と理由を書きます。記録する項目は次のとおりです。

- 実行日・OS・シェル
- kind / kubectl / Kubernetes / metrics-server のバージョン
- Node の台数と、API Pod のノード別の配置
- Probe の設定値（確認先・間隔・失敗回数）と requests / limits の値・根拠
- アイドル時と負荷時の API Pod の CPU・メモリ
- Rolling Update 中の Pod 数の変化と HTTP ステータスの分布
- 故障実験 A（API Pod 削除）の Pod 数・HTTP 応答・復旧時間
- 故障実験 B（DB 一時停止）の READY・RESTARTS・HTTP ステータスの順序・復旧時間
- 故障実験 C（Readiness 失敗の更新）の新旧 Pod 数と HTTP 応答
- 故障実験 D（CPU 負荷）の HPA の推移（TARGETS・REPLICAS・所要時間）
- 故障実験 E（存在しないイメージ）の Pod の状態と rollback 後のリビジョン
- 故障実験 F（drain と PDB）の移動した Pod・拒否されたメッセージ・Pending の理由
- 設計課題 1〜7 への回答と、ADR-0009 との違い
- 後片付け・残したクラスター
- 疑問・未解決事項

## 実装時の検証記録

2026-11-10、Windows 11・PowerShell 5.1、Docker Desktop の Linux エンジン、kubectl v1.34.1（Kustomize v5.7.1）、kind v0.33.0、Kubernetes v1.35.8、metrics-server v0.9.1 で実装担当が確認しました。学習者自身の記録は README ではなく学習ポータルに残します。時刻は `watch-http` の出力（約 1 秒または 0.5 秒間隔）の読み取りで、秒単位の目安です。

| 確認・コマンド | 結果 |
| --- | --- |
| PowerShell 3 スクリプトの構文解析、`bash -n` 3 本 | エラーなし。`.ps1` は UTF-8 BOM 付き、`.sh` は LF・BOM なし |
| `docker build --target test app/api` と一時 PostgreSQL でのテスト実行 | `/metrics` のテスト 3 件を含む 18 件が成功 |
| `python -m unittest discover -s learning-portal/tests` | 29 件が成功 |
| `kubectl kustomize` の overlay / metrics-server | 成功。API replicas 3、Web 2、PDB・HPA を出力。metrics-server に `--kubelet-insecure-tls` を追加 |
| `up.ps1` で `workboard-phase4` を新規作成 | control-plane 1・worker 2 が Ready。API 3/3、Web 2/2、StatefulSet 1/1、PVC Bound、migration Job Complete、`kubectl top` が値を返し HPA の TARGETS に数値が出た。`db.env` はランダム値を自動生成（値は出力しない） |
| 初回の構築で API の 3 つ目の Pod が Pending | `FailedScheduling`: `2 node(s) didn't match pod topology spread constraints`。control-plane（taint あり）が分散の対象に入り最小値が 0 になったため。`nodeTaintsPolicy: Honor` を追加して解消し、以後は API 3 Pod が worker 2 台に 2/1 で配置された |
| `up.ps1` の再実行 | 終了コード 0。`db.env` は不変、Job は再作成、Pod は維持 |
| WSL2 Ubuntu で `up.sh` を既存クラスターに実行 | 冪等に完了メッセージまで成功（終了コードは出力に表示されず未確認）。`watch-http.sh` と `watch-http.ps1` は 200 と、到達不能時の `000` を出力 |
| アイドル時の使用量（`kubectl top`） | API Pod: CPU 3〜5m、メモリ約 65Mi。Web: CPU 1〜2m、メモリ約 12Mi。PostgreSQL: CPU 23〜24m、メモリ 31〜38Mi |
| 故障実験 A: API Pod 削除 | 50 回（約 25 秒）すべて 200。新しい Pod は約 8 秒で Ready（`Startup probe failed` を数回記録）。新しい Pod は削除した Pod と同じノード（worker2）に置かれ、API は worker 2 台に 2/1 の配置を維持した |
| 故障実験 B: DB 停止（scale 0）→ 復帰 | 停止直後に `000`（2 秒のタイムアウト）→ `500` → `502` の順。API Pod は 3 つとも READY 0/1、RESTARTS 0、Service の endpoints は空。`scale --replicas=1` の約 3 秒後に 200 が戻り、停止から復旧まで約 30 秒。タスクは残った |
| 故障実験 C: Readiness のパスを `/health/nope` に変更 | 新 Pod が `0/1` のまま更新が進まず（`rollout status` は 10 秒でタイムアウト）、旧 3 Pod は Ready のまま。Deployment は AVAILABLE 3、新旧合計 4 Pod。イベントは `Readiness probe failed: HTTP probe failed with statuscode: 404`。40 回の応答はすべて 200。`rollout undo` で復旧 |
| 故障実験 E: `workboard-api:does-not-exist` に更新 | 新 Pod は `ErrImageNeverPull`、旧 3 Pod は Ready のまま。`rollout status` は 30 秒でも完了せず。35 回の応答はすべて 200。`rollout undo` で元のイメージ名 `workboard-api:kind` に戻った |
| `rollout restart`（preStop なしの定義）3 回 | 各回 69〜79 回の 200 と 1 回の 502（毎回 1 回、計 3 回再現） |
| `rollout restart`（`preStop` で 5 秒待つ定義）3 回 | 各回 80 回すべて 200、502 は 0 回。更新の所要は約 14 秒（1 回の計測） |
| 故障実験 D: 負荷 Deployment を適用 | 開始（09:43:25）の約 30 秒後に API が 3 → 6 Pod（`maxReplicas`）。6 Pod のノード別配置は 3/3。TARGETS は約 320%/50% のままで、上限 6 で頭打ち。負荷中の API Pod は CPU 約 300〜340m、メモリ約 66Mi。`SuccessfulRescale`: `above target` |
| 負荷を削除（09:46:40） | TARGETS は約 75 秒後に 21%、約 90 秒後に 3% 台へ低下。3 Pod に戻ったのは次の確認時点（09:49:02）で、負荷停止から 2.5 分以内。段階的な縮小の途中経過は取得しなかった |
| 故障実験 F: `workboard-phase4-worker2` を drain（PostgreSQL がいないノード） | 約 8 秒で完了。API 1 Pod・Web 1 Pod・migration の完了済み Pod・metrics-server が退避され、すべて残ったノードで再作成された。PDB の `ALLOWED DISRUPTIONS` は 1。この間の HTTP 記録は、`port-forward` が選んだ Web Pod が退避されたため `000` になり、drain の影響の測定としては無効（記録は取得できていない） |
| 故障実験 F: 続けて残った worker を drain（`--timeout=40s`） | API の 2 Pod の退避が `Cannot evict pod as it would violate the pod's disruption budget` で 5 秒間隔に繰り返し拒否され、`global timeout reached: 40s`。PostgreSQL（PDB なし）と Web は退避されて Pending になり、DB が停止。API の別の 1 Pod も Pending。`uncordon` 後に API は 3/3、PostgreSQL は 1/1 に戻った |
| metrics-server から `--kubelet-insecure-tls` を外す | 新しい Pod が Ready にならず、ログに `x509: cannot validate certificate for 172.20.0.x because it doesn't contain any IP SANs`。引数を戻すと `kubectl top` が値を返した |

未実施・未検証: HTTP 応答の測定は `port-forward` 経由（Web Pod 1 つに固定）で、Service や kube-proxy を直接測っていません。drain 中の HTTP 応答の連続性は未測定です。CPU の `limits` による throttling と memory の OOMKill、`ScheduleAnyway` との比較、Pod 数が 6 を超える場合のノード不足による Pending、ネイティブ Linux、macOS、Docker Engine 単独での実行、`up.sh` の終了コードの確認は未実施です。metrics-server が `kubectl top` の値を返し始めるまでの時間は計測していません。AWS は使用していません。
