import { useEffect, useRef, useState } from "react";
import { Button } from "./ui";
import type { Diagram } from "./types";
import { SemanticDiagram } from "./SemanticDiagram";

const initialMessage = "サンプルのタスクが 3 件保存されています。状態の変化を予想し、操作してみましょう。";

function Simulator({ diagram, highlight }: { diagram: Diagram; highlight: (ids: string[]) => void }) {
  const [state, setState] = useState({ records: 3, generation: 1, migrated: true, message: initialMessage });
  const ephemeral = diagram.type === "kubernetes";
  const compose = diagram.type === "compose";

  function replaceApi() {
    highlight(diagram.simulation?.api || []);
    setState(value => ({ ...value, generation: value.generation + 1, message: compose ? "API コンテナを再作成しました。DB の volume は残るので、タスクのデータは保持されます。" : "ReplicaSet が新しい API Pod を補い、Deployment がその ReplicaSet を管理します。Pod の IP が変わっても、Service が通信の入口になります。DB のデータはそのままです。" }));
  }
  function replaceDatabase() {
    highlight(diagram.simulation?.database || []);
    setState(value => ephemeral
      ? { ...value, records: 0, migrated: false, message: "Phase 2 の DB は一時保存です。Pod の置き換えでタスクとスキーマが失われました。migration でテーブルを作り直しても、元のデータは戻りません。" }
      : { ...value, message: compose ? "DB コンテナを再作成しても名前付き volume を再利用すればデータが残ります。volume 自体の削除やホスト障害への備えは別に必要です。" : "同じ PVC を再利用できる範囲では、Pod を置き換えてもデータが残ります。ノードや保存先の喪失まで保証されるわけではありません。" });
  }
  function migrate() {
    highlight(diagram.simulation?.migration || []);
    setState(value => ({ ...value, migrated: true, message: value.records ? "スキーマはすでに最新です。migration はデータのバックアップではなく、テーブルなどの構造を管理します。" : "空の DB にスキーマを作成しました。保存データは 0 件のままです。migration とデータ復元の違いに注目しましょう。" }));
  }
  const metrics = [["API の世代", `v${state.generation}`], ["保存データ", `${state.records} 件`], ["DB スキーマ", state.migrated ? "準備完了" : "未作成"], ["通信の入口", compose ? "コンテナ名: api" : "Service: 接続先を維持"]];
  return <div className="simulator">
    <div className="simulator-heading"><div><span className="eyebrow">TRY IT IN YOUR HEAD</span><h3>もし、この構成を変えたら？</h3></div><span className="badge amber">シミュレーション</span></div>
    <p className="simulation-notice">実際のコンテナや Pod は操作しません。教材のモデル上で、状態の変化を観察します。</p>
    <div className="simulation-state">{metrics.map(([label, value]) => <div className="simulation-metric" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>
    <div className="simulation-controls">
      <Button className="button secondary compact" icon="refresh" onClick={replaceApi}>{compose ? "API を再作成" : "API Pod を置き換える"}</Button>
      <Button className="button secondary compact" icon="layers" onClick={replaceDatabase}>{compose ? "DB を再作成" : "DB Pod を置き換える"}</Button>
      <Button className="button secondary compact" icon="terminal" onClick={migrate}>migration を実行</Button>
      <Button className="text-button" onClick={() => setState({ records: 3, generation: 1, migrated: true, message: "初期状態に戻しました。どの操作がデータに影響するか、予想してから試してみましょう。" })}>リセット</Button>
    </div>
    <div className="simulation-output" role="status" aria-live="polite">{state.message}</div>
  </div>;
}

export function Architecture({ diagram }: { diagram: Diagram }) {
  const [changing, setChanging] = useState<string[]>([]);
  const timer = useRef(0);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  const highlight = (ids: string[]) => {
    window.clearTimeout(timer.current);
    setChanging(ids);
    timer.current = window.setTimeout(() => setChanging([]), 1200);
  };
  return <>
    <div className="card architecture-card">
      <div className="card-topline"><h3>{diagram.title}</h3><span className="diagram-label">INTERACTIVE DIAGRAM</span></div>
      <SemanticDiagram diagram={diagram} changing={changing} />
      <p className="graph-caption">{diagram.caption}</p>
    </div>
    {["compose", "kubernetes", "storage"].includes(diagram.type) && <Simulator diagram={diagram} highlight={highlight} />}
  </>;
}
