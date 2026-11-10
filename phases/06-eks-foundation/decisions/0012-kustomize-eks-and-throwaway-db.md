# ADR-0012: EKS の最初のワークロード（使い捨て DB、EBS CSI なし、ECR、入口は port-forward）

> **読む順番:** この ADR には Lab 06 の設計課題の答えにあたる内容が含まれます。先に [Phase 6 のラボ](../README.md) の設計課題に自分で答えてから読み、自分の考えと比べてください。

## Status

提案（2026-11-10）。Phase 6 に適用。学習者が Lab 06 の設計課題に回答し、内容を確認したうえで「採用」に変更する。

## Context

Phase 6 の目的は、EKS 基盤（ネットワーク、IAM、ノード、ECR）の観察と、Web/API のコンテナが EKS で動くことの確認である。DB は Phase 7 で RDS に移すことが決まっている。Phase 3 の DB は StatefulSet + PVC で、EKS で同じ構成を動かすには EBS CSI ドライバー、IAM 権限、StorageClass（gp3）が必要になる。

## Decision

1. **DB は使い捨ての PostgreSQL（emptyDir の Deployment）にする。** Pod が消えるとデータも消える。タスクは検証用のダミーだけを入れる。Phase 7 で RDS に切り替えるため、この Phase で永続化を作り込まない。Phase 2 の DB と同じ形で、`components/postgres-ephemeral` に分けて eks overlay が取り込む（Phase 7 は含めない）。更新時に同じ emptyDir を取り合わないよう `strategy: Recreate` にする。
2. **EBS CSI ドライバーとアドオン用 IAM は入れない。** PVC を使わないので不要で、IAM（Pod Identity か IRSA）・アドオン・StorageClass・AZ 固定の EBS ボリュームという学習対象と残存資産（EBS）を増やさない。ボリュームは削除後も残り得るため、入れないことで `aws-cleanup.md` の点検対象も減る。永続ボリュームを EKS で扱う課題は、必要になった時点で別に設ける。
3. **イメージは ECR に置く。** overlay はダミーのアカウント ID（`111122223333`）のレジストリを指す。`scripts/deploy` が `kubectl kustomize` の出力のダミーのレジストリ文字列を、確認した実アカウントのレジストリに置き換えて `apply` する。実アカウント ID をリポジトリに書かず、standalone の `kustomize` も必要としない。タグ `phase6` は同じタグを再 push して使う。`kubectl rollout restart` を使うので、イメージを更新したら Pod を再起動する。
4. **base は Phase 3 の base をコピーして独立させる。** `imagePullPolicy: Never` のパッチは外す。ConfigMap・Secret の generator と migration Job の削除→適用の運用は Phase 3 と同じ（ADR-0006 の内容を再利用）。意図的な重複（[ADR-0007](../../../docs/adr/0007-phase-directory-layout.md)）。
5. **入口は `kubectl port-forward`（8086）。** ALB と AWS Load Balancer Controller は Phase 7。Phase 6 で公開 URL を作らないので、ALB の費用と外部公開のリスクがない。

## Alternatives

- **StatefulSet + PVC + EBS CSI:** kind の構成に近い。アドオンと IAM が必要で、EBS が残存資産になる。
- **RDS をこの Phase で使う:** Phase 7 の内容が先に来る。Phase 6 の学習（基盤）と Phase 7（マネージドサービス連携）を分けられなくなり、費用が増える。
- **DB なし（API を起動しない）:** 最も安いが、Web/API/DB/Job の連携を EKS で確認できない。
- **イメージを Docker Hub から取得:** ECR を使う手順（認証、push、ノードの pull 権限）を学べない。
- **`kustomize edit set image` で差し替え:** 標準的だがツールを追加で導入する。また実アカウント ID を含む差分が Git に残りやすい。

## Consequences

- DB Pod が再作成されるとデータとスキーマが消える（migration Job の再実行でスキーマは復旧）。故障実験で観察する。
- Phase 6 の検証は port-forward のため、クライアントはローカルから API server 経由で通信する（`kubectl` が許可 CIDR から接続できる必要がある）。
- Phase 6 のデータは Phase 7 に引き継がれない。ローカルのタスクを RDS に移す手順は Phase 7（`data-migration.md`）で扱う。

## Evidence

- `kubectl kustomize phases/06-eks-foundation/kustomize/overlays/eks` で、ダミーの ECR のイメージ参照、ハッシュ付き ConfigMap/Secret、Postgres の Deployment（emptyDir）が出力されることを確認した（クラスターには適用していない）。
- [Amazon EKS managed node groups](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html): private subnet のノードが ECR からイメージを取得するには、NAT Gateway または ECR/S3 の VPC endpoint が必要。
