# 図解用の公式アイコン

このディレクトリは、学習ポータルのアーキテクチャ図で使う公式配布素材を収録します。実行時に外部CDNへ接続せず、ポータルからローカル配信します。

## Kubernetes

配布元は [kubernetes/community の Kubernetes Icons Set](https://github.com/kubernetes/community/tree/main/icons) です。Kubernetesリソース用の `icons/svg/resources/unlabeled` と、インフラ用の `icons/svg/infrastructure_components/unlabeled` から必要なSVGを選びます。SVG本体の図形・色・内部情報は変更せず、ローカルでのファイル名だけを分かりやすくしています。

取得日: 2026-11-09。固定commit: [`70a4bb2d8cc35bb0672f221bad9bc60c27a6f94b`](https://github.com/kubernetes/community/tree/70a4bb2d8cc35bb0672f221bad9bc60c27a6f94b/icons)。20個のSVGを収録しました。各ファイルの固定取得URLとSHA-256は [kubernetes/manifest.json](kubernetes/manifest.json)、ライセンス全文は [kubernetes/LICENSE](kubernetes/LICENSE) にあります。API Server用の `api.svg` だけは公式配布のlabeled版です。

| 配信パス | 公式リポジトリ内のパス |
| --- | --- |
| `kubernetes/pod.svg` | `icons/svg/resources/unlabeled/pod.svg` |
| `kubernetes/deployment.svg` | `icons/svg/resources/unlabeled/deploy.svg` |
| `kubernetes/replicaset.svg` | `icons/svg/resources/unlabeled/rs.svg` |
| `kubernetes/service.svg` | `icons/svg/resources/unlabeled/svc.svg` |
| `kubernetes/job.svg` | `icons/svg/resources/unlabeled/job.svg` |
| `kubernetes/statefulset.svg` | `icons/svg/resources/unlabeled/sts.svg` |
| `kubernetes/node.svg` | `icons/svg/infrastructure_components/unlabeled/node.svg` |
| `kubernetes/pvc.svg` | `icons/svg/resources/unlabeled/pvc.svg` |
| `kubernetes/pv.svg` | `icons/svg/resources/unlabeled/pv.svg` |
| `kubernetes/configmap.svg` | `icons/svg/resources/unlabeled/cm.svg` |
| `kubernetes/secret.svg` | `icons/svg/resources/unlabeled/secret.svg` |
| `kubernetes/hpa.svg` | `icons/svg/resources/unlabeled/hpa.svg` |
| `kubernetes/networkpolicy.svg` | `icons/svg/resources/unlabeled/netpol.svg` |
| `kubernetes/serviceaccount.svg` | `icons/svg/resources/unlabeled/sa.svg` |
| `kubernetes/namespace.svg` | `icons/svg/resources/unlabeled/ns.svg` |
| `kubernetes/volume.svg` | `icons/svg/resources/unlabeled/vol.svg` |
| `kubernetes/role.svg` | `icons/svg/resources/unlabeled/role.svg` |
| `kubernetes/clusterrole.svg` | `icons/svg/resources/unlabeled/c-role.svg` |
| `kubernetes/controlplane.svg` | `icons/svg/infrastructure_components/unlabeled/control-plane.svg` |
| `kubernetes/api.svg` | `icons/svg/control_plane_components/labeled/api.svg` |

公式READMEは Apache-2.0 または CC-BY-4.0 の選択を認めています。本教材では **Apache-2.0** を選択します。著作者・貢献者は配布元の Kubernetes Icons Set contributors です。取得したファイル内の権利表示を保持し、Apacheライセンス全文を同梱します。

固定commitのリポジトリ直下には `LICENSE` があり、`NOTICE`・`COPYING` はありませんでした。これは取得時にGitHub公式APIのファイル一覧で確認したものです。

Kubernetesの名称・ロゴは商標です。オープンソースライセンスと商標の利用条件は別であり、[Linux Foundationの商標利用方針](https://www.linuxfoundation.org/legal/trademark-usage) も適用されます。本教材への収録は公式による教材の承認を意味しません。

ブラウザー・汎用コンテナ等の独自の図記号は、この公式Kubernetesリソースアイコンとは区別します。ブラウザーをPodアイコンで表すなど、対象が異なる用途には使いません。

## AWS

配布元は [AWS Architecture Icons](https://aws.amazon.com/architecture/icons/) の公式配布パッケージです。対象はAWSサービスを説明する構成図であり、AWSの承認やスポンサーシップを示すための素材ではありません。アイコンの色や形は変更しません。

AWS公式ページは、構成図や説明資料での素材利用を案内しています。Kubernetes側のApacheライセンスをAWS素材へ適用することはしません。AWSの配布物に含まれる利用ガイドと権利表示を別途保持します。

取得日: 2026-11-09。公式パッケージのリリース名は **07312026** です。配布元は Amazon Web Services で、[公式ページ](https://aws.amazon.com/architecture/icons/) が直接リンクする [Icon package](https://d1.awsstatic.com/onedam/marketing-channels/website/public/shared/architecture-icon-release/Icon-package_07312026.5846e92413caa21490223536cc97f1269e44fa92.zip) から8個のSVGを抽出しました。第三者の再配布リポジトリは利用していません。

| 配信パス | 対象と公式パッケージ内の分類 |
| --- | --- |
| `aws/eks.svg` | Amazon Elastic Kubernetes Service / Service Icons: Containers |
| `aws/ecs.svg` | Amazon Elastic Container Service / Service Icons: Containers |
| `aws/ecr.svg` | Amazon Elastic Container Registry / Service Icons: Containers |
| `aws/rds.svg` | Amazon RDS / Service Icons: Databases |
| `aws/ec2.svg` | Amazon EC2 / Service Icons: Compute |
| `aws/iam.svg` | AWS Identity and Access Management / Service Icons: Security-Identity |
| `aws/vpc.svg` | Amazon Virtual Private Cloud / Service Icons: Networking-Content-Delivery |
| `aws/alb.svg` | Application Load Balancer / Resource Icons: Networking-Content-Delivery |

完全なzip内パス・取得URL・リリース名・zipと各SVGのSHA-256は [aws/manifest.json](aws/manifest.json) にあります。取得したzipにPDF・テキスト・Markdown・HTML・Office文書形式の利用ガイドやライセンス文書はありませんでした。そのため存在しないライセンスファイルを作らず、利用条件の参照先として公式配布ページを記録しています。SVG内のメタデータは保持しています。

取得した版・完全な取得URL・原本とローカル名の対応・ハッシュは、同ディレクトリの出典記録を参照してください。収録していないサービスを、似たアイコンの流用で公式素材として表示しないでください。

## 更新時の確認

1. 公式配布元から取得し、固定commitまたはリリース名・取得日を記録する。
2. 必要なファイルだけを選び、ライセンス・利用ガイド・権利表示を保持する。
3. SVGを改変せず、取得元のバイト列とローカルファイルのハッシュを照合する。
4. アイコンの対象リソースと図の説明が一致していることを確認する。

公式ページ確認日: 2026-11-09。
