# ADR-0001: WorkBoard と段階的な学習スタック

## Status

採用（2026-11-08）。技術の具体的なバージョンは各フェーズで検証して固定する。

## Context

目的は Kubernetes / EKS の設計・運用判断を学ぶこと。業務機能や UI の複雑さに学習時間を取られない、小さな同一アプリを継続して利用する必要がある。

## Decision

タスク CRUD を行う WorkBoard を題材にする。静的画面は Vanilla TypeScript + Vite、配信と API 転送は Nginx、API は Python + FastAPI、DB は PostgreSQL、スキーマ管理は SQLAlchemy + Alembic を採用する。Phase 1 は Docker Compose、後続で kind、Kustomize、Terraform による EKS へ進める。

Phase 0 は文書・設定・参照のみの環境確認を用意する。環境確認は PowerShell と Bash の小さな関数で各ツールのローカルバージョンを取得し、追加依存は導入しない。一次設計書は既存の原本に一本化し、`PROJECT_DESIGN.md` はリンク用の入口とする。

## Alternatives

- React: UI の拡張には適するが、本教材ではフレームワーク固有の学習が増える。
- SQLite: 初期構成は簡単だが、DB 接続・サービス名解決・外部 DB・永続化の学習対象が減る。
- 最初から EKS: AWS 固有の設計を学べるが、費用と構成要素が増え、Kubernetes 自体の観察が難しくなる。
- 設計書のコピー: 指定ファイル単体で読めるが、二つの設計書の同期が必要になる。

## Consequences

画面・API・DB の責任を追いやすく、Compose と Kubernetes の違いを同じアプリで比較できる。一方、Python と TypeScript 両方のツールが必要になり、DB の migration 管理も必要になる。これらの実装は Phase 1 で行う。

二つのシェルの環境確認は同じ対象と判定方針を持つが、各 OS の標準機能で直接書く。共通ランタイムの導入より読みやすさと実行の簡単さを優先する。

## Evidence

- [一次設計書](../kubernetes-eks-hands-on-design.md) セクション 0、2.3、4.1、6、7、10.1。
- Phase 0 ではライブラリやイメージを追加しない。サポートバージョン、互換性、サービス仕様は各フェーズ開始時に公式資料で確認する。
