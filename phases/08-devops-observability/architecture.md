# Phase 8: 配信と可観測性

```mermaid
flowchart LR
    Dev[開発者] -->|"push / PR"| GH[GitHub]
    GH --> CI["CI: ci.yaml<br/>テスト・ビルド・kustomize・terraform 検証"]
    GH -->|"手動実行 + environment lab の承認"| CD["CD: cd.yaml"]
    CD -->|"OIDC の一時認証"| AWSRole["IAM ロール<br/>ECR push / EKS describe"]
    AWSRole --> ECR[ECR]
    AWSRole --> EKS["EKS: Phase 7 の eks overlay<br/>kubectl apply"]

    subgraph Kind["kind クラスター workboard-phase8"]
        Repo["argocd: repo-server"] --> Ctrl["argocd: application-controller"]
        Ctrl -->|"比較・同期"| WB["workboard namespace<br/>Web 2 / API 3 / PostgreSQL / migrate Job"]
        Up["scripts/up"] -->|"db.env から作成"| Secret["Secret workboard-db<br/>Git 管理外・Argo CD 管理外"]
        Secret -.->|参照| WB
        Prom["monitoring: Prometheus"] -->|"kubernetes_sd で Pod を発見<br/>15 秒ごとに /metrics"| API["API Pod x3"]
        Manual["kubectl の手動変更"] -.->|drift| WB
    end
    GH -.->|"Git を取得"| Repo
    Browser[ブラウザー] -->|"8084 / 8085 / 8087 の port-forward"| Kind
```

## 構成

| 要素 | 役割 |
| --- | --- |
| `.github/workflows/ci.yaml` | push・PR ごとに API・Web・ポータルのテスト/ビルド、イメージのビルド、Kustomize の生成、Terraform の検証、スクリプトの構文確認 |
| `.github/workflows/cd.yaml` | 手動実行。environment `lab` の承認後、OIDC で AWS に接続し、ECR へ push、EKS へ適用 |
| `terraform/` | GitHub OIDC プロバイダー、CD 用 IAM ロール（特定のリポジトリ・environment だけが引き受け可）、EKS の access entry（`workboard` namespace の編集権限） |
| kind クラスター `workboard-phase8` | control-plane 1 と worker 2。Argo CD、Prometheus、WorkBoard が入る |
| Argo CD v3.6.1 | `argocd` namespace。Application `workboard` が `kustomize/overlays/kind` を Git から取得して比較・同期する（既定は手動同期） |
| Prometheus v3.15.1 | `monitoring` namespace。`workboard` の API Pod（`app=workboard-api`、ポート 8000）だけを対象にする。保存は `emptyDir` |
| Secret `workboard-db` | `scripts/up` が `db.env` から作成。Git にも Argo CD の管理対象にも入らない |
| 移行 Job | Argo CD の `Sync` hook。同期のたびに作り直す |
| `slo.md` | 学習用 SLI/SLO の定義 |

ポートは、WorkBoard 8084、Argo CD 8085、Prometheus 8087（いずれも `kubectl port-forward` で 127.0.0.1 にだけ公開）。

Phase 4 との違いは、HPA と metrics-server を含まないこと、`overlays/kind` が Secret を生成しないこと、移行 Job に Argo CD の hook があることです。DB（PostgreSQL）は Phase 4 と同じ 1 Pod の StatefulSet で、単一障害点のままです。
