# Kubernetes / Amazon EKS Hands-on Learning Repository — 設計書

> **Project name:** `kubernetes-eks-learning`  
> **Sample app:** `WorkBoard`  
> **Document status:** v1.0 / implementation specification  
> **Design date:** 2026-11-08  
> **Audience:** Kubernetes / EKS の基礎から設計・運用判断まで習得したいインフラ／DevOpsエンジニア、および実装支援に利用する Codex

---

## 0. この文書の使い方（Codex は必ず最初に読む）

この文書は、ローカルの Codex に渡す**実装可能なプロジェクト設計書**である。単なる完成物の作成ではなく、ハンズオンによって設計判断力を高めることを最優先とする。

**Codex の作業原則**

1. **明示されたフェーズだけを実装する。** 先のフェーズの機能を先回りして大量実装しない。
2. 各フェーズでは「今回作るもの」「学ぶこと」「検証方法」「設計判断」を説明する。完成コードの納品だけで終わらない。
3. 実装前に短い作業計画を提示し、実装後に実行したコマンド、テスト結果、変更ファイル、残課題を報告する。
4. 設計上の選択肢が複数あるときは、最小構成を選び、採用理由と代替案を `docs/adr/` に記録する。
5. ユーザーが明示的に許可するまでは **AWS の有料リソースを作らない**。`terraform apply`、AWSリソース作成、課金が発生し得るコマンドは自動実行しない。`terraform destroy` も実施前に対象と影響を確認する。
6. 機密情報、実パスワード、実際の AWS アカウントID、認証情報、Terraform state を Git にコミットしない。
7. バージョンやサービス仕様は実装時に公式ドキュメントで確認し、依存関係のバージョンは適切に固定する。推測でサポートバージョンを決めない。
8. 既存の機能を壊さず、学習フェーズが進むごとに同一アプリケーションを発展させる。
9. 実装可能な範囲は自動化するが、ラボの**問いと観察ポイントは省略しない**。各ラボをユーザーが自ら検証できる状態にする。
10. 不明な環境依存事項は `preflight` で検出し、実行不能な検証は「未実施」と報告する（成功したと捏造しない）。

### 受け入れの最終像

- ローカルの Docker Compose で WorkBoard が動作する。
- ローカル kind クラスターで同じアプリを Kubernetes にデプロイできる。
- コントローラー、サービスディスカバリ、設定、永続化、スケジューリング、障害復旧、スケーリングを**実験して説明できる**。
- Terraform を用いた EKS 構成を設計し、ユーザーが許可した場合のみ AWS に作成・検証できる。
- EKS と ECS の採用判断を、要件・コスト・運用負荷・移植性の観点から文書化できる。

---

## 1. ゴールと非ゴール

### 1.1 到達目標

| 能力 | 到達条件 |
| --- | --- |
| Kubernetes 概念理解 | Pod、ReplicaSet、Deployment、Service、StatefulSet、PV/PVC、ConfigMap/Secret、HPA、RBAC の役割を説明できる |
| ワークロード設計 | アプリの特性から適切なリソース、リソース要求、Probe、レプリカ数、デプロイ方式を選べる |
| 障害対応 | `kubectl describe`、`logs`、`events`、`top` 等を使い、障害の観察・原因分析・復旧を行える |
| AWS 統合 | EKS の責任分界、VPC、IAM、ALB、ECR、RDS、Pod Identity の関係を説明できる |
| IaC / DevOps | Terraform、CI、マニフェスト管理、継続的デリバリー、監視を実装・比較できる |
| 技術選定 | 同一要件を ECS と EKS に当てはめ、採用・不採用の理由を ADR にまとめられる |

### 1.2 非ゴール

- 複雑な業務アプリ・美しいフロントエンドを開発すること。
- 認証基盤、決済、マルチテナント、マイクロサービス分割を最初から構築すること。
- Service Mesh、Karpenter、GitOps、Helm、OpenTelemetry などを序盤から全部投入すること。エコシステムのツールは、素の `kubectl` とマニフェストで仕組みを理解した後に、必要になったフェーズで段階的に導入する（[ADR-0005](adr/0005-kubernetes-ecosystem-tools.md)）。
- 本番システムと同等の SLA、ゼロダウンタイム、セキュリティ保証を主張すること。
- クラウド環境を常時起動すること。

**優先順位:** 学習効果・再現性 > 設計判断の明瞭さ > 運用のしやすさ > 新技術の採用数。

---

## 2. 題材アプリ: WorkBoard

### 2.1 サービス概要

個人向けの簡易タスク管理サービス。タスクを作成・編集・一覧・削除し、ステータスを更新できる。業務機能を最小化することで、インフラの挙動を観察しやすくする。

**MVP のユースケース**

1. タスクを作成する（タイトル必須・説明任意）。
2. タスク一覧を取得し、ステータスで絞り込む。
3. タスクのタイトル、説明、ステータスを更新する。
4. タスクを削除する。
5. 画面から上記操作を実施し、ブラウザ再読込後もデータが残る。
6. API の稼働・DB への接続性をそれぞれ調べる。

**データモデル**

```text
Task
  id           UUID (primary key)
  title        string (1..120 chars)
  description  nullable string (max 2000 chars)
  status       enum: TODO | IN_PROGRESS | DONE
  created_at   UTC timestamp
  updated_at   UTC timestamp
```

- MVP はユーザーアカウントなし、個人のローカル学習用途を想定。
- 公開 EKS 環境で認証なしの API を恒常的にインターネット公開しない。EKS の ALB 公開は**短時間の検証用途**とし、公開制限・セキュリティグループ・後片付けを必須とする。
- 外部公開が必要な場合は非機密のダミーデータのみ使用する。

### 2.2 API インターフェース

| Method | Path | 動作 | 主な成功レスポンス |
| --- | --- | --- | --- |
| `GET` | `/api/v1/tasks` | 一覧・`status` 絞り込み | 200 |
| `POST` | `/api/v1/tasks` | 新規登録 | 201 |
| `GET` | `/api/v1/tasks/{id}` | 詳細取得 | 200 |
| `PATCH` | `/api/v1/tasks/{id}` | 部分更新 | 200 |
| `DELETE` | `/api/v1/tasks/{id}` | 削除 | 204 |
| `GET` | `/health/live` | プロセスの生存確認（DB に依存しない） | 200 |
| `GET` | `/health/ready` | リクエスト受け入れ可否（DB 接続性を確認） | 200 / 503 |

- 存在しないタスクは 404、不正なデータは 422 等の適切なエラーにする。
- API が返す日時は UTC（ISO 8601）。
- API ドキュメントは FastAPI の OpenAPI を利用する。
- **重要:** Liveness に DB の接続性を含めない（DB 障害で無意味な API 再起動が連鎖する設計を避ける）。
- API のベースパス `/api/v1` を保ち、Compose / kind / EKS で画面からの呼び出し先を変えない。

### 2.3 採用技術と理由

| Layer | 初期技術 | 採用理由 |
| --- | --- | --- |
| Frontend | Vite + Vanilla TypeScript（静的ページ） | React 固有の学習コストを避け、画面は最小限 |
| Web server / reverse proxy | Nginx（静的ファイル配信、`/api/` 転送） | 入口を一本化し、Service 名解決と L7 転送を実習できる |
| Backend | Python + FastAPI | 少ないコードで CRUD、Health、負荷試験を作れる |
| ORM / migrations | SQLAlchemy + Alembic | DB スキーマ管理と初期化の責務を学べる |
| DB | PostgreSQL | 永続化、StatefulSet、PVC と RDS の対比に使える |
| Container | Docker / Docker Compose | Kubernetes と比較する出発点 |
| Local Kubernetes | kind + kubectl | クラスターをローカルに再作成できる |
| マニフェスト管理 | Kustomize（`kubectl -k`） | 早期に Helm の追加学習を要求せず環境差分を管理できる |
| パッケージ利用 | Helm（Phase 7 から） | 公式 chart で配布される周辺コンポーネントを導入する。自作 chart は Phase 8 の比較後に判断 |
| GitOps | Argo CD（Phase 8、まず kind 上） | Git を正とした同期と、CI からの直接 apply の違いを費用をかけずに比較できる |
| 補助 CLI | k9s（Phase 5、任意） | `kubectl` での調査手順を習得した後の、観察の効率化に限定して使う |
| AWS IaC | Terraform | VPC・EKS・周辺サービスの構造を明示的に学べる |
| CI / CD | GitHub Actions（後半） | テスト・イメージ作成・デプロイの責務を分離できる |

**依存ライブラリ、イメージ、Kubernetes バージョンの具体値は各ラボ開始時に互換性を確認して固定する。** この設計書の発行時点のバージョンを無条件に固定しない。

### 2.4 機能の段階的拡張（必要になってから実装）

- Phase 4: `/metrics` にアプリ指標を追加し、応答時間・エラー率の可視化に利用。
- Phase 5: 安全なダミー負荷生成スクリプトと障害注入シナリオを追加。
- Phase 7: **任意の発展課題**として CSV エクスポートを S3 に保存し、EKS Pod Identity を学ぶ。必要に応じて Redis + Worker を追加し、非同期処理を学ぶ。**MVP に Worker は不要**。
- Phase 8: 配信方式の変更（CI/CD、GitOps）、監視、バックアップ方針を評価。

---

## 3. 段階別アーキテクチャ

### 3.1 Phase 1: Docker Compose

```text
Browser (localhost:8080)
   |
   v
web [Nginx + static files]
   |  /api/* reverse proxy
   v
api [FastAPI:8000]
   |
   v
db [PostgreSQL:5432] -- named volume (local persistence)
```

- 公開するのは Web コンテナの `localhost:8080` のみ。
- DB ポートはホストに公開しない。開発時に必要なら明示的にポート公開するラボを別途設ける。
- Web、API、DB はそれぞれ別コンテナ。
- DB 認証情報は開発専用の `.env`（Git 管理対象外）から読み込む。`.env.example` には非機密の例のみ記載する。

### 3.2 Phase 2–5: ローカル Kubernetes（kind）

```text
Browser
   |
   v
kubectl port-forward svc/workboard-web 8080:80
   |
   v
Service: workboard-web (ClusterIP)
   |
   v
Deployment: web (Nginx)
   |  /api/* --> http://workboard-api:8000
   v
Service: workboard-api (ClusterIP)
   |
   v
Deployment: api (FastAPI) [1 -> 2/3 replicas]
   |
   v
Service: workboard-postgres (ClusterIP)
   |
   v
PostgreSQL [Phase 2: disposable / Phase 3: StatefulSet + PVC]
```

- 最初は `kubectl port-forward` を入口とし、Ingress / Gateway Controller を学習の前提条件にしない。
- Phase 2 はデータを捨ててもよい教材として PostgreSQL を簡易起動し、再作成による消失を観察する。
- Phase 3 で StatefulSet + PVC に置き換え、Pod 再作成時のデータ保持を確認する。PV は**ノード喪失を含めた可用性の保証ではない**ことも学ぶ。
- kind の StorageClass は事前に `kubectl get storageclass` で確認し、使用可能な StorageClass がない場合は適切なプロビジョナーを追加してから進める。
- CNI の対応状況を確認せずに NetworkPolicy の通信遮断効果を主張しない。対応 CNI の導入と検証を独立した課題にする。

### 3.3 Phase 6–8: AWS / EKS

```text
Browser (検証時のみ、アクセス制限を設定)
   |
   v
AWS ALB (AWS Load Balancer Controller が管理)
   |
   v
EKS: Service web -> Deployment web (Nginx)
                             |
                             v
                     Service api -> Deployment api
                                         |
                                         v
                                 Amazon RDS PostgreSQL

ECR: コンテナイメージ保管
VPC: Public subnets (ALB) / Private subnets (nodes, RDS)
IAM: EKS cluster/node roles, access entries, 必要に応じ Pod Identity
Terraform: VPC / EKS / ノード / 周辺サービス
```

- 最初の EKS は**標準 EKS + Managed Node Groups**を教材に採用。ノード／アドオン／ロードバランサーの責任分界を観察できるようにする。
- EKS Auto Mode は後半の**比較課題**とする。標準 EKS と Auto Mode で管理主体・可観測性・追加費用が変わる点を比較する。
- 初回構成は単一の学習専用環境。Public/Private subnet を複数 AZ に配置する案を基本とするが、NAT Gateway、VPC endpoints、ALB、EC2 等の料金を事前に見積もり、コスト削減案と可用性上のトレードオフを記録する。
- Web と API は Stateless。DB は原則 RDS に移し、Kubernetes 外部でデータを管理する理由を説明する。
- ALB 用の Ingress は AWS Load Balancer Controller で管理する。古い**community ingress-nginx**への依存を作らない。
- 必要であれば将来 Gateway API を扱う独立ラボを用意し、導入する Controller の互換性を確認する。

---

## 4. リポジトリ構成（最終形。Phase 0 で全ファイルを実装する必要はない）

```text
kubernetes-eks-learning/
├── README.md                       # 全体概要、現在の進捗、学習開始手順
├── AGENTS.md                       # Codex 向け作業ルール（本設計書から抽出）
├── .gitignore
├── .editorconfig
├── .env.example
├── docs/
│   ├── PROJECT_DESIGN.md           # 本書（リポジトリへコピー）
│   ├── architecture/
│   │   ├── 01-compose.md
│   │   ├── 02-kind.md
│   │   └── 03-eks.md
│   ├── adr/
│   │   ├── README.md
│   │   └── 0001-application-and-learning-stack.md
│   ├── operations/
│   │   ├── troubleshooting.md
│   │   └── aws-cleanup.md
│   └── comparisons/
│       └── ecs-vs-eks.md
├── app/
│   ├── web/
│   │   ├── src/
│   │   ├── Dockerfile
│   │   └── nginx.conf
│   └── api/
│       ├── src/
│       ├── migrations/
│       ├── tests/
│       ├── Dockerfile
│       └── pyproject.toml
├── docker/
│   └── compose.yaml
├── kubernetes/
│   ├── base/                        # web/api の共通 Deployment + Service
│   │   └── kustomization.yaml
│   ├── components/
│   │   └── postgres-local/          # ローカル用 DB リソース
│   └── overlays/
│       ├── kind/
│       │   └── kustomization.yaml
│       └── eks/
│           └── kustomization.yaml
├── terraform/
│   ├── modules/                     # 必要になった時点で追加
│   └── environments/
│       └── lab/
│           ├── main.tf
│           ├── variables.tf
│           ├── outputs.tf
│           └── terraform.tfvars.example
├── scripts/
│   ├── preflight.ps1                # Windows PowerShell / WSL2 の利用を考慮
│   ├── preflight.sh
│   └── ...
├── labs/
│   ├── 00-repository-foundation/
│   ├── 01-compose-basics/
│   ├── 02-kubernetes-basics/
│   ├── 03-configuration-storage/
│   ├── 04-reliability-scaling/
│   ├── 05-security-and-failure/
│   ├── 06-eks-foundation/
│   ├── 07-aws-integration/
│   ├── 08-devops-observability/
│   └── 09-architecture-review/
└── .github/
    └── workflows/                   # CI ラボで追加
```

### 4.1 ファイルを増やす順序

- **Phase 0:** README、AGENTS、Git 設定、設計書、`labs/00...`、ADR だけ。
- **Phase 1:** `app/`、Compose、テスト、`.env.example` を追加。
- **Phase 2–5:** `kubernetes/`、kind 用スクリプト、検証記録を追加。
- **Phase 6–7:** `terraform/`、AWS 構成図、コスト・削除手順を追加。
- **Phase 8–9:** CI/CD、監視、比較レポートを追加。

**注意:** 上のツリーは完成後の目標構成。Phase 0 時点では空フォルダや大量の TODO だけのファイルを無理に作らない。

---

## 5. 各ラボの共通テンプレート

各 `labs/NN-.../README.md` に最低限次を記述する。

```markdown
# Lab NN: [タイトル]

## 学習目標
- 最終的に何を説明・判断できるようになるか

## 前提条件
- 必要なツール、前のラボの成果物、想定コスト

## 設計課題（実装前に考える）
1. なぜこの方式を選ぶのか？
2. 別の選択肢は何か？
3. 障害・運用負荷・コストの観点で何が変わるか？

## 実装タスク
- 小さく独立した順序で記載

## 検証コマンド・期待結果
- コマンド例
- 期待される状態
- 失敗したときに調べるポイント

## 故障実験（該当するラボのみ）
- 故障の注入方法と復旧・観察方法

## 完了条件
- [ ] 実行可能なテスト
- [ ] 理由の説明
- [ ] 結果の記録

## 学習メモ
- 実際の観察、疑問、未解決事項、参照した公式資料
```

### 5.1 評価方法

各ラボは次の 4 軸で確認する。

1. **作れる** — 定義を適用し、期待通りに稼働させられる。
2. **観察できる** — ログ、イベント、状態、メトリクスで実際の動作を確認できる。
3. **説明できる** — なぜその構成なのか、代替案との違いを説明できる。
4. **壊して復旧できる** — 想定障害の現象、復旧条件、残存リスクを説明できる。

「`kubectl apply` が成功した」は十分な完了条件ではない。

---

## 6. フェーズ別バックログ

### Phase 0 — リポジトリ基盤（Codex の初回タスク）

**目的:** 学習教材として継続しやすい器を作る。

- `README.md`、`AGENTS.md`、`.gitignore`、`.editorconfig` を作成。
- 本設計書を `docs/PROJECT_DESIGN.md` に配置。
- `labs/00-repository-foundation/README.md` をテンプレートに従って作成。
- `docs/adr/0001-application-and-learning-stack.md` に技術選定理由を記録。
- `scripts/preflight.ps1` と `scripts/preflight.sh` を実装し、Git、Docker、Docker Compose、kubectl、kind、Python、Node.js、AWS CLI、Terraform の導入有無・バージョンを**参照のみで**表示する。未導入ツールがあっても Phase 0 は完了可能とする。
- 利用 OS が Windows の場合は PowerShell と WSL2/Docker Desktop の実行経路を README に示す。環境未確認のコマンドは「要確認」とする。

**Done:** リポジトリを clone して目的・学習順序が理解でき、preflight の結果が読める。アプリや AWS はまだ作らない。

### Phase 1 — Docker Compose とアプリ MVP

**学ぶこと:** コンテナ、イメージ、Dockerfile、ネットワーク、DNS、ポート公開、volume、起動依存関係。

**実装:** WorkBoard CRUD / web / API / PostgreSQL、Compose、DB migration、基本ユニット・API テスト。

**検証:**

- `docker compose -f docker/compose.yaml up --build -d` で起動できる（パスはリポジトリ直下からの実行を想定）。
- `http://localhost:8080` にアクセスし、タスク作成・一覧・更新・削除ができる。
- ブラウザ再読み込み、API コンテナ再起動後にデータが残る。
- DB の volume を**意図的に**消すとデータが消えることを別実験で確認する（削除前の明示確認が必要）。
- API テストが成功し、Web 以外のポートは原則ホスト公開されていない。

**設計の問い:** `depends_on` だけで DB の readiness は保証されるか？ API が DB 接続に失敗したとき、どこで再試行すべきか？

**Done:** Compose で再現可能な MVP とテスト、基本構成図、観察記録。

### Phase 2 — Kubernetes 最小構成

**学ぶこと:** Control Plane / Node、Pod、ReplicaSet、Deployment、Service、label/selector、DNS、宣言的管理。

**実装:** kind クラスター、Web/API Deployment、ClusterIP Service、学習用の一時的 PostgreSQL、kind へのローカルイメージ投入、Web の port-forward。

**検証:**

- `kind create cluster --name workboard-lab` 等で作成、`kubectl get nodes` で確認。
- 使用イメージを `kind load docker-image ... --name workboard-lab` で投入し、タグと `imagePullPolicy` の関係を確認。
- `kubectl get pods,deploy,svc -n workboard` で起動を確認。
- `kubectl port-forward -n workboard svc/workboard-web 8080:80` からブラウザ操作できる。
- API Pod を削除し、Deployment が再作成することを観察。

**設計の問い:** Pod と Deployment の違いは何か？ Service が必要な理由は？ なぜ Pod IP を直接参照しないのか？

**Done:** クラスターを作り直して手順を再実行できる。Compose と Kubernetes の責任範囲を比較した文章がある。

### Phase 3 — 設定、機密情報、永続化

**学ぶこと:** Namespace、ConfigMap、Secret、StatefulSet、PVC/PV、StorageClass、Kustomize、migration。

**実装:** 共通 `base` と `kind` overlay、DB の StatefulSet + PVC、アプリ設定の分離、Secret の扱い、DB migration を再実行可能な方式にする。

**検証:**

- `kubectl kustomize kubernetes/overlays/kind` の結果を確認できる。
- DB Pod の再作成後もデータが残ることを確認。
- `kubectl get pvc,pv -n workboard` でバインドを確認。
- ローカルのダミー秘密情報だけを使い、実パスワードはリポジトリに含まれない。
- 秘密情報を Secret に置いただけでは暗号化・アクセス制御が完全になるわけではないと説明できる。

**設計の問い:** PostgreSQL をなぜ StatefulSet にするのか？ PVC は何を守り、何を守らないのか？ Kustomize の overlay は何を変え、何を生成しないのか（テンプレートエンジンとの違い）？

**Done:** 永続化の実験結果と、StatefulSet 対 RDS の初期比較 ADR を作る。

### Phase 4 — 可用性、更新、スケーリング

**学ぶこと:** Liveness / Readiness / Startup probes、resource requests/limits、Rolling Update、HPA、PDB、Pod 配置制御。

**実装:**

- API に Probe を設定。Liveness は DB 非依存、Readiness は DB 接続依存。
- CPU / memory requests・limits を設定し、その根拠を記録。
- API の replicas を増やし、Rolling Update と rollback を試す。
- HPA を追加。metrics-server は公式の対応・インストール要件を確認し、ローカルの実験に必要な設定を記録。
- 複数ノードで PDB と topology spread を観察する（kind クラスター構成を調整）。

**故障実験:** API Pod 削除、DB 一時停止、Readiness 異常、CPU 負荷。必要に応じ `kubectl rollout undo`。

**設計の問い:** レプリカが 3 つでもノードが 1 つなら何が単一障害点か？ HPA は Node の台数まで増やすのか？

**Done:** 障害前後の Pod 数、HTTP 応答、イベント、復旧時間の観測結果が記録される。

### Phase 5 — セキュリティ、障害調査、運用

**学ぶこと:** ServiceAccount、RBAC、NetworkPolicy、Pod Security Standards、非 root 実行、イメージ管理、診断フロー。任意で補助 CLI の k9s。

**実装:**

- アプリ実行ユーザーの権限を最小化。
- 必要な ServiceAccount / Role / RoleBinding を説明・実装。
- NetworkPolicy をサポートする CNI を導入したうえで通信許可・拒否をテスト（kind 標準ネットワークのまま動作すると決めつけない）。
- 意図的な誤設定を `kubectl describe`、logs、events などで調査するトラブルシュート集。
- 任意: Runbook を `kubectl` で完成させた後に、同じ障害を k9s で観察し、各画面がどの `kubectl` 操作・API 呼び出しに当たるかを対応づける。k9s は専用 kubeconfig の kind クラスターだけで使い、編集・削除の操作は Runbook の手順に含めない。

**故障実験:** 存在しない image tag、誤った Service selector、DB の DNS 名ミス、権限不足、Resource limit による再起動。

**設計の問い:** K8s Secret のセキュリティ境界は？ 誰が Kubernetes API を操作できるべきか？ k9s のような TUI を使っても、操作できる範囲は何で決まるのか（RBAC との関係）？

**Done:** 意図的に作った障害を再現・発見・復旧する Runbook を完成。

### Phase 6 — Amazon EKS 基盤構築（AWS の有料リソースを利用）

**開始条件:** ユーザーによる AWS 利用明示承認、見積金額確認、通知予算設定、クリーンアップ手順のレビュー。

**学ぶこと:** AWS と Kubernetes の責任分界、VPC、subnet、route/NAT、EKS、Managed Node Groups、IAM、ECR、Terraform。

**実装:**

- Terraform で学習用 VPC と EKS、Managed Node Groups を定義（実際の create は承認後）。
- 使う region、Kubernetes / node AMI、サブネット配置、EKS endpoint のアクセス制限を決定・ADR 化。
- ローカルビルドしたイメージを ECR に配置する CI/手動手順を作る。
- Kustomize の `eks` overlay を作り、まず API / Web のコンテナ実行を検証。
- `terraform plan` の差分、料金要因、削除後に残り得る資産を記録する。

**設計の問い:** EKS でも OS/Node の運用責任は残るか？ マネージド Node Group と Auto Mode の管理境界の差は？

**Done:** 最低限のクラウド構成を安全に再構築・破棄できる（実行が許可された場合）。

### Phase 7 — EKS と AWS マネージドサービス連携

**学ぶこと:** ALB / Ingress、AWS Load Balancer Controller、RDS、Pod Identity、IAM least privilege、ネットワーク設計、Helm（chart の利用者として）。

**実装:**

- RDS PostgreSQL に切り替え、コンテナ内 DB と責任分界を比較。
- AWS Load Balancer Controller で ALB を管理し、外部公開の範囲を制限して疎通確認。
- Controller は公式手順に従い Helm chart で導入する。導入前に chart のバージョンと values を固定・記録し、`helm template` で生成されるマニフェスト（ServiceAccount、RBAC、Deployment、Webhook 等）を読んでから適用する。`helm list` / `helm history` で release の状態と rollback の単位を確認する。
- ローカルのタスクデータ移行・バックアップ・リストアの設計を記録。
- 発展課題: CSV エクスポートを S3 に保存し、Pod Identity による限定的なアクセス権限を検証。
- 発展課題: Redis + Worker を追加し、Job、Deployment、非同期処理の適用先を比較する。

**設計の問い:** なぜ PostgreSQL を RDS に置くのか？ RDS の障害が API の Readiness にどう影響するか？ 第三者の Helm chart を導入するとき、何を確認すれば中身を把握したと言えるか？

**Done:** AWS API 権限、L7 ルーティング、データ永続化の設計判断とアクセス試験が残る。

### Phase 8 — DevOps、可観測性、運用改善

**学ぶこと:** GitHub Actions、CI/CD、デプロイ戦略、GitOps、ログ・メトリクス・トレース、SLO、コスト最適化。

**実装:**

- CI で lint、unit/API test、Docker image build、Kustomize の構文確認。
- CD は最初は手動承認制。GitOps（Argo CD 等）は方式比較後に追加。
- Argo CD は、まず kind 上で WorkBoard の Kustomize overlay を同期対象にして試す（AWS 費用なし）。手動の `kubectl` 変更による drift の検出、同期、Git の revert による戻しを観察する。EKS への導入は、Phase 6 以降の利用承認の範囲内で別途判断する。
- 自アプリのマニフェストを Helm chart 化するかは、既存の Kustomize 構成と同じ基準（差分の見通し、レビューのしやすさ、配布の必要性）で比較し、ADR に記録してから決める。
- アプリメトリクスを計測し、レイテンシ、HTTP エラー率、Pod 再起動、リソース使用量を観察。
- SLI/SLO を小規模な学習用指標として定義する（例: 正常リクエスト率、p95 応答時間）。測定前に達成済みと断言しない。
- Cost Explorer 等で AWS コストを確認し、不要時に環境を削除する仕組みを検討。

**設計の問い:** GitOps と CI からの直接 `kubectl apply` の違いは？ 管理対象が増えたらどちらが有利か？ Helm と Kustomize は、それぞれどんな変更・配布に向くか？ 両方を同じアプリに使うと何が複雑になるか？

**Done:** 変更から検証、デプロイ、観察、復旧までの手順を説明できる。

### Phase 9 — 最終設計レビュー: ECS vs EKS

**課題シナリオ（仮定。ユーザー要件ではない）**

> 月間数十万リクエスト規模の社内タスク管理サービスを AWS で運用する。少人数の運用チームが担当し、可用性・変更容易性・コスト・学習負担をバランスさせる。将来は別チームの複数サービスが追加される可能性がある。

**比較軸**

| 軸 | 比較時に答える問い |
| --- | --- |
| 初期構築 | どちらが要件実現までの構成要素が少ないか |
| 運用責任 | ノード、パッチ、ネットワーク、アドオンの管理責務はどちらにあるか |
| スケール | Pod/Task と Node/Capacity の独立性、負荷への追従はどう違うか |
| 可用性 | ノード / AZ / DB 障害にどの設計で対応するか |
| セキュリティ | IAM、ネットワーク、コンテナ権限、監査で何が必要か |
| コスト | 常時費用、変動費、運用人件費、移行費用の差は何か |
| 開発体験 | GitOps、共通基盤、エコシステム、組織の学習負荷はどう違うか |
| 長期戦略 | 既存技術、移植性、マルチクラスタ要件が判断に影響するか |

**成果物:** `docs/comparisons/ecs-vs-eks.md` に想定要件、採用判断、反対案、定量・定性根拠、不確実性を記録。**EKS 採用を正解として扱わない。**

---

## 7. 設計上の重要な意思決定（ADR の種）

| ID | 決定 | 理由・トレードオフ |
| --- | --- | --- |
| ADR-0001 | WorkBoard + FastAPI + TS/Vite + PostgreSQL | 業務ロジックを薄くしインフラ学習へ集中。技術的多様性は限定 |
| ADR-0002 | kind 先行、EKS は後半 | 低コスト・高速再現。クラウド特有の制約は後半で学ぶ |
| ADR-0003 | 初期の Web 入口は port-forward | ネットワーク構成要素を段階導入できるが公開検証は別途必要 |
| ADR-0004 | `base` + `overlays` を Kustomize で管理 | 設定差分を明示。Helm は後半で比較 |
| ADR-0005 | EKS で RDS を使う | DB の運用責任を分離。費用と AWS 依存が増える |
| ADR-0006 | 標準 EKS / Managed Node Groups を最初に使用 | 学習対象が明示される。Auto Mode より初期構成が複雑 |
| ADR-0007 | 学習段階では AWS を自動プロビジョニングしない | 意図しない課金・公開・データ削除を防止 |
| [docs/adr/0005](adr/0005-kubernetes-ecosystem-tools.md) | エコシステムのツールを段階導入（Kustomize→k9s→Helm→Argo CD） | 仕組みを理解してから道具を使う。導入の時期が後になり、ツールの比較はフェーズの後半に寄る |

この表の ID は設計時の「種」であり、`docs/adr/` の実ファイル番号とは一致しない。実際の ADR はファイル名で参照する。

ADR テンプレートには `Status / Context / Decision / Alternatives / Consequences / Evidence` を含める。

---

## 8. 初回に実施する環境確認

Phase 0 のスクリプトで以下をチェックする。**この文書内の記載は、現在のローカル環境に導入済みであることを意味しない。**

| ツール | Phase 0 | Phase 1 | Phase 2–5 | Phase 6–8 |
| --- | --- | --- | --- | --- |
| Git | 必須 | 必須 | 必須 | 必須 |
| Docker / Compose | 任意で確認 | 必須 | 必須 | 必須（ローカルビルド時） |
| Python / Node.js | 任意で確認 | 必須 | 必須 | 必須 |
| kubectl / kind | 任意で確認 | 不要 | 必須 | kubectl は必須 |
| AWS CLI / Terraform | 任意で確認 | 不要 | 不要 | 必須 |

**実行環境の方針**

- Windows は PowerShell と Docker Desktop + WSL2 を想定候補とする（実環境を確認してから手順確定）。
- 代替として Linux / macOS でも再現可能な設計を目指す。
- README には OS ごとの操作の差を記載する。
- 1つのパスやシェルだけで動く設計にしない。

---

## 9. セキュリティ・コスト・削除のガードレール

### 9.1 Git と Secret

- `.env`、`.env.*.local`、`*.tfstate*`、`.terraform/`、`terraform.tfvars`、認証 JSON、秘密鍵を除外。
- `example` ファイルにはダミー値のみを含める。
- Kubernetes Secret の YAML に実際の認証情報を直接コミットしない。
- 将来は AWS Secrets Manager 等の使用も比較するが、MVP に導入しない。

### 9.2 AWS コスト

- EKS クラスター料金だけでなく、EC2、ALB、RDS、NAT Gateway、ECR、EBS、データ転送等の費用を確認する。
- 実行前に料金表の最新情報を AWS 公式ページで確認する。見積りには region・利用時間・台数・AZ 構成を明記する。
- AWS Budgets 等の通知を設定する。ただし**予算通知は課金停止を保証しない**。
- 学習完了後は削除対象を一覧化する。特に EKS により作られた ALB、関連 ENI、RDS、EBS、NAT Gateway、ECR、ログ、Terraform state 管理先を点検する。
- `terraform destroy` の前に、DB データ・バックアップの喪失リスクを明示する。

### 9.3 現行エコシステムへの配慮

- **community ingress-nginx は 2026-03-24 に引退済み。** 本プロジェクトの新規ローカル公開基盤として採用しない。
- 「Ingress API」「AWS Load Balancer Controller」「community ingress-nginx」は異なるものとして明確に区別する。
- Gateway API を利用する場合も、それを実際に処理する Gateway Controller が必要。API リソースを作るだけでは通信できない。

---

## 10. Codex に渡すプロンプト（そのまま使用可能）

### 10.1 初回: Phase 0 のみを実施

以下を Codex のチャットに貼り付ける。**事前にこのファイルを新規リポジトリの `docs/PROJECT_DESIGN.md` として置くこと。**

```text
このリポジトリは Kubernetes / Amazon EKS を体系的に学ぶための
ハンズオン教材です。

まず docs/PROJECT_DESIGN.md を全文読み、内容を唯一の一次設計書として
扱ってください。現時点では Phase 0（リポジトリ基盤）だけ実装します。

要求事項:
1. README.md と AGENTS.md を作成してください。
2. .gitignore と .editorconfig を整備してください。
3. labs/00-repository-foundation/README.md を作成してください。
4. docs/adr/0001-application-and-learning-stack.md を作成してください。
5. 環境を確認する scripts/preflight.ps1 と preflight.sh を作成してください。
6. 実行可能な範囲でスクリプトの検証を行ってください。
7. 変更内容、検証結果、未検証事項、次にユーザーが実施するコマンドを報告してください。

制約:
- Phase 1 以降のアプリやマニフェストを先回りで実装しない。
- AWS の有料リソースを作らない。terraform apply は実行しない。
- インストール済みでないツールを「導入済み」と書かない。
- 初心者がコマンドの意味を理解できる学習ドキュメントにする。
- 要件が複数の解釈を持つ場合は安全で単純な案を採り、理由を記録する。

まず短い作業計画を提示し、その後に実装してください。
```

### 10.2 Phase 1 に進むときのプロンプト

```text
Phase 0 の成果物と docs/PROJECT_DESIGN.md を読み、
Phase 1（Docker Compose と WorkBoard MVP）のみ実装してください。

最初に今回学ぶ概念と構成図、設計判断（なぜこの実装か）を説明してください。
次に app/web、app/api、docker/compose.yaml、テスト、
labs/01-compose-basics/README.md を実装してください。

CRUD とヘルスチェックは設計書の API 仕様に従ってください。
Docker が利用可能なら起動・API テストを実施し、結果を提示してください。
利用不可なら検証できなかった理由と再現コマンドを記載してください。
Phase 2 以降の Kubernetes マニフェストや AWS リソースは作りません。
最後に「実装したこと」「ユーザーが自分で試す課題」「未解決事項」をまとめてください。
```

### 10.3 以降の進め方

各フェーズの開始時に以下のテンプレートを使う。

```text
docs/PROJECT_DESIGN.md と既存の ADR、現在のリポジトリを確認し、
Phase N のみを実装してください。実装前に以下を示してください。

- 学習目標とアーキテクチャ差分
- 実装作業の小さな段階分け
- 検証手順と期待結果
- 重要なトレードオフ

実装後は tests / 検証コマンド / 観察記録 / 設計判断を残してください。
既存のフェーズの成果物を壊さず、次のフェーズを先回りしないでください。
AWS の作成・破棄が必要なら実行前に対象、見積り、影響を示し、
明示承認を得てください。
```

---

## 11. リリース／レビューの運用

- 小さなコミット単位を推奨: `docs:`, `feat:`, `test:`, `infra:`, `lab:`, `fix:` など。
- 各フェーズに「課題 → 実装 → 観察 → ADR → チェックリスト」を残す。
- main に動かない半完成物を無理に統合しない（作業ブランチ推奨）。
- アプリとインフラのどちらを変更したかを PR / コミットで区別する。
- README に現在の到達フェーズ、直近の実行手順、後片付け手順を更新する。

---

## 12. 最初に決めておく成果物の優先度

| 優先度 | 成果物 | 理由 |
| --- | --- | --- |
| P0 | 再現可能な Compose / kind 環境 | ハンズオンの最低条件 |
| P0 | ラボごとの検証コマンドと期待結果 | 「動いた」だけで終わらせない |
| P0 | 設計判断・トレードオフの ADR | 技術選定力の育成 |
| P0 | AWS 作成前の安全チェック | 意図しない課金・公開防止 |
| P1 | 自動テストと CI | 継続的な変更の安全性 |
| P1 | 障害注入と診断シナリオ | 運用判断力の育成 |
| P1 | EKS と ECS 比較レポート | 最終的な技術選定力 |
| P2 | Redis + Worker / S3 拡張 | 非同期・AWS 権限の応用学習 |
| P2 | GitOps / 高度な監視 | 運用成熟度の拡張 |

---

## 13. 根拠となる公式資料（実装時に更新確認）

以下は設計方針を検証するための一次情報。URL は 2026-11-08 時点に確認したもの。コマンド・バージョン・料金は実行時に再確認すること。

1. [Kubernetes Concepts](https://kubernetes.io/docs/concepts/) — Kubernetes のリソース概念全般。
2. [Kubernetes Workloads](https://kubernetes.io/docs/concepts/workloads/) — Deployment / StatefulSet の適用範囲。
3. [kind Quick Start](https://kind.sigs.k8s.io/docs/user/quick-start/) — kind の作成とローカルイメージ利用。
4. [Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/) — Probe の意味と挙動。
5. [Horizontal Pod Autoscaling](https://kubernetes.io/docs/concepts/workloads/autoscaling/horizontal-pod-autoscale/) — HPA の責務。
6. [Declarative Management Using Kustomize](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/) — base / overlay と `kubectl -k`。
7. [Kubernetes: Ingress NGINX Retirement](https://kubernetes.io/blog/2025/11/11/ingress-nginx-retirement/) — community ingress-nginx の引退。
8. [Kubernetes Gateway API](https://kubernetes.io/docs/concepts/services-networking/gateway/) — Gateway / HTTPRoute の概念。
9. [Amazon EKS: Managed Node Groups](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html) — 標準 EKS ノード管理。
10. [Amazon EKS: ALB Ingress](https://docs.aws.amazon.com/eks/latest/userguide/alb-ingress.html) — ALB / AWS Load Balancer Controller。
11. [Amazon EKS: AWS Load Balancer Controller Installation](https://docs.aws.amazon.com/eks/latest/userguide/lbc-helm.html) — Controller の導入前提。
12. [Amazon EKS: Pod Identities](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html) — ServiceAccount と IAM ロールの関連づけ。
13. [Amazon EKS: Auto Mode Best Practices](https://docs.aws.amazon.com/eks/latest/best-practices/automode.html) — 管理境界の比較。
14. [Amazon EKS: Cluster API endpoint access](https://docs.aws.amazon.com/eks/latest/userguide/cluster-endpoint.html) — API endpoint の公開・非公開制御。
15. [Amazon EKS Pricing](https://aws.amazon.com/eks/pricing/) — EKS 利用料金（都度確認）。
16. [AWS Pricing Calculator](https://calculator.aws/) — クラウド費用の事前見積り。
17. [Helm Docs](https://helm.sh/docs/) — chart・release・`helm template` の概念（Phase 7 で版を確認）。
18. [Argo CD Documentation](https://argo-cd.readthedocs.io/en/stable/) — Application、同期、drift の扱い（Phase 8 で版を確認）。
19. [k9s](https://k9scli.io/) — 補助 CLI の機能と導入方法（Phase 5 で版を確認）。

---

## 14. この設計書の確定事項と後で決める事項

### 確定（基本方針）

- 単一の `WorkBoard` アプリを段階的に発展させる。
- ローカルで Kubernetes の概念を理解してから EKS を導入する。
- 各ラボに検証と設計判断を必須とする。
- アプリはシンプルな 3 層構成から開始し、複雑なコンポーネントは目的が生じた際に追加する。
- Codex は指示されたフェーズだけ実装し、AWS の変更は事前承認を要求する。

### 実装時に決定する（現段階では断定しない）

- ローカルの OS / シェル、Docker の動作方式、ツール導入状況。
- 使用する Python / Node.js / PostgreSQL / Kubernetes / EKS の具体的なサポートバージョン。
- ローカル PVC 用 StorageClass と NetworkPolicy 対応 CNI。
- AWS region、node instance type、NAT / VPC endpoint 設計、月額予算上限。
- EKS の公開方式とアクセス制限条件、CI の認証・配信方法。

**次にやること:** 空の `kubernetes-eks-learning` リポジトリを用意し、本書を `docs/PROJECT_DESIGN.md` に配置。セクション **10.1 のプロンプト**を Codex に渡して Phase 0 から開始する。
