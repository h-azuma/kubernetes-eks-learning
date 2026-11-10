# ADR-0017: ECS と EKS の比較の進め方と評価の基準

> **読む順番:** この ADR には Lab 09 の設計課題に答えるときの考え方にあたる内容が含まれます。先に [Phase 9 のラボ](../README.md) の設計課題に自分で答えてから読み、自分の比較の進め方と比べてください。

## Status

提案（2026-11-10）。Phase 9 に適用。学習者が Lab 09 の設計課題に回答し、内容を確認したうえで「採用」に変更する。この ADR は ECS と EKS のどちらを採用するかの結論ではなく、**比較をどう進め、何を基準に評価するか**を決める。

## Context

Phase 6〜8 では EKS を題材にして学んだ。学習の過程で EKS に関する知識と実績が増えるため、そのまま ECS と比較すると、EKS を前提にした見方に偏りやすい。設計書は「EKS 採用を正解として扱わない」ことを求めている。

比較の対象は、少人数の運用チーム、将来の複数サービスの追加といった仮定のシナリオであり、実在の要件ではない。また、料金やサービスの仕様は変動する。比較の方法が曖昧だと、条件の違う数字を比べたり、観察していないことを根拠にしたりしやすい。

## Decision

1. **同一の要件・同一の条件で比べる。** 要件と仮定を先に書き、ECS 案と EKS 案の両方をその要件から設計する。費用は region、稼働時間、構成、調査日を揃える。
2. **どちらも正解としない。** EKS も ECS も、条件つきで選ぶ。結論には「判断が変わる条件」と最も強い反対案を必ず付ける。
3. **8 つの比較軸を同じ粒度で評価する。** 初期構築、運用責任、スケール、可用性、セキュリティ、コスト、開発体験、長期戦略について、事実・根拠・推測を分けて書く。
4. **運用人件費と学習負担を含める。** AWS の利用料だけでなく、運用の工数、人の学習負担、移行費用を、仮定を明示したうえでコストの一部として扱う。
5. **根拠の出所を明示する。** 公式資料の記述、自分が実際に観察したこと、推測を区別する。観察していないことを観察したこととして書かない。
6. **料金の具体値は固定しない。** 料金は都度、公式の料金ページと Pricing Calculator で確認し、調査日を付けて記録する。
7. **不確実性を結論と同じ重さで残す。** 確認できなかったことは追加調査の項目にする。
8. **個人の記録と様式を分ける。** 比較の様式は `phases/09-architecture-review/ecs-vs-eks.md` に置き、学習者の結論と観察は学習ポータルに保存する。

## Alternatives

- **EKS を基準にして ECS の不足を挙げる:** Phase 6〜8 の経験と整合するが、EKS を前提にした偏りが生じ、ECS が適する条件が見えなくなる。
- **機能一覧の比較表だけを作る:** 手早いが、要件と条件が無いため、どちらが適するかを判断できない。
- **AWS 利用料だけを比較する:** 数値で比べやすいが、少人数の運用チームでは運用人件費と学習負担が結論を左右し得るため、判断を誤りやすい。
- **実際に両方を AWS に構築して計測する:** 根拠は強くなるが、費用と削除リスクが増える。この Phase では AWS を操作せず、公式資料と見積もりツールを使う。
- **料金の例を教材に載せる:** 読みやすいが、料金は変わるので、古い数字が正しいものとして残りやすい。
- **成果物を `docs/comparisons/ecs-vs-eks.md` に置く（設計書 §6 の記述）:** 設計書 §4 の構成ツリーと ADR-0007（Phase ごとにディレクトリで完結させる）に合わせ、`phases/09-architecture-review/` に置く。

## Consequences

- 比較に手間がかかる。要件の整理と ECS 案の設計が必要になる。
- 結論が「条件つき」になり、一つの答えを得たい場合は物足りなく感じることがある。
- 運用人件費の工数は仮定に依存し、客観的な数値にならない。仮定を明示して、感度を見る必要がある。
- 公式資料と料金は変わるため、結論には調査日が付き、時間が経つと再確認が必要になる。
- Phase 6〜8 を実行していない場合、その軸の根拠は公式資料と推測に限られ、「未観察」として残る。

## Evidence

2026-11-10 に次の公式資料の URL が到達できることを確認した（ページの内容と最新の仕様・料金は、比較のたびに学習者が確認する）。確認日: 2026-11-10。

- [Amazon ECS 開発者ガイド](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/Welcome.html)
- [Amazon ECS: AWS Fargate](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/AWS_Fargate.html)
- [Amazon ECS: タスクの IAM ロール](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task-iam-roles.html)
- [Amazon ECS: ロードバランシング](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/service-load-balancing.html)
- [Amazon EKS ユーザーガイド](https://docs.aws.amazon.com/eks/latest/userguide/what-is-eks.html)
- [Amazon EKS: Managed Node Groups](https://docs.aws.amazon.com/eks/latest/userguide/managed-node-groups.html)
- [Amazon EKS: Pod Identities](https://docs.aws.amazon.com/eks/latest/userguide/pod-identities.html)
- [Amazon EKS: Auto Mode Best Practices](https://docs.aws.amazon.com/eks/latest/best-practices/automode.html)
- [Amazon ECS Pricing](https://aws.amazon.com/ecs/pricing/)
- [AWS Fargate Pricing](https://aws.amazon.com/fargate/pricing/)
- [Amazon EKS Pricing](https://aws.amazon.com/eks/pricing/)
- [AWS Pricing Calculator](https://calculator.aws/)
