# Runbook: WorkBoard の障害調査（Phase 5）

対象は kind クラスター `workboard-phase5` の Namespace `workboard` です。ほかのクラスターには使いません。最初に `env.ps1`（Bash は `source .../env.sh`）を読み込み、以降のコマンドで `--context kind-workboard-phase5` を付けます（`-n` は `workboard`）。

## 調査の基本手順

1. **全体を見る:** `kubectl get pods,deploy,sts,job,svc -o wide` — どのリソースが `READY` でないか、`STATUS` は何か。
2. **イベントを見る:** `kubectl get events --sort-by=.lastTimestamp` — 直近の警告（`Failed`・`BackOff`・`Unhealthy`・`FailedCreate`）。
3. **1 つに絞って詳細を見る:** `kubectl describe pod <名前>` の `State` / `Last State` / `Events`。
4. **ログを見る:** `kubectl logs <Pod> [-c コンテナ] [--previous]`。起動できないコンテナは `--previous` が必要なことがある。
5. **つなぎ目を見る:** Service が Pod に届いているか（`kubectl get endpointslices -l kubernetes.io/service-name=<Service名>`）、名前解決（`getent hosts`）、通信（`wget` / `nc`）、権限（`kubectl auth can-i`）。
6. **復旧は設定のほうを直す:** 故障実験は `kubectl apply -k phases/05-security-and-failure/kustomize/overlays/kind` で元の定義に戻る。Pod を手で消すだけでは、設定が悪ければ同じ状態に戻る。

読み取りの調査だけなら `workboard-viewer`（読み取り専用）として実行できます。権限が足りるかは、先に `kubectl auth can-i <動詞> <リソース> --as=system:serviceaccount:workboard:workboard-viewer` で確かめます。

## 1. 存在しない image tag（ImagePullBackOff）

| 項目 | 内容 |
| --- | --- |
| 注入 | `kubectl apply -k phases/05-security-and-failure/experiments/bad-image-tag` |
| 症状 | 新しい Web Pod が `ErrImagePull` → `ImagePullBackOff`。古い Web Pod は `1/1` のまま（ロールアウトが進まない）。画面は使い続けられる |
| 観察 | `kubectl get pods -l app=workboard-web` / `kubectl describe pod <新しい Pod>` の Events / `kubectl get events --sort-by=.lastTimestamp` / `kubectl rollout status deploy/workboard-web --timeout=20s`（待っても完了しない） |
| 原因の読み方 | Events の `Failed to pull image "…": … not found`。イメージ名・タグの誤り、またはレジストリの認証・到達性（認証エラーなら `pull access denied`）。メッセージで切り分ける |
| 復旧 | `kubectl apply -k phases/05-security-and-failure/kustomize/overlays/kind`。`rollout status` で完了を確認 |
| 再発防止 | タグ（できれば digest）を固定し、デプロイ前に存在を確認する。Deployment の `maxUnavailable` により古い Pod が残る仕組みを理解する |

## 2. 誤った Service selector

| 項目 | 内容 |
| --- | --- |
| 注入 | `kubectl apply -k phases/05-security-and-failure/experiments/wrong-selector` |
| 症状 | API の Pod は `1/1 Running` なのに、Web 経由の API 呼び出しが 504（ブラウザーのタスク一覧が失敗） |
| 観察 | `kubectl get endpointslices -l kubernetes.io/service-name=workboard-api`（`ENDPOINTS` が `<unset>`） / `kubectl get svc workboard-api -o jsonpath='{.spec.selector}'` と `kubectl get pods --show-labels` を比べる / `kubectl exec deploy/workboard-web -- wget -qO- -T 4 http://workboard-api:8000/health/ready`（タイムアウト） |
| 原因の読み方 | Pod は健全で、Service の selector がどの Pod にも一致しないため、宛先が 0 件。ログやイベントには何も出ないことが多い |
| 復旧 | `kubectl apply -k phases/05-security-and-failure/kustomize/overlays/kind` |
| 再発防止 | selector とラベルの対応をレビューで確認する。デプロイ後に EndpointSlice が空でないことを確認する |

## 3. DB の DNS 名の誤り

| 項目 | 内容 |
| --- | --- |
| 注入 | `kubectl apply -k phases/05-security-and-failure/experiments/wrong-db-host` |
| 症状 | 新しい API Pod が `0/1 Running` のまま Ready にならない。古い API Pod が残るので画面は動く |
| 観察 | `kubectl describe pod <新しい API Pod>` の Events（`Readiness probe failed` の `context deadline exceeded` など） / `kubectl exec <新しい API Pod> -- printenv POSTGRES_HOST` / `kubectl exec <新しい API Pod> -- getent hosts workboard-postgres`（成功）と `getent hosts workboard-postgress`（失敗） / ログには起動メッセージのみで、DB のエラーが出ないことを確認する |
| 原因の読み方 | 起動はしているが readiness が DB 接続に失敗している。環境変数の値（`env` が ConfigMap より優先される）と、Service 名の綴りが一致しているかを見る |
| 復旧 | `kubectl apply -k phases/05-security-and-failure/kustomize/overlays/kind`、`kubectl rollout status deploy/workboard-api` |
| 再発防止 | 接続先を 1 か所（ConfigMap）で定義する。Service 名を直書きしない。readiness が失敗したままのロールアウトを検知する |

## 4. 権限不足（RBAC）

| 項目 | 内容 |
| --- | --- |
| 注入 | `kubectl -n workboard delete rolebinding workboard-viewer`（Role は残る） |
| 症状 | `workboard-viewer` として `kubectl get pods` すると `Error from server (Forbidden)` |
| 観察 | `kubectl -n workboard get pods --as=system:serviceaccount:workboard:workboard-viewer` のエラー文（主体・動詞・リソース・Namespace が書かれる） / `kubectl -n workboard auth can-i get pods --as=…`（`no`） / `kubectl -n workboard get role,rolebinding` / `kubectl -n workboard auth can-i --list --as=…` |
| 原因の読み方 | エラー文の「誰が・何を・どこで」と、Role（何ができるか）・RoleBinding（誰に結ぶか）の両方を確認する。Role があっても RoleBinding がなければ権限はない |
| 復旧 | `kubectl apply -k phases/05-security-and-failure/kustomize/overlays/kind`（RoleBinding が再作成される）、`auth can-i` が `yes` に戻る |
| 再発防止 | 必要な動詞とリソースだけを Role に書き、`can-i` を確認手順にする。広い権限（`*`、ClusterRole）で回避しない。Secret の読み取りは与えない |

## 5. memory limit による OOMKilled

| 項目 | 内容 |
| --- | --- |
| 注入 | `kubectl apply -k phases/05-security-and-failure/experiments/low-memory-limit` |
| 症状 | 新しい API Pod が `CrashLoopBackOff`（`RESTARTS` が増える）。古い API Pod が残るので画面は動く |
| 観察 | `kubectl describe pod <新しい API Pod>` の `Last State: Terminated`、`Reason: OOMKilled`、`Exit Code: 137`、`Limits: memory: 20Mi` / `kubectl logs <Pod> --previous`（アプリのエラーがなくログが途中で切れる） / `kubectl get pod <Pod> -o jsonpath='{.status.containerStatuses[0].lastState}'` |
| 原因の読み方 | `OOMKilled`・137 は、コンテナがメモリの `limits` を超えて強制終了されたことを示す。アプリのバグとは限らない。limits が使用量に対して小さすぎないかを見る |
| 復旧 | `kubectl apply -k phases/05-security-and-failure/kustomize/overlays/kind` |
| 再発防止 | 実測（Phase 4 のメトリクスなど）に基づいて requests/limits を決める。メモリ使用量を監視する。CPU は limits ではなく requests を基本にする |

## 6. NetworkPolicy による遮断（Pod は Ready なのに通信できない）

| 項目 | 内容 |
| --- | --- |
| 注入 | `kubectl -n workboard delete networkpolicy api-traffic`（API の ingress/egress の許可が消え、default deny が残る） |
| 症状 | すべての Pod が `Running`/Ready のまま。画面からのタスク一覧が 504（Web から API に届かない）。Pod の状態、イベント、API のログには何も出ない |
| 観察 | `kubectl exec deploy/workboard-web -- wget -qO- -T 3 http://workboard-api:8000/health/ready`（タイムアウト） / `kubectl exec deploy/workboard-web -- nc -zv -w 3 workboard-api 8000`（タイムアウト。`Connection refused` ではなく**タイムアウト**は破棄を疑う） / `kubectl get networkpolicy` と `kubectl describe networkpolicy <名前>` で、対象 Pod と許可を確認する / 名前解決は成功する（DNS egress が許可されているため）ことも確認する |
| 原因の読み方 | `refused` は相手が応答して拒否、`timed out` はパケットが届かないか破棄されている状態。名前解決が成功し、Endpoint もあるのに接続だけタイムアウトするなら NetworkPolicy を疑う。kubelet の readiness probe はノードから送られるため、NetworkPolicy の影響を受けず、Ready のままになりうる |
| 復旧 | `kubectl apply -k phases/05-security-and-failure/kustomize/overlays/kind`（`api-traffic` が再作成される） |
| 再発防止 | 経路図（`architecture.md`）と NetworkPolicy を一致させ、許可と拒否の両方を試験する。readiness にはアプリ間の通信を含める |

## 7. Pod Security で作成が拒否される（参考）

`kubectl apply -f phases/05-security-and-failure/experiments/violating-pod.yaml` は `Forbidden: violates PodSecurity "restricted:v1.35"` で拒否されます。Deployment の場合はオブジェクトは受理され、Pod が作られずに `kubectl get events` / `kubectl describe replicaset` に `FailedCreate` が出ます。メッセージに違反項目がすべて列挙されるので、`securityContext` の対応する設定を直します。

## 8. 起動時に read-only のエラー（参考）

`readOnlyRootFilesystem: true` のコンテナが書き込もうとすると、`Read-only file system` でクラッシュします。ログのパスを確認し、そのパスを emptyDir にマウントします（`/tmp`、nginx の `/etc/nginx/conf.d`・`/var/cache/nginx`・`/run`、PostgreSQL の `/var/run/postgresql`）。

## 任意: k9s で同じ障害を観察する

kubectl で上の Runbook を完成させた**後に**、同じ障害を k9s で見て、画面と kubectl の操作を対応づけます。k9s は次の条件で使います。

- 専用 kubeconfig の kind クラスターだけで使う: `k9s --kubeconfig .kube/workboard-phase5.yaml --context kind-workboard-phase5 -n workboard --readonly`。`--readonly` により編集・削除の操作を無効にする。
- 編集・削除・`exec` は Runbook の手順に含めない。復旧は `kubectl apply -k` で行う。
- k9s が表示・操作できる範囲は k9s の機能ではなく、kubeconfig の資格情報に対する **RBAC** で決まる。読み取り専用の主体では、一覧に表示できないリソースがある。

| k9s の画面（キー） | 対応する kubectl |
| --- | --- |
| `:pods` | `kubectl get pods -w` |
| Pod で `d` | `kubectl describe pod <名前>` |
| Pod で `l` | `kubectl logs <名前>` |
| `:events` | `kubectl get events` |
| `:svc` | `kubectl get svc` |
| `:netpol` | `kubectl get networkpolicy` |

この環境では k9s を導入していないため、k9s の画面・キー操作は未検証です。導入と版の確認は、使う場合に [k9s](https://k9scli.io/) の公式手順で行います。
