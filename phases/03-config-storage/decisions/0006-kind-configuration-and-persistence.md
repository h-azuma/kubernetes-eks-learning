# ADR-0006: kind での設定分離と DB 永続化

> **読む順番:** この ADR には Lab 03 の設計課題の答えにあたる内容が含まれます。先に [Phase 3 のラボ](../README.md) の設計課題に自分で答えてから読み、自分の考えと比べてください。

## Status

提案（2026-11-10）。Phase 3 に適用。学習者が Lab 03 の設計課題に回答し、内容を確認したうえで「採用」に変更する。

## Context

Phase 2 では、DB を emptyDir の Deployment で動かしたため、DB Pod を作り直すとタスクとスキーマが消えた。設定値と学習用のダミーパスワードも、DB・API・Job の各マニフェストに直接書いていた（ADR-0003）。

Phase 3 では、次の 3 点を kind 上で観察できる構成にしたい。

- Pod の寿命とデータの寿命を分ける。
- 設定値と機密情報を、アプリの定義から切り離す。
- 環境ごとの差分を Kustomize で表す。

将来は EKS（Phase 6）と RDS（Phase 7）に移る予定なので、AWS の構成に移っても共通部分を書き換えずに済む分け方が必要になる。一方で、Lab 02 は学習途中であり、その手順と環境は壊したくない。

## Decision

### 1. DB は StatefulSet + PVC とし、RDS は Phase 7 で比較する

- PostgreSQL を StatefulSet で動かす。`volumeClaimTemplates` で 1Gi・ReadWriteOnce の PVC を Pod ごとに作る。
- governing Service は headless Service 1 つとし、アプリからの接続先も兼ねる。
- `PGDATA` はマウント先のサブディレクトリにする。kind では不要だが、EBS など `lost+found` を持つボリュームに移したときの初期化失敗を避けるため。
- DB の定義は `kustomize/components/postgres-local`（Kustomize の Component）に分ける。RDS を使う環境では、この Component を含めないだけで済むようにする。

### 2. StorageClass は指定せず、クラスターの既定に任せる

kind の既定 `standard`（local-path）を使う。EKS では、同じ定義のまま gp3 などの既定 StorageClass が使われる。

### 3. 設定は ConfigMap、パスワードは Git 管理外のファイルから作る Secret にする

- 機密でない設定（DB のホスト名・DB 名・ユーザー名、Web から見た API のホスト名）は、overlay の `configMapGenerator` で作る。Web・API・DB で 1 つの ConfigMap を共有する。
- パスワードは `secretGenerator` で `secrets/db.env` から作る。このファイルは `.gitignore` の対象で、存在しなければ構築スクリプトがランダムな値を生成する。値は画面やログに出さない。リポジトリには、ダミー値だけの `db.env.example` を置く。
- generator が名前にハッシュを付けるので、値を変えると参照先の名前も変わり、Pod が新しい設定で作り直される。

### 4. migration Job は毎回削除してから適用する

- 構築スクリプトは、Job を削除してから `kubectl apply -k` する。Job の Pod テンプレートは作成後に変更できず、ConfigMap や Secret のハッシュ付き名前が変わると `field is immutable` で適用に失敗するため。
- `alembic upgrade head` は何度実行しても安全（冪等）なので、Job を作り直しても問題ない。
- DB の初回起動が遅くても再試行回数を使い切らないよう、`pg_isready` で DB を待つ initContainer を付ける。

### 5. Phase 2 のマニフェストは Lab 02 用にそのまま残す

Phase 2 のマニフェスト（`phases/02-kind-basics/manifests/`）は変更しない。Web・API の定義は `kustomize/base` と重複するが、Phase を独立させ学習段階を再現できるようにするための意図的な重複とする（[ADR-0007](../../../docs/adr/0007-phase-directory-layout.md)）。Phase 3 は別クラスター `workboard-phase3`（専用 kubeconfig、port-forward は 8081）で動かす。

## Alternatives

- **最初から RDS を使う:** 本番に近いが、AWS 費用がかかり、EKS・IAM・ネットワークの学習要素が同時に増える。PVC と StorageClass を観察する機会もなくなる。
- **Deployment + PVC:** 1 レプリカなら動くが、Pod ごとの固定の名前と、Pod ごとの PVC の対応を学べない。レプリカを増やしたときに同じ PVC を共有する誤りも起こしやすい。
- **StorageClass を明示する:** 環境依存の名前が base や Component に入り、EKS への移行時に書き換えが必要になる。
- **パスワードをマニフェストに直接書く（Phase 2 の方式）:** 実際の値をリポジトリに入れる習慣につながる。
- **Sealed Secrets・SOPS・External Secrets Operator・AWS Secrets Manager:** 実務では有力だが、追加のコンポーネントや AWS が必要になる。設計書 §9.1 に従い、この段階では導入しない。
- **migration を `generateName` の Job にする:** `kubectl apply` とは相性が悪く、Kustomize で管理しにくい。
- **API の起動時に migration を実行する:** 手順は単純になるが、レプリカを増やしたときに同時実行が起こり得る。また、スキーマ準備と API の責任を分けられない。
- **Helm hook や Argo CD の PreSync で migration を実行する:** ツールの導入が前提になる。Phase 8 以降の比較対象とする（ADR-0005）。
- **Phase 2 の構成も Kustomize に移す:** 重複はなくなるが、Lab 02 の手順と学習中の環境が変わってしまう。

## Consequences

- DB Pod を作り直しても、PVC が残る限りタスクは残る。ただし、次のものは守られない。
  - Node（kind のノードコンテナ）を失うこと。PV はノード内のディレクトリにある。
  - PVC を削除すること。reclaim policy が `Delete` なので、PV とデータも消える。
  - バックアップと高可用性。
- Secret の値は base64 で表されているだけで、暗号化ではない。保存時の暗号化と、RBAC による読み取り制限は未設定。
- DB を初期化した後に `db.env` の値だけを変えると、DB 側のパスワードと一致しなくなり、migration Job と新しい API Pod が失敗する（Lab 03 の故障実験）。`db.env` を失った場合も、既存の PVC と食い違う。
- ConfigMap を 1 つで共有しているため、Web や API だけに関わる値を変えても、DB の Pod まで作り直される（データは PVC に残る）。単純さを優先したトレードオフで、値が増えたら分割を検討する。
- generator で作った古い ConfigMap と Secret は、自動では削除されずに残る。
- 構築スクリプトの Job の削除から再作成までの間は、Job が存在しない時間がある。Argo CD などに移すときは、方式を再設計する必要がある。
- Web・API の定義を Phase 2 と Phase 3 の 2 か所で管理する。Phase 2 の学習を終えた後に、整理を検討する。

## Evidence

2026-11-10 に `workboard-phase3`（kind v0.33.0、Kubernetes v1.35.8）で次を確認した。詳細は Lab 03 の「実装時の検証記録」にある。

- `kubectl kustomize phases/03-config-storage/kustomize/overlays/kind` で、ハッシュ付きの ConfigMap 名・Secret 名と、参照側の書き換えを確認した。
- DB Pod を削除すると UID は変わったが、PVC と PV は同じものが使われ、タスクは残った。
- StatefulSet を削除しても PVC と PV は残り、再作成後もタスクは残った。PVC を削除すると PV も消え、再構築後は空の DB になった。
- Secret の値だけを変えると migration Job が `password authentication failed` で失敗し、新しい API Pod は Ready にならなかった。
- `kubectl auth can-i get secrets` は、管理者が yes、`workboard:default` ServiceAccount が no だった。

参考資料:

- [StatefulSets](https://kubernetes.io/docs/concepts/workloads/controllers/statefulset/)
- [Persistent Volumes](https://kubernetes.io/docs/concepts/storage/persistent-volumes/)
- [ConfigMaps](https://kubernetes.io/docs/concepts/configuration/configmap/)
- [Secrets](https://kubernetes.io/docs/concepts/configuration/secret/)
- [Declarative Management Using Kustomize](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/)
- [Jobs](https://kubernetes.io/docs/concepts/workloads/controllers/job/)
- [PostgreSQL 公式 Docker イメージ（PGDATA）](https://hub.docker.com/_/postgres)
