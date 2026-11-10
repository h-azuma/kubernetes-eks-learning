# ADR-0009: kind での可用性、更新、スケーリングの構成

> **読む順番:** この ADR には Lab 04 の設計課題の答えにあたる内容が含まれます。先に [Phase 4 のラボ](../README.md) の設計課題に自分で答えてから読み、自分の考えと比べてください。

## Status

提案（2026-11-10）。Phase 4 に適用。学習者が Lab 04 の設計課題に回答し、内容を確認したうえで「採用」に変更する。

## Context

Phase 3 の WorkBoard は、Web・API・DB が各 1 Pod で、Probe も resources もなく、Pod の削除・更新・ノードの停止が、そのまま利用者への停止になった。Phase 4 では次の点を、kind 上で観察できる構成にしたい。

- Pod の障害や更新で、利用者に見える停止を起こさない。
- DB が止まったときに、「再起動しても直らない障害」で API を再起動し続けない。
- 負荷に応じて Pod 数が変わる様子を、費用なしで観察する。
- ノード単位の障害・保守で、何が残り、何が止まるかを確認する。

この構成は EKS（Phase 6）でも同じマニフェストの考え方を使う。ただし kind はノードが Docker コンテナで、ローカル専用の設定が混ざるため、環境依存の設定は overlay に分ける。

## Decision

### 1. クラスターは control-plane 1 台と worker 2 台にする

- 1 ノードでは topology spread、PDB、drain の効果が観察できない。worker を 2 台にし、Pod の分散とノード単位の退避を確認できるようにした。ノードイメージは Phase 3 と同じ `kindest/node:v1.35.8`（digest 固定）。
- クラスターは Phase 3 から独立した `workboard-phase4` とし、port-forward は 8082 を使う（ADR-0007）。

### 2. Probe は 3 つに分け、Liveness は DB に依存させない

| Probe | 確認先 | 設定 | 意図 |
| --- | --- | --- | --- |
| startup | `/health/live` | 2 秒間隔、失敗 30 回まで | 起動が遅いときに、Liveness による再起動を始めさせない（最大 60 秒） |
| liveness | `/health/live` | 10 秒間隔、タイムアウト 2 秒、失敗 3 回 | プロセスが応答できなくなったときだけ再起動する。DB は見ない |
| readiness | `/health/ready` | 3 秒間隔、タイムアウト 4 秒、失敗 2 回 | DB に接続できない Pod を Service の宛先から外す。再起動はしない |

- DB 障害時に Liveness も DB を見ると、全 API Pod が再起動を繰り返し、DB が復旧しても API の復旧が遅れる。設計書 §2.2 の方針に従う。
- Readiness のタイムアウトは、アプリ側の DB 接続タイムアウト（3 秒）より長くした。短いと DB が遅いだけの状態を、接続不能と区別できない。
- Web は Nginx が `/` を返せるかだけを見る。API の状態は Web の Probe に含めない（API 障害で Web を宛先から外すと、利用者に 502 ではなく接続エラーが見えるため）。

### 3. requests / limits は実測値から決める

アイドル時と負荷時に `kubectl top` で測った値（Evidence 参照）を基準にした。

| 対象 | CPU requests | メモリ requests | CPU limits | メモリ limits |
| --- | --- | --- | --- | --- |
| API | 100m | 128Mi | 500m | 256Mi |
| Web | 20m | 16Mi | 200m | 64Mi |
| PostgreSQL | 100m | 256Mi | なし | 512Mi |

- CPU requests はスケジューラーの配置と、HPA の使用率の分母になる。API はアイドル時に 3〜5m、高負荷時に約 300〜340m だった。100m とすると、HPA の目標 50% は約 50m に当たり、アイドル時（約 5%）との差が大きく、負荷で確実に反応する。
- メモリは圧縮できない資源なので、実測（約 65Mi、負荷中も約 66Mi）に余裕を持たせ、requests を 128Mi、limits を 256Mi にした。limits を超えると OOMKill される。
- CPU limits は超えると throttling（再起動ではなく速度低下）になる。API には 500m を付け、暴走した 1 Pod がノードを占有しないようにした。PostgreSQL は CPU limits を付けず、遅延の原因が throttling になるのを避けた。
- requests と limits が異なる Pod の QoS は Burstable。Guaranteed にはしていない。

### 4. Rolling Update は `maxSurge: 1` / `maxUnavailable: 0`、終了前に 5 秒待つ

- 3 レプリカのうち、更新中も 3 Pod 以上が Ready であることを優先する。`maxUnavailable: 0` なら、新しい Pod が Ready にならない限り旧 Pod は減らず、Readiness 異常や不正イメージの更新が、利用者への停止にならない（Evidence 参照）。代償として、更新に 1 Pod 分の余裕（CPU/メモリ）が一時的に必要になる。
- API に `preStop` で 5 秒の `sleep` を入れた。Pod の削除では、Service の宛先からの除外と SIGTERM の送信が並行して進むため、終了処理を始めた Pod に要求が届くことがある。`rollout restart` を 3 回行ったとき、`preStop` なしでは毎回 1 回の 502 が出て、`preStop` ありでは 3 回とも 0 回だった。
- `rollout undo` は Pod テンプレート（イメージや Probe）を直前のリビジョンに戻す。`replicas` や HPA の設定、ConfigMap/Secret の内容、DB のデータは戻らない。

### 5. 分散は `topologySpreadConstraints`、保守時の下限は PDB で守る

- API は `kubernetes.io/hostname` で `maxSkew: 1`、`whenUnsatisfiable: DoNotSchedule` とする。Pod が偏ることで、1 ノードの停止が全停止になるのを避ける。
- `nodeTaintsPolicy: Honor` を付ける。付けないと taint で Pod を置けない control-plane も分散の対象に数えられ、Pod が 0 個の control-plane が最小値になって、worker に 1 Pod ずつしか置けない。実際に 3 つ目の Pod が Pending になった（Evidence 参照）。
- PDB は `minAvailable: 2`（3 レプリカのうち 1 Pod まで自発的な退避を許す）。PDB が対象にするのは `drain` や Eviction API による自発的な退避だけで、ノード障害や Pod の直接削除、OOMKill には効かない。
- PostgreSQL と Web には PDB を付けない。DB は 1 レプリカのため、PDB（`minAvailable: 1`）を付けると drain が止まったままになる。

### 6. HPA は CPU、3〜6 Pod、縮小の待ち時間は 60 秒

- `autoscaling/v2` で CPU 使用率 50%（requests に対する割合）。`minReplicas: 3` は Deployment の replicas と一致させ、PDB と topology spread の前提を保つ。
- `maxReplicas: 6` は、requests 合計（600m）が kind の 2 台に収まる範囲として決めた。HPA は Node の台数ではなく `maxReplicas` と、メトリクスの値で増減する。ノードに空きが無ければ Pod は Pending になり、ノードを増やすのは別の仕組み（Cluster Autoscaler / Karpenter。Phase 6 以降）。
- `scaleDown.stabilizationWindowSeconds` を 60 秒にした（既定は 300 秒）。ラボの観察時間を短くするための変更で、本番の値ではない。
- HPA が管理する Deployment に `replicas` を書き残すと、マニフェストの値を変えて再適用したときに HPA の決めた台数と競合する。本番では `replicas` を外すことが多い。この Phase では、台数の初期値と PDB の前提を読みやすくするため残しているが、再適用時の挙動は検証していない。

### 7. metrics-server は公式 v0.9.1 を固定し、kind 用の引数を 1 つ足す

- 公式リリース v0.9.1 の `components.yaml` を `kustomize/metrics-server/components.yaml` に変更なしで置く。URL を直接参照すると、再現性が失われ、適用時にネットワークも必要になるため。更新は、公式の新しいリリースを確認して差し替える。
- kind の kubelet は、クラスターの CA で署名されていない証明書を提示する。metrics-server がそれを検証できず、すべてのノードの取得に失敗するため、`--kubelet-insecure-tls` を `kustomize/metrics-server/kustomization.yaml` のパッチで追加した。証明書の検証を省略するので、ローカル専用である。EKS では付けない。
- `kube-system` に配置するため、Namespace を `workboard` に付け替える `overlays/kind` とは別の適用単位にした。構築スクリプトが先に適用する。

### 8. 負荷生成は同じクラスター内の別 Deployment にする

`load/load-generator.yaml` は kustomize の対象に含めず、実験のときだけ `kubectl apply` する。busybox の `wget` で `Service: workboard-api` だけを繰り返し呼び出す。外部には通信しない。

### 9. API に `/metrics` を追加する

設計書 §2.4 に従い、Prometheus 形式の `GET /metrics` を追加した（`prometheus-client` 0.26.0）。名前は Phase 8 の収集と共有するため固定する。

- `workboard_http_requests_total{method,route,status}`
- `workboard_http_request_duration_seconds{method,route}`

`route` には実パスではなく、パステンプレート（`/api/v1/tasks/{task_id}`）を使い、ラベルの値の数を抑える。一致する経路が無いリクエストは `unmatched` にまとめる。`/metrics` 自身は計測しない。

## Alternatives

- **Liveness も DB を確認する:** DB 障害で全 Pod が再起動し、復旧が遅れ、原因の調査も難しくなる。
- **Startup Probe を使わず Liveness の `initialDelaySeconds` で待つ:** 起動が速い Pod の検知も遅れ、遅い起動には足りない。
- **requests と limits を同じにして Guaranteed にする:** CPU が確保され安定するが、HPA の使用率が limits 基準でないため目標の解釈が変わり、ローカルのノードの空きを無駄に占有する。
- **`maxUnavailable: 1`（既定の 25% など）:** 余分な Pod は不要だが、更新中に Ready が 2 Pod まで減り、失敗した更新が容量不足に直結する。
- **`ScheduleAnyway`:** Pod が置けないことはなくなるが、同じノードに偏り、ノード障害時に全停止する可能性が残る。偏りの許容は可用性の要件で決める。
- **`podAntiAffinity` による分散:** 1 ノード 1 Pod に制限され、レプリカがノード数を超えられない。`maxSkew` なら偏りの程度を指定できる。
- **PDB を `maxUnavailable: 1` にする:** 3 レプリカでは意味が同じだが、HPA でレプリカが増えると許容数が変わらず、割合で指定する方が拡張しやすい面もある。この Phase では「最低 2 つ」を明示する読みやすさを優先した。
- **metrics-server を Helm で入れる:** 公式の手順の 1 つだが、Helm の導入が Phase 7 以降の方針（ADR-0005）と合わない。
- **metrics-server の CA を kubelet に設定する（`--kubelet-insecure-tls` を使わない）:** 本番に近いが、kind の kubelet の証明書設定を変える必要があり、学習の主題から外れる。
- **KEDA やカスタムメトリクスで HPA を拡張する:** 実務で有力だが、追加コンポーネントが必要。`/metrics` の収集と合わせて Phase 8 以降に検討する。
- **負荷生成に外部ツール（k6、hey など）を入れる:** 精密な測定には向くが、追加の依存が必要。busybox の `wget` で CPU を使わせるだけなら足りる。

## Consequences

- API Pod の削除、ノードの退避、更新の途中で Ready にならない Pod があっても、Web/API の応答は途切れにくい。一方で、次のものは守られない。
  - DB は 1 レプリカの StatefulSet のまま。DB の停止、DB を載せたノードの喪失は、全体の停止になる（PV はノード内のディレクトリで、Pod はそのノードに固定される）。
  - 8082 の `port-forward` は 1 つの Web Pod にしかつながらず、その Pod が消えると接続が切れる。
  - 1 つの kind クラスター（1 つの Docker ホスト）は、ホストの障害に対する冗長性ではない。
- DB が止まると、API は Ready にならず宛先から外れ、利用者には 500 → 502 が見える。再起動は起きない。復旧は DB の復旧に依存する。
- ノードの drain は PDB の範囲でだけ API を退避できる。DB を載せたノードの drain は、DB を Pending にして停止させる。PDB は DB には効かない。
- HPA が増やせる範囲は `maxReplicas` と、ノードの空き、`requests` で決まる。使用率は requests 基準のため、requests を実態とずらすと、増減が過敏または鈍感になる。
- `--kubelet-insecure-tls` は証明書検証を省略する。ローカル専用の設定であり、EKS には持ち込まない。
- HPA が管理する Deployment の `replicas` をマニフェストに残しているため、値を変えて再適用すると HPA と競合し得る（未検証）。
- `preStop` の 5 秒分、Pod の終了が遅くなる。更新の所要時間も増える。
- Web・API の定義は Phase 3 と Phase 4 の 2 か所にあり、変更の反映は手動になる。

## Evidence

2026-11-10 に `workboard-phase4`（kind v0.33.0、Kubernetes v1.35.8、control-plane 1 + worker 2）で次を確認した。詳細は Lab 04 の「実装時の検証記録」にある。

- 初回の構築で、`topologySpreadConstraints` に `nodeTaintsPolicy` を付けない定義の API の 3 つ目の Pod が `didn't match pod topology spread constraints` で Pending になった。`nodeTaintsPolicy: Honor` で解消した。
- 実測値（`kubectl top`）: API はアイドル時に CPU 3〜5m・メモリ約 65Mi、負荷中に CPU 約 300〜340m・メモリ約 66Mi。Web は CPU 1〜2m・メモリ約 12Mi。PostgreSQL は CPU 約 24m・メモリ 31〜38Mi。
- API Pod の削除では、50 回の応答がすべて 200 だった。新しい Pod は約 8 秒で Ready になった。
- DB を `scale --replicas=0` にすると、応答は `000`（タイムアウト）→ 500 → 502 の順に変わった。API Pod は READY 0/1、RESTARTS 0 のままで、endpoints は空だった。DB を戻した約 3 秒後に 200 が戻った。
- Readiness のパスを誤った更新と、存在しないイメージの更新では、旧 3 Pod が Ready のまま残り、応答はすべて 200 だった。どちらも `rollout undo` で戻った。
- `rollout restart` を 3 回繰り返すと、`preStop` なしでは毎回 1 回の 502、`preStop` で 5 秒待つ定義では 0 回だった。
- 負荷で HPA は約 30 秒後に 6 Pod（`maxReplicas`）になり、ノード別は 3/3 だった。使用率は 6 Pod でも約 320% のままだった。負荷停止後、2.5 分以内に 3 Pod に戻った。
- PostgreSQL がいない worker の drain は約 8 秒で完了した。続けて残りの worker を drain すると、API の退避が `Cannot evict pod as it would violate the pod's disruption budget` で拒否され続けた。PDB のない PostgreSQL は退避されて Pending になった。
- `--kubelet-insecure-tls` を外すと、metrics-server が `x509: cannot validate certificate for 172.20.0.x because it doesn't contain any IP SANs` でノードの取得に失敗し、Ready にならなかった。

採用したバージョンと確認元（確認日 2026-11-10）:

- metrics-server v0.9.1（2026-10-29 公開。`components.yaml` の SHA-256 は `3c7f57cdbee0f57fb0259a150e8f6d6cb4f29d72d1aa5dce8803151dd6d4c2a1`。イメージ `registry.k8s.io/metrics-server/metrics-server:v0.9.1`）: [リリース](https://github.com/kubernetes-sigs/metrics-server/releases/tag/v0.9.1)、[README（要件・設定）](https://github.com/kubernetes-sigs/metrics-server/blob/v0.9.1/README.md)
- prometheus-client 0.26.0（PyPI の最新の安定版、2026-07-24 公開）: [PyPI](https://pypi.org/project/prometheus-client/)
- busybox 1.37.0（負荷生成用）: [Docker Hub](https://hub.docker.com/_/busybox)

参考資料:

- [Liveness, Readiness, and Startup Probes](https://kubernetes.io/docs/concepts/configuration/liveness-readiness-startup-probes/)
- [Resource Management for Pods and Containers](https://kubernetes.io/docs/concepts/configuration/manage-resources-containers/)
- [Pod Quality of Service Classes](https://kubernetes.io/docs/concepts/workloads/pods/pod-qos/)
- [Deployments（Rolling Update）](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [Pod Topology Spread Constraints](https://kubernetes.io/docs/concepts/scheduling-eviction/topology-spread-constraints/)
- [Disruptions と PodDisruptionBudget](https://kubernetes.io/docs/concepts/workloads/pods/disruptions/)
- [Safely Drain a Node](https://kubernetes.io/docs/tasks/administer-cluster/safely-drain-node/)
- [Horizontal Pod Autoscaling](https://kubernetes.io/docs/tasks/run-application/horizontal-pod-autoscale/)
- [Container Lifecycle Hooks（preStop）](https://kubernetes.io/docs/concepts/containers/container-lifecycle-hooks/)
- [Prometheus 計装のベストプラクティス（ラベルの値の数）](https://prometheus.io/docs/practices/instrumentation/)
