# ADR-0007: Phase ごとのディレクトリ構成

## Status

採用（2026-11-10）。ユーザーの決定。全体に適用。

## Context

この学習リポジトリを後でチームに展開する。メンバーは Phase 1 から順に学び、先の Phase の答えや他人の記録を目にせずに進められる必要がある。

これまでは種類ごとに資材を分けていた（`labs/`、`docker/`、`kubernetes/`、`scripts/`、`docs/architecture/`、`docs/adr/`）。この構成では、ある Phase の資材が複数のディレクトリに散らばり、Phase を単独で読み・動かすことが難しい。ADR には設計課題の答えにあたる内容が含まれるため、課題より先に目に入りやすい。また、観察結果と設計課題への回答がラボ README に書かれていたため、教材（全員共通）と個人の記録（人ごとに違う）がファイルの中で混ざっていた。

## Decision

- ラボ手順・マニフェスト・スクリプト・構成図・その Phase の ADR を `phases/NN-xxx/` に集める。`app/`（共通の WorkBoard）と `tools/`（preflight、kind 導入、学習ポータル起動、kind 共通処理）は全 Phase 共通として分ける。
- 各 Phase は他の Phase のディレクトリを参照せず、単独で動く。Phase 3 は自分の `cluster.yaml` と `kustomize/` を持ち、Phase 2 の `cluster.yaml` やマニフェストを使わない。
- Phase 別の ADR は `phases/NN-xxx/decisions/` に提案として置き、設計課題に答えた**後で**読む。全体に関わる ADR（0001、0004、0005、0007）は `docs/adr/` に置き、`docs/adr/README.md` で全 ADR の所在を示す。ADR の番号は全体で一意とし、移動しても変えない。
- 個人の記録（観察結果・設計課題への回答）は README に書かず、学習ポータル（各自の PC の Git 管理外 `learning-portal/.data`）にだけ保存する。ラボ README の「学習メモ」節は、記録する項目の一覧と案内だけを持つ。
- クラスター名・kubeconfig・ポート・Compose のプロジェクト名と volume 名は変えない（`workboard-lab` / `.kube/workboard-kind.yaml` / 8080、`workboard-phase3` / `.kube/workboard-phase3.yaml` / 8081、Compose の `name: workboard`）。`.tools/` と `.kube/` はリポジトリ直下に残す。

## Alternatives

- **現構成のまま Git タグで Phase を区切る:** ディレクトリは増えないが、メンバーはタグを切り替えながら学ぶことになり、学習中に先の Phase の資材を見られない代わりに、全体像も見えない。切り替えのたびに作業ツリーが変わり、個人の記録も失われやすい。
- **README に記録し、各自が fork する:** 追加の仕組みは要らないが、fork ごとに教材の更新を取り込む手間が出る。回答が Git 履歴に残り、他人に見えてしまう。
- **互換用のシムやリダイレクトを残す:** 旧パスのコマンドが動き続けるが、要らないファイルが増え、どれが正かが分からなくなる（YAGNI）。パスはすべて新構成に更新した。

## Consequences

- Phase 間で意図的な重複が生まれる。Phase 3 の `cluster.yaml` は Phase 2 と内容が同じ短いファイルで、Phase 3 の `kustomize/base` の Web/API の定義も Phase 2 の `manifests/` と重複する。Phase を独立させる価値を優先し、共通化しない。kind の導入・前提確認・イメージ読み込みなど、動作が同じ処理は `tools/kind-common.ps1`（Bash 版は `kind-common.sh`、[ADR-0008](0008-linux-support.md)）に集めた。
- `app/` は全 Phase で共通なので、後の Phase で変更しても、前の Phase の手順が動き続けるよう後方互換を保つ必要がある。
- ファイルのパスが変わる。旧パス（`labs/`、`scripts/kind-up.ps1 -Phase 3` など）のコマンドは動かない。`phases/NN-*/scripts/env.ps1` と `up.ps1` を使う。
- 既存の環境（kind クラスター、kubeconfig、Compose の volume、Phase 3 の `db.env`）は、名前を変えないため作り直さずに使い続けられる。`db.env` は新しい overlay の `secrets/` へ移す（Git 管理外）。
- 学習ポータルは新しい場所のラボ・設計書を読み、記録は引き続きローカルの `.data` に保存される。ポータルを起動中の場合は、再起動すると新しいパスを読む。

## Evidence

- 構成変更後に、`docker compose -f phases/01-compose/compose.yaml config` の volume 名が変更前と同じ（`workboard_postgres-data`）であること、`kubectl kustomize` の出力と Secret のハッシュ付き名が変更前と同じであること、既存の `workboard-phase3` に対して `phases/03-config-storage/scripts/up.ps1` が冪等に成功することを確認した。
- 学習ポータルの教材生成・テスト・ビルドが成功し、Phase 0〜3 が実装済み、Phase 4〜9 が予習のままであることを確認した。
