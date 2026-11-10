# ADR-0016: WorkBoard のマニフェストを Helm chart にするかの比較

> **読む順番:** この ADR には Lab 08 の設計課題の答えにあたる内容が含まれます。先に [Phase 8 のラボ](../README.md) の設計課題に自分で答えてから読み、自分の考えと比べてください。

## Status

提案（2026-11-10）。Phase 8 に適用。学習者が Lab 08 の設計課題に回答し、内容を確認したうえで「採用」に変更する。[ADR-0005](../../../docs/adr/0005-kubernetes-ecosystem-tools.md) の「自アプリの Helm chart 化は Phase 8 で Kustomize と比較してから判断し、別の ADR に記録する」に対応する。

## Context

WorkBoard（Web・API・移行 Job・PostgreSQL）のマニフェストは、Phase 3 から Kustomize の `base` + `overlays` + `components` で管理している。ADR-0005 は、Helm の導入を Phase 7 の周辺コンポーネント（AWS Load Balancer Controller）の「利用者」としての経験に限り、自アプリへの適用は比較してから決めるとした。比較せずに併用しない、とも定めている。

設計書 §6 Phase 8 は、次の 3 つの基準で比較することを求めている。

- 差分の見通し（環境ごとに何が違うかを読めるか）
- レビューのしやすさ（変更の影響を、レビューで確認できるか）
- 配布の必要性（他の人・他の環境へ渡す必要があるか）

現状の事実:

- 環境は kind（Phase 3〜5、8）と EKS（Phase 6・7）の 2 種類。環境ごとの差は、イメージの置き場所とタグ、`imagePullPolicy`、DB の接続先、Secret の作り方、DB を Pod にするか RDS にするか、Ingress の有無で、数が少ない。
- 差分は overlay（kind は 40 行、Phase 7 の eks は 30 行の kustomization と 27 行の Ingress）に収まっている。
- 配布先は、この学習リポジトリ内に限られる。外部の利用者に chart を配る予定はない。
- Argo CD は Kustomize と Helm のどちらも同期対象にできる。

## Decision

**WorkBoard のマニフェストは Kustomize のまま管理し、Helm chart 化しない。**

| 基準 | Kustomize（現状） | Helm chart |
| --- | --- | --- |
| 差分の見通し | 素の YAML が `base` にあり、環境の差は overlay のパッチ・`images`・generator に集まる。`kubectl kustomize` の出力は完成した YAML そのもの | 差分は `values.yaml` と、テンプレートの条件分岐（`if`/`range`）に分かれる。描画しないと最終形が分からない |
| レビューのしやすさ | 差分は YAML のパッチなので、そのまま読める。パッチが当たらない場合は生成時に失敗する | values の変更が、どのテンプレートのどこに効くかを追う必要がある。`helm template` の出力の差分を併せてレビューする運用が要る |
| 配布の必要性 | 不要。リポジトリのパスを指せば足りる。他人に渡す場合は、パスと overlay の使い方を伝える | 必要な場合に強い。バージョン付きのパッケージ、依存関係、`helm install/upgrade/rollback`、リリース履歴を、他のチームに渡せる |
| 環境の数・パラメーター | 環境が少ない間は十分。利用者が自由に値を入れる形には向かない | 利用者が多様な値を渡す場合に向く |
| 学習上のコスト | `kubectl -k` に組み込み済み。追加のツールがいらない | テンプレート記法と values の設計という別の学習対象が加わる |

理由は、配布の必要がなく、環境の差も小さく、差分とレビューの基準で Kustomize が上回るため。Helm が上回るのは「他者に配る」場合だけで、現状は該当しない。

次のいずれかが起きたら、再評価する。

- WorkBoard を、WorkBoard の作者以外の組織・クラスターに配布する必要が出た。
- 環境の数や、環境ごとに利用者が決める値が増え、overlay の複製が管理できなくなった。
- リリースの履歴や rollback を、Helm のリリース単位で管理する必要が出た。

### 併用しない

同じアプリのマニフェストに Helm と Kustomize を併用しない。Helm で描画した出力を Kustomize でパッチする形（`helm template` → overlay）や、Kustomize の `helmCharts` は、次の複雑さを持ち込む。

- 値を変える場所が 2 つになる（values と overlay のパッチ）。どちらが優先されるか、どちらを直すべきかが分かりにくい。
- chart のテンプレートが変わると、overlay のパッチが当たらなくなる、または意図せず当たる。
- 描画が 2 段になり、Argo CD の同期やレビューで最終形を確認する手順が増える。

周辺コンポーネントの Helm（AWS Load Balancer Controller など）は、アプリのマニフェストとは別の管理単位なので併用の対象ではない。

## Alternatives

- **WorkBoard を Helm chart にする:** 配布先が増える場合には合理的。現状は配布の必要がなく、テンプレートの書き方と values の設計が増えるだけになる。ADR-0005 の懸念（生成された YAML を読まずに適用する習慣）にも当たる。
- **Helm で環境差を表し、Kustomize で最後に調整する:** 柔軟だが上記の理由で併用を避けた。
- **Kustomize の `helmCharts` で既存の chart だけ取り込む:** WorkBoard 自体ではなく第三者の chart（Prometheus など）を使う場合の選択肢。Phase 8 では Prometheus を最小構成で自作したため使っていない。
- **overlay を増やさず、スクリプトの `sed` で置換する:** Phase 7 の `deploy` や CD の描画後の置換が実際にこの方式を一部使っている。置換対象が増えると、どこで何が変わるかが見えなくなる。ダミー値の置換は最小限にとどめる。

## Consequences

- Phase 8 でも、`kustomize/base` + `components` + `overlays/kind` の構成を維持する。
- Argo CD の Application は Kustomize の overlay を指す。
- chart 化を再評価するときは、この ADR の基準（差分の見通し・レビュー・配布）で、実際の差分の数を数えて比較する。
- 環境ごとの置換（CD での `sed`）は Kustomize で表現できていない部分で、将来 overlay の `images` や patch に寄せる余地がある。

## Evidence

2026-11-10 時点。

- Phase 3〜8 のリポジトリ内の overlay の行数（本 ADR の Context に記載）は、リポジトリを `wc -l` で数えた。環境の差が少ないことの根拠は、`phases/04-reliability-scaling/kustomize/overlays/kind` と `phases/07-aws-integration/kustomize/overlays/eks`、`phases/08-devops-observability/kustomize/overlays/kind` の中身。
- 実際に Helm chart を作って比較したものではない。本 ADR は、設計の比較と現状の事実に基づく提案である。
- 参考資料: [Helm: Charts](https://helm.sh/docs/topics/charts/)、[Kustomize のリファレンス](https://kubectl.docs.kubernetes.io/references/kustomize/)、[Argo CD: Kustomize](https://argo-cd.readthedocs.io/en/stable/user-guide/kustomize/)、[Kubernetes: Kustomize による宣言的管理](https://kubernetes.io/docs/tasks/manage-kubernetes-objects/kustomization/)、[Helm Docs](https://helm.sh/docs/)
