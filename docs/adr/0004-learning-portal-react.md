# ADR-0004: 学習ポータルの画面を React へ移行する

## Status

採用（2026-11-09）。学習対象の WorkBoard には適用しない。

## Context

ユーザーから、学習ポータルの現在のデザインを維持したまま React へ移行する依頼があった。画面には Phase 切り替え、図解、入力、自動保存、非同期の採点があり、描画と状態をコンポーネント単位で管理する。

## Decision

- 既存 Vite・TypeScript の構成に React・React DOM と型定義を追加する。
- ページ、目次、図解、シミュレーター、回答フォーム、評価を JSX で描画する。保存・採点処理は小さな hook にまとめる。
- 既存 CSS、文言、SVG 座標、API 契約、SQLite、教材データを維持する。
- ルーターや外部の状態管理ライブラリは追加せず、既存のハッシュによる移動と React の標準機能を使う。
- 元の DOM 描画実装は置き換え、二つの描画方式を並行して管理しない。

## Alternatives

- Vanilla TypeScript の継続：追加依存は不要だが、今回の React 移行依頼を満たさない。
- フルスタックフレームワークへの変更：サーバー側も管理できるが、動作済みの Python API と保存機能を変更する必要がなく、今回の範囲には大きすぎる。

## Consequences

React の依存が増える一方、画面の状態と描画を同じコンポーネントで追える。起動方法と保存先は変わらない。入力中の状態や非同期保存の競合に注意し、移行前後の画像・レイアウト比較と操作の回帰確認を行う。

## Evidence

- ユーザーによる「デザインはそのまま React で作り直す」という明示依頼。
- [既存プロジェクトへの React 導入](https://react.dev/learn/add-react-to-an-existing-project)
- [React のバージョン方針・公開版](https://react.dev/versions)
- 実際の固定バージョンは `learning-portal/package.json` と lock ファイルを参照する。
