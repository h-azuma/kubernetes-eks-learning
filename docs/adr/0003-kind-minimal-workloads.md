# ADR-0003: kind の最小ワークロードと一時 DB

## Status

採用（2026-11-08）。Phase 2 に適用。

## Context

Phase 1 と同じ WorkBoard で Pod・ReplicaSet・Deployment・Service を観察したい。クラウド費用や Ingress Controller、永続化・設定管理の学習を同時に追加せず、ローカルで再現できる最小構成が必要。

## Decision

- kind v0.33.0 と、そのリリースが提供する Kubernetes v1.35.8 の digest 固定ノードイメージを使う。1.35 は確認時点のサポート対象で、既存 kubectl v1.34.1 との minor 差は1。kubectl を追加・上書きする必要がない。
- Windows の kind は SHA-256 検証後に Git 除外の `.tools/kind.exe` へ配置する。グローバル PATH を変更しない。専用 kubeconfig で既存環境と分離する。
- ノードは1台。Web/API は Deployment と ClusterIP Service。入口はループバックへの port-forward。
- API/Web は既存 Dockerfile から `:kind` タグをビルドし、`kind load docker-image` でノードに投入する。`imagePullPolicy: Never` により、投入忘れをレジストリへのアクセスで隠さない。PostgreSQL は公式パッチタグを使い `IfNotPresent` とする。
- PostgreSQL は Recreate 戦略の Deployment、保存先は emptyDir。DB の準備完了後に単独 Job で既存 Alembic migration を実行する。成功後に Web/API を適用する。
- Nginx の設定は1つのテンプレートを共有する。公式 entrypoint の local-resolvers と envsubst を使い、DNS は実行環境から取得し、API Service 名だけ環境変数で指定する。
- DB/API/Web の readiness は初期構築と Service 宛先の確認に必要な最小限に留める。

## Alternatives

- kind の最新既定 K8s 1.37: 既存 kubectl 1.34 との対応範囲を外れるため、別途 kubectl の導入が必要。
- 最初から PVC/StatefulSet: データは残るが、Pod の寿命とデータの寿命の違いを段階的に学びにくい。
- Ingress Controller: 入口の構成要素が増える。まず Service の観察を優先する。
- Compose 用と Kubernetes 用の Nginx 設定を複製: 接続先以外の同じ設定を二重管理することになる。

## Consequences

アプリコードとイメージの構築方法を再利用できる。API Pod が置き換わっても Service への接続先は維持できる。一方、DB Pod を削除すると全タスクとスキーマを失う。migration の再実行でスキーマは戻るがタスクは復元されない。

plain YAML の読みやすさと Phase 3 での設定分離を優先し、学習専用ダミー DB 接続値は DB/API/Job に明記する。共通化のためだけの生成コード・YAML List・ConfigMap/Secret は今は追加しない。この小さな重複は意図的なトレードオフで、実パスワードの管理方法として流用しない。

再実行した構築スクリプトはクラスターや DB を削除しない。完了済み Job は自動再実行されないため、DB 再作成時は Job を明示的に削除・再適用する。ローカルアプリコードを更新して同じタグを再投入した場合は、Deployment の rollout restart が別途必要。

## Evidence

2026-11-08 に以下を確認。kind v0.33.0 の release notes で v1.35.8 の digest を確認し、クラスター定義に固定した。Docker 公式 Nginx 1.30.6 の `/docker-entrypoint.d/15-local-resolvers.envsh` と `20-envsubst-on-templates.sh` の実装も確認した。

- [kind v0.33.0 リリース](https://github.com/kubernetes-sigs/kind/releases/tag/v0.33.0)
- [kind Quick Start](https://kind.sigs.k8s.io/docs/user/quick-start/)
- [Kubernetes Version Skew Policy](https://kubernetes.io/releases/version-skew-policy/)
- [Deployment](https://kubernetes.io/docs/concepts/workloads/controllers/deployment/)
- [Service](https://kubernetes.io/docs/concepts/services-networking/service/)
- [emptyDir](https://kubernetes.io/docs/concepts/storage/volumes/#emptydir)
- [Nginx 公式 Docker イメージの entrypoint](https://github.com/nginx/docker-nginx/tree/master/entrypoint)
