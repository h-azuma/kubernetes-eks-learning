# ADR-0010: kind でのセキュリティ設定と障害調査の構成

> **読む順番:** この ADR には Lab 05 の設計課題の答えにあたる内容が含まれます。先に [Phase 5 のラボ](../README.md) の設計課題に自分で答えてから読み、自分の考えと比べてください。

## Status

提案（2026-11-10）。Phase 5 に適用。学習者が Lab 05 の設計課題に回答し、内容を確認したうえで「採用」に変更する。

## Context

Phase 3 までの WorkBoard は、Pod が root で動くものを含み、Namespace に Pod の制限がなく、Pod 間の通信は無制限で、ServiceAccount も既定のままだった。Phase 5 では、権限・通信・実行ユーザーを最小化し、意図的に作った障害を調査して復旧できる状態にしたい。

設計書は「kind 標準のネットワークで NetworkPolicy が効くと決めつけない」ことを求めている。NetworkPolicy は API オブジェクトにすぎず、遮断は CNI が行う。また、Phase 5 の Done は「障害を再現・発見・復旧する Runbook」である。

## Decision

### 1. NetworkPolicy 対応の CNI として Calico v3.33.0 を導入する

- `cluster.yaml` で `networking.disableDefaultCNI: true` とし、`podSubnet` を Calico の既定プールと同じ `192.168.0.0/16` にする。ノードイメージは Phase 3 と同じ `kindest/node:v1.35.8`（digest 固定）。
- `up` が公式の manifest 方式（`calico.yaml`、v3.33.0 に固定）を `kubectl create` で導入し、DaemonSet・Deployment・Node の準備完了を待ってからアプリを適用する。CRD が大きく `apply` では上限を超えることがあるという公式の注意に従う。
- 構築スクリプトは `tools/` の `Initialize-KindCluster`（Bash は `initialize_kind_cluster`）の待ち時間の引数を空にして、`--wait` なしでクラスターを作る。既定 CNI のない kind は CNI を入れるまで Node が Ready にならず、`--wait` は失敗するため。既存クラスターと kubeconfig の安全確認は共通関数のものをそのまま使い、CNI 導入後に Node の Ready を待つ。
- 「NetworkPolicy が効く」ことは、許可された通信が成功し、許可されていない通信が失敗する実測で確認する。

### 2. Pod Security Standards は restricted を enforce・warn・audit のすべてに設定する

- WorkBoard の 3 つのワークロード（Web・API・PostgreSQL）は、すべて restricted の要件を満たせることを実測した。満たせるのに緩いレベルを選ぶ理由がないため、`enforce: restricted` にする。
- `warn` と `audit` も同じ restricted にする。enforce は Pod にしか効かず、Deployment や Job は受理されて ReplicaSet の段階で Pod が拒否される。`warn` により、`kubectl apply` の時点で違反に気づける。
- バージョンは `v1.35`（クラスターと同じ minor）に固定する。`latest` にすると、クラスターの更新で基準が変わり、既存の Pod が突然拒否されうる。更新はバージョンを意識的に上げる作業にする。
- `kube-system` など、システム用の Namespace には設定しない（Calico や CoreDNS は restricted を満たさない）。

### 3. ワークロードごとの最小権限

- ワークロードごとに ServiceAccount を作り、`automountServiceAccountToken: false` にする（Pod から Kubernetes API を呼ぶ必要がないため）。`default` の ServiceAccount は使わない。
- すべてのコンテナで `allowPrivilegeEscalation: false`、`capabilities.drop: [ALL]`、`readOnlyRootFilesystem: true`、Pod で `runAsNonRoot: true` と `seccompProfile: RuntimeDefault` を設定する。書き込みが必要な場所（`/tmp`、nginx の設定・キャッシュ・PID、PostgreSQL のソケット）だけ emptyDir にする。
- メモリの `limits` を設定する。CPU の `limits` は設定しない（スロットリングによる遅延を避ける。`requests` でスケジューリングの目安を与える）。

### 4. Web イメージ（`app/web`）は変更せず、マニフェストで非 root 化する

- nginx 公式イメージは、非特権ユーザーでも `runAsUser: 101`、書き込み先の emptyDir、80 番を使うための sysctl があれば動く。これで Phase 1〜3 の Compose とマニフェストに影響を与えずに restricted を満たせる。
- 80 番の待ち受けには、sysctl `net.ipv4.ip_unprivileged_port_start=0` を使う。この sysctl は Kubernetes の「安全な sysctl」で、capability の `NET_BIND_SERVICE` を追加する方法は、非 root プロセスに capability が引き継がれないことがあり、挙動が環境に依存する。
- 将来、非特権ポートで待ち受ける専用イメージ（`nginxinc/nginx-unprivileged` など）に切り替える選択もあるが、現時点では `app/web` の共有と Phase の独立性を優先する。

### 5. RBAC は読み取り専用の Role を ServiceAccount に結びつける学習用の構成にする

- Namespace 内の Role（Pod・ログ・Service・EndpointSlice・イベントなどの読み取りのみ。Secret と書き込みは含めない）を RoleBinding で `workboard-viewer` ServiceAccount に結びつける。`kubectl auth can-i --as=system:serviceaccount:workboard:workboard-viewer` で許可と拒否を確かめる。
- ClusterRole / ClusterRoleBinding は使わない。権限の範囲を Namespace に閉じる。
- アプリの Pod に付ける RBAC は存在しない（API を呼ばないため）。viewer は人間や調査ツールが使う主体を模したもの。

### 6. NetworkPolicy は default deny + 経路ごとの許可にする

- Namespace 全体の ingress/egress を拒否し、DNS（kube-dns、UDP/TCP 53）と、Web→API、API→DB、migrate→DB、loadgen→Web だけを許可する。許可は、Pod のラベルとポートで絞る。
- 許可する通信と拒否する通信の両方を実測で確認する。

### 7. 障害注入は「パッチ 1 つの Kustomization」にする

- 各故障は `experiments/<名前>/kustomization.yaml`（overlay + パッチ 1 つ）で、`apply -k` で注入し、同じ overlay を `apply -k` して復旧する。独自のスクリプトや Helm は使わない。ConfigMap の値の変更は Job の `immutable` エラーを呼ぶため、API の `env` を上書きする形にした。

### 8. k9s は任意とし、Runbook を kubectl で完成させた後に使う

[ADR-0005](../../../docs/adr/0005-kubernetes-ecosystem-tools.md) に従う。専用 kubeconfig の kind クラスターだけで使い、編集・削除は手順に含めない。

## Alternatives

- **kind 既定の CNI（kindnet）のまま NetworkPolicy を作る:** 作成はできるが、遮断する CNI かどうかを確認せずに「効いた」と判断する危険がある。この Phase の学習対象はまさにその確認なので、CNI を明示的に選ぶ。
- **Cilium:** NetworkPolicy に加え可視化や L7 の制御もできるが、学習対象が増える。Calico のほうが kind での導入手順が公式に載っており、この Phase の範囲（L3/L4 の NetworkPolicy）には十分。
- **Calico をオペレーター方式で導入:** 公式の推奨方式。ただし Tigera Operator とカスタムリソースの層が増える。この Phase は単一ノードの学習用であり、manifest 方式の 1 ファイルで足りる。
- **PSS を baseline にする:** 設定は少なくて済むが、root 実行や書き込み可能なルートを許してしまい、非 root 化の効果を測れない。
- **`pod-security.kubernetes.io/enforce` だけ設定する:** Deployment の適用時に警告が出ず、ReplicaSet のイベントを見るまで原因に気づけない。
- **`nginxinc/nginx-unprivileged` に変更:** 8080 番での待ち受けなどが前提になり、Compose や Phase 1〜3 のマニフェストにも影響が及ぶ。
- **RBAC を ClusterRole で広く付与:** 管理は楽だが、最小権限に反する。

## Consequences

- Calico の導入で、クラスター作成に数分余計にかかり、イメージの取得にネットワークが必要になる。
- 構築スクリプトは、`tools` の共通関数と一部が重複する（クラスター作成の分岐）。`--wait` を選べるように共通関数を拡張すれば、重複を解消できる。
- 非 root 化のため、書き込み先の emptyDir を明示する必要がある。アプリを更新して書き込み先が増えると、`ReadOnlyFileSystem` 系のエラーで Pod が失敗する。Runbook に調べ方を載せる。
- NetworkPolicy は許可の合算で、port-forward は対象外。Ingress / Gateway の導入時（Phase 6 以降）は、そのコントローラーからの通信を許可し直す必要がある。
- Secret は環境変数として渡されるため、Secret を読める主体と `exec` できる主体は値を取得できる。保存時暗号化、外部の Secret 管理は別の設計（Phase 7 以降）。

## Evidence

2026-11-10 に公式資料で確認した（確認日 2026-11-10）。

- [Calico: Quickstart for Calico on kind](https://docs.tigera.io/calico/latest/getting-started/kubernetes/kind) — 最新は Calico 3.33（manifest は v3.33.0）。kind 設定は `disableDefaultCNI: true` と `podSubnet: 192.168.0.0/16`。manifest 方式は `kubectl apply -f .../v3.33.0/manifests/calico.yaml`。CRD が大きい場合は `create` または `replace` を使う。
- [Kubernetes: Pod Security Admission](https://kubernetes.io/docs/concepts/security/pod-security-admission/) — Namespace ラベルの `enforce` / `audit` / `warn` とバージョン固定。enforce は Pod にのみ適用され、warn と audit は Deployment 等のワークロードにも適用される。
- [Kubernetes: Pod Security Standards](https://kubernetes.io/docs/concepts/security/pod-security-standards/) — restricted の要件。
- [Kubernetes: Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/) — NetworkPolicy は対応するネットワークプラグインが必要。
- [Kubernetes: Using RBAC Authorization](https://kubernetes.io/docs/reference/access-authn-authz/rbac/)
- [Kubernetes: Configure Service Accounts for Pods](https://kubernetes.io/docs/tasks/configure-pod-container/configure-service-account/)
- [Kubernetes: Using sysctls in a Kubernetes Cluster](https://kubernetes.io/docs/tasks/administer-cluster/sysctl-cluster/)
- [k9s](https://k9scli.io/)

実測の結果は README の「実装時の検証記録」に記載する。
