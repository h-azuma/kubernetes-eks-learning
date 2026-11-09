# ADR-0005: Kubernetes エコシステムのツールを段階的に導入する

## Status

採用（2026-11-09）。学習計画の方針として適用。各ツールの導入・バージョン固定は、該当フェーズの開始時に公式資料で確認してから行う。現時点（Phase 2）では、どのツールも導入しない。

## Context

実務の Kubernetes 運用では、素の `kubectl` とマニフェストだけでなく、Kustomize、Helm、Argo CD、k9s などの周辺ツールを組み合わせて使う。学習計画にこれらを含めないと、実務で使う構成とのつながりが見えにくくなる。

一方で、仕組みを理解する前に道具を使うと、「ツールの操作を覚えたこと」と「Kubernetes の仕組みを理解したこと」の区別がつきにくい。設計書の非ゴール（GitOps や Helm などを序盤から全部投入しない）とも衝突する。ツールごとに役割が違い、学ぶ価値と導入の前提条件も異なる。

| ツール | 役割 | 学習上の主な価値 |
| --- | --- | --- |
| Kustomize | マニフェストの環境差分（base / overlay） | `kubectl -k` に組み込み済み。素の YAML を保ったまま差分を管理できる |
| Helm | chart のパッケージ管理と release 管理 | 周辺コンポーネントの多くは chart で配布される。テンプレート生成と release の単位を学べる |
| Argo CD | Git を正とした継続的な同期（GitOps） | 配信方式の設計判断（push 型の apply か、pull 型の同期か）を体験できる |
| k9s | クラスターを観察・操作する TUI | 調査が速くなる。概念の理解には直接つながらない |

## Decision

ツールは、仕組みを `kubectl` とマニフェストで理解した後、必要になったフェーズで導入する。

- **Kustomize（Phase 3）:** 従来どおり、`base` と `kind` overlay で導入する。テンプレートエンジンではなく、パッチで差分を表現する点を設計の問いにする。
- **k9s（Phase 5、任意）:** 障害調査の Runbook を `kubectl` で完成させた後に限り使う。各画面を `kubectl` の操作と API 呼び出しに対応づけることを目的にする。専用 kubeconfig の kind クラスターだけで使い、編集・削除の操作は Runbook の手順に含めない。
- **Helm（Phase 7）:** まず chart の利用者として学ぶ。AWS Load Balancer Controller を公式手順の Helm chart で導入する。chart のバージョンと values を記録し、`helm template` の出力を読んでから適用する。
- **Argo CD（Phase 8）:** まず kind 上で、WorkBoard の Kustomize overlay を同期対象にして試す。EKS での利用は、AWS 利用承認の範囲内で別途判断する。
- **自アプリの Helm chart 化:** Phase 8 で Kustomize と比較してから判断する。比較の結果は別の ADR に記録する。比較せずに、自アプリのマニフェスト管理へ Helm と Kustomize を併用しない。

## Alternatives

- **エコシステムを含めない:** 学習の範囲は小さくなるが、実務の構成や周辺コンポーネントの導入方法とつながらない。
- **最初から Helm で自アプリを管理する:** 実務によくある形だが、テンプレートの記法と values の設計が、Kubernetes の各リソースの理解より先に来る。生成された YAML を読まずに適用する習慣もつきやすい。
- **Phase 2 から k9s を使う:** 観察は速くなる。しかし `kubectl get / describe / logs / events` で調べる手順が身につく前に TUI へ頼ることになり、Runbook も再現しにくくなる。
- **Argo CD を EKS で初めて導入する:** 本番に近い形で試せるが、AWS 費用がかかり、学習要素（EKS、IAM、GitOps）が同時に増える。kind で先に挙動を理解したほうが、原因を切り分けやすい。
- **Flux など他の GitOps ツール:** 比較の候補になり得る。ただし学習の対象を増やさないため、Phase 8 では Argo CD を基準にする。代替案の比較は ADR の範囲に留める。

## Consequences

- 各ツールは導入の前提となる概念（RBAC、Controller、Kustomize の構成など）を学んだ後に登場する。そのため、ツールの出力を Kubernetes のリソースに対応づけて説明できる。
- ツールに触れるのは Phase 5 以降になる。Helm と Argo CD の比較は Phase 7〜8 の後半に寄る。
- Helm は Phase 7（EKS、AWS の有料リソース）で初めて使う。AWS 利用承認が得られない場合は、kind 上で `helm template` による生成結果の確認だけを行う代替手順を、Phase 7 の開始時に検討する。
- 各ツールのバージョン・導入方法・チェックサムの確認は、そのフェーズの作業になる。この ADR では値を固定しない。
- 学習ポータルのフェーズ説明は設計書から生成されるため、教材データの再生成後に反映される。

## Evidence

2026-11-09 時点の設計書の記述（§1.2 非ゴール、§2 技術スタック、Phase 3・5・7・8）と、以下の公式資料の掲載先に基づく。具体的な版と手順は各フェーズで再確認する。

- [Declarative Management Using Kustomize](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/)
- [Helm Docs](https://helm.sh/docs/)
- [Amazon EKS: AWS Load Balancer Controller Installation（Helm）](https://docs.aws.amazon.com/eks/latest/userguide/lbc-helm.html)
- [Argo CD Documentation](https://argo-cd.readthedocs.io/en/stable/)
- [k9s](https://k9scli.io/)
