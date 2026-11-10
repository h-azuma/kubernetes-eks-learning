# ADR-0011: EKS 基盤（標準 EKS + Managed Node Group、region、endpoint、NAT、Terraform の書き方）

> **読む順番:** この ADR には Lab 06 の設計課題の答えにあたる内容が含まれます。先に [Phase 6 のラボ](../README.md) の設計課題に自分で答えてから読み、自分の考えと比べてください。

## Status

提案（2026-11-10）。Phase 6 に適用。学習者が Lab 06 の設計課題に回答し、内容を確認したうえで「採用」に変更する。値（バージョン・料金）は 2026-11-10 時点の公式資料の確認結果で、実行前に再確認する。

## Context

Phase 3 までは kind 上で Kubernetes の概念を学んだ。Phase 6 では AWS 上に EKS を作り、「AWS が管理するもの」と「利用者が管理するもの」の境界を観察する。AWS の有料リソースを作るため、費用・公開範囲・後片付けのしやすさを設計の主な制約にする。設計書 §3.3 は、標準 EKS + Managed Node Group を最初の教材とし、EKS Auto Mode は後半の比較課題とする。この Phase の作成・変更・削除は、ユーザーの明示承認を得た後にだけ実行する（`terraform apply` は未実施）。

## Decision

### 1. 標準 EKS + Managed Node Group（Auto Mode ではない）

コントロールプレーンは EKS、ワーカーノードは Managed Node Group（EC2、On-Demand）。ノードの作成・登録、更新時のドレインは EKS が行うが、OS イメージ（AMI）を新しい版へ切り替える作業、アドオンの更新、ノードのサイズ決定は利用者の責任として残る。Auto Mode はノードとアドオン（ネットワーク、ロードバランサー等）まで AWS が管理するため、この責任分界を観察する教材にならない。比較は設計課題と後半の課題で扱う。

### 2. バージョンと構成値

| 項目 | 値 | 根拠 |
| --- | --- | --- |
| Terraform | `~> 1.17.0`（検証は 1.17.1） | releases.hashicorp.com の最新安定版（2026-10-28 公開） |
| AWS provider | `~> 6.72`（lock は 6.72.0） | Terraform Registry の最新版（2026-11-04 公開） |
| Kubernetes | 1.35 | EKS の標準サポート中の版（1.34〜1.37）のうち、教材の kind（1.35.8）と kubectl 1.34〜1.36 に合わせた。標準サポート終了は 2027-03-27 |
| ノード AMI | `AL2023_x86_64_STANDARD` | Amazon Linux 2023 の EKS 最適化 AMI（x86_64）。Terraform の `validate` で値の妥当性を確認 |
| インスタンス | `t3.medium` × 2（最小 1、最大 3） | 2 vCPU / 4 GiB。WorkBoard の Pod 数（Web、API、DB、Job）に十分で、Windows でビルドする x86_64 イメージをそのまま動かせる。料金は cost-estimate.md |
| region | `ap-northeast-1`（変数） | 日本から近く、AZ が 3 つ以上ある。料金は region で異なるため、見積もりに region を明記する |

Kubernetes 1.37 が最新だが、kubectl 1.34〜1.36 の教材範囲と kind の版に合わせて 1.35 とした。標準サポートが短くなる代わりに、ローカルと同じ版で学べる。延長サポート（クラスター時間あたり $0.60、標準は $0.10）へ自動で入らないよう `upgrade_policy.support_type = STANDARD` を指定した。

### 3. API endpoint は public + private、public は CIDR で制限する

`public_access_cidrs` は必須の変数で、空と `0.0.0.0/0` を validation で拒否する。private endpoint も有効にするので、ノードから API への通信は VPC 内で完結し、NAT の IP を許可 CIDR に含める必要がない。public endpoint の既定は全世界へ公開で、IAM と RBAC が守るが、攻撃面を減らすため自分の IP の /32 に限定する。IP が変わると自分も接続できなくなる（`terraform apply` で CIDR を更新する）。

### 4. VPC は 2 AZ、NAT Gateway は単一を既定にする

public subnet（ALB 用）と private subnet（ノード用）を 2 AZ に置く。NAT Gateway は 1 つ（`single_nat_gateway = true`）にして、時間料金とデータ処理料金のうち固定部分を半分にする。トレードオフは、NAT のある AZ の障害で、もう一方の AZ のノードも外向き通信（ECR からのイメージ取得、AWS API）ができなくなること。学習用なので可用性よりコストを優先する。`false` にすると AZ ごとの NAT になる。VPC endpoint（ECR、S3）で NAT を減らす案もあるが、interface endpoint は時間料金がかかり、構成要素が増えるため採用しない。ノード自体は 2 AZ に分散する。

### 5. Terraform は community module を使わず、AWS provider のリソースで明示的に書く

`terraform-aws-modules/vpc` や `eks` を使えば行数は大幅に減る。しかし、この Phase の目的は VPC のルーティング、EKS のロール、ノードグループ、access entry がどう繋がるかを読んで理解することなので、リソースを直接書く。Module は入力値で内部の構成が隠れるため、まず直接書いた後で比較する教材にする。

- ファイルは `network.tf`（VPC）、`iam.tf`、`eks.tf`、`ecr.tf` に分け、共通タグは provider の `default_tags`（`Project=workboard-learning`、`Phase`、`ManagedBy`）で全リソースに付ける。
- `allowed_account_ids` で操作対象アカウントを固定し、別アカウントの認証情報による誤適用を防ぐ。
- アドオン（vpc-cni、kube-proxy、coredns）は版を固定せず、クラスターの版に合う既定にする。固定すると Kubernetes の更新時に手作業が増える。再現性は下がるため、実際の版を記録する。EBS CSI ドライバーは入れない（[ADR-0012](0012-kustomize-eks-and-throwaway-db.md)）。
- 認可は access entries だけ（`authentication_mode = "API"`）。作成者への自動の管理権限（`bootstrap_cluster_creator_admin_permissions`）は無効にし、変数 `admin_principal_arn` の IAM 主体に `AmazonEKSClusterAdminPolicy` を明示的に付ける。「誰が管理者か」がコードに残る。
- ノードのロールには `AmazonEKSWorkerNodePolicy`、`AmazonEKS_CNI_Policy`、`AmazonEC2ContainerRegistryPullOnly` を付ける。CNI の権限をノードのロールに持たせるのは簡単だが、ノード上の全 Pod が使える権限になる。最小権限化（Pod Identity での分離）は Phase 7 以降の課題。
- ECR はリポジトリ 2 つ（api、web）。タグは変更可能（検証で同じタグを再 push するため）、push 時スキャン有効、古いイメージは直近 5 件だけ残す。`force_delete` は既定で無効にし、イメージが残ったままの削除を失敗させて気づけるようにする。
- コントロールプレーンログは既定で無効（CloudWatch Logs の料金を避ける）。必要なら `cluster_log_types` で有効にし、保持期間は 7 日にする。

### 6. state はローカルファイル（Git 管理外）

`terraform.tfstate` は `.gitignore`（`*.tfstate*`）で除外される。state にはリソース ID などが含まれ、場合によっては機密値も含まれるため、Git に入れない。Remote backend（S3 + ロック）は複数人・複数端末で実務的だが、state 用 S3 バケットの作成（鶏と卵の問題）、バケットの暗号化・バージョニング・削除手順が学習範囲に加わり、バケット自体が残存資産になる。1 人の学習用環境ではローカルとし、PC を失うと state を失い、リソースが手作業での削除になるリスクを受け入れる。`aws-cleanup.md` に、state を失った場合の探し方を書く。

## Alternatives

- **EKS Auto Mode:** 運用は軽いが、ノード・アドオンの責任分界が見えない。追加の管理料金がかかる。後半の比較課題とする。
- **Fargate:** ノード管理が不要だが、DaemonSet が使えない、Pod 単位の課金など制約が異なり、Node の運用責任の学習対象から外れる。
- **community module（terraform-aws-modules）:** 行数・保守性では有利。内部が見えにくいため、直接書いた後の比較対象とする。
- **public endpoint のみ（CIDR 制限なし）/ private のみ:** 前者は攻撃面が広い。後者は VPN や踏み台が必要で、学習の準備が増える。
- **AZ ごとの NAT Gateway:** 可用性は高いが、時間料金が AZ 数だけかかる。
- **NAT なし（public subnet にノード）:** 安いが、ノードが直接インターネットに面する。ノードを private に置く構成の理解を優先する。
- **Remote backend / HCP Terraform:** 実務向き。学習範囲と残存資産が増える。
- **Spot ノード・Graviton（`t4g`）:** 安いが、中断対応と arm64 イメージのビルドが加わる。まず On-Demand の x86_64 で挙動を学ぶ。

## Consequences

- 費用は主に EKS コントロールプレーン、EC2、NAT Gateway で、稼働時間に比例する。放置が最大のリスクで、削除手順（`aws-cleanup.md`）に従う。
- NAT が単一のため、片方の AZ の障害で外向き通信が止まり得る（意図的）。
- API endpoint の許可 CIDR が自分の IP に固定される。IP が変わると `kubectl` と Terraform の一部操作が通らなくなる。
- アドオンの版が固定されないので、再作成時に版が変わり得る。
- state を失うとリソースを Terraform で削除できない。
- Kubernetes 1.35 の標準サポートは 2027-03-27 まで。以後は更新するか、延長サポート（有料）に入る。

## Evidence

2026-11-10 に次を確認した。Terraform と AWS provider は `terraform init -backend=false` と `terraform validate` が成功した。AWS には接続していない（plan/apply 未実施）。

- [Amazon EKS Kubernetes version lifecycle](https://docs.aws.amazon.com/eks/latest/userguide/kubernetes-versions.html)（1.34〜1.37 が標準サポート。1.35 は 2026-01-27 公開、標準サポート終了 2027-03-27）
- [Amazon EKS Pricing](https://aws.amazon.com/eks/pricing/)（標準サポート $0.10、延長サポート $0.60 /クラスター時間）
- [Amazon EKS managed node groups](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html)（AMI の修正版を配備する責任は利用者。private subnet のノードが ECR へ到達するには NAT または VPC endpoint が必要）
- [Cluster API server endpoint](https://docs.aws.amazon.com/eks/latest/userguide/cluster-endpoint.html)（public access CIDR は public endpoint だけに効く。CIDR で制限する場合は private endpoint も有効にするか、ノードの送信元を CIDR に含める）
- [Terraform releases](https://releases.hashicorp.com/terraform/)、[AWS provider](https://registry.terraform.io/providers/hashicorp/aws/latest)
