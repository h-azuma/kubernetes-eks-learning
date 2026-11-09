import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type RefObject } from "react";
import { DiagramText } from "./DiagramText";
import { resourceTitle, ResourceSymbol } from "./ResourceSymbol";
import type { Diagram, DiagramGroup, DiagramNode, DiagramRelation } from "./types";

const groupDescriptions: Record<DiagramGroup["kind"], string> = {
  cluster: "Kubernetes の管理範囲",
  namespace: "論理スコープ · Node の所有・配置範囲ではありません",
  node: "実行場所 · Pod と、その内側の container",
  management: "API に保存する管理宣言 · コンテナやプロセスではありません",
  aws: "AWS サービスの範囲 · Kubernetes クラスターとは別の境界",
  external: "クラスターの外 · 利用者や外部ツール",
};
const relations: Record<DiagramRelation, { label: string; color: string; dash?: string }> = {
  traffic: { label: "通信の向き（HTTP / SQL 等）", color: "var(--accent)" },
  ownership: { label: "管理・所有（実行プロセスではない）", color: "#64748b", dash: "7 5" },
  control: { label: "制御・設定の反映", color: "#8a79a8", dash: "3 5" },
  storage: { label: "データの保存・利用", color: "#b68a4e", dash: "10 3 2 3" },
  configuration: { label: "設定・権限の参照", color: "#8a79a8", dash: "3 5" },
};

type Edge = Diagram["edges"][number];
type Box = { x: number; y: number; width: number; height: number };

function edgeRoute(from: Box, to: Box) {
  const a = { x: from.x + from.width / 2, y: from.y + from.height / 2 };
  const b = { x: to.x + to.width / 2, y: to.y + to.height / 2 };
  const horizontal = Math.abs(a.y - b.y) < Math.min(from.height, to.height) / 2;
  if (horizontal) {
    const sign = Math.sign(b.x - a.x) || 1;
    const start = { x: a.x + from.width / 2 * sign, y: a.y };
    const end = { x: b.x - (to.width / 2 + 7) * sign, y: b.y };
    const center = (start.x + end.x) / 2;
    return { d: `M${start.x} ${start.y} C${center} ${start.y},${center} ${end.y},${end.x} ${end.y}`, x: center, y: (start.y + end.y) / 2 - 10 };
  }
  const sign = Math.sign(b.y - a.y) || 1;
  const start = { x: a.x, y: a.y + from.height / 2 * sign };
  const end = { x: b.x, y: b.y - (to.height / 2 + 7) * sign };
  const center = (start.y + end.y) / 2;
  return { d: `M${start.x} ${start.y} C${start.x} ${center},${end.x} ${center},${end.x} ${end.y}`, x: (start.x + end.x) / 2 + 8, y: center - 8 };
}

function Connections({ edges, canvasRef, selected, layoutKey }: { edges: Edge[]; canvasRef: RefObject<HTMLDivElement | null>; selected: string | null; layoutKey: string }) {
  const [layout, setLayout] = useState<{ width: number; height: number; boxes: Map<string, Box> }>({ width: 1, height: 1, boxes: new Map() });
  useLayoutEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const measure = () => {
      const origin = canvas.getBoundingClientRect();
      const boxes = new Map<string, Box>();
      canvas.querySelectorAll<HTMLElement>("[data-diagram-node]").forEach(element => {
        const box = element.getBoundingClientRect();
        boxes.set(element.dataset.diagramNode!, { x: box.left - origin.left, y: box.top - origin.top, width: box.width, height: box.height });
      });
      setLayout({ width: canvas.offsetWidth, height: canvas.offsetHeight, boxes });
    };
    measure();
    const observer = new ResizeObserver(measure);
    observer.observe(canvas);
    return () => observer.disconnect();
  }, [canvasRef, layoutKey]);
  return <svg className="semantic-edges" width={layout.width} height={layout.height} viewBox={`0 0 ${layout.width} ${layout.height}`} aria-hidden="true">
    <defs>{Object.entries(relations).map(([key, value]) => <marker key={key} id={`arrow-${key}`} viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0 10 5 0 10Z" style={{ fill: value.color }} /></marker>)}</defs>
    {edges.map((edge, index) => {
      const from = layout.boxes.get(edge.from);
      const to = layout.boxes.get(edge.to);
      if (!from || !to) return null;
      const route = edgeRoute(from, to);
      const relation = edge.relation || "traffic";
      const style = relations[relation];
      return <g key={`${edge.from}-${edge.to}-${index}`}>
        <path d={route.d} fill="none" style={{ stroke: style.color }} strokeWidth="2" strokeDasharray={style.dash} markerEnd={`url(#arrow-${relation})`} data-relation={relation} className={`graph-edge${selected && (edge.from === selected || edge.to === selected) ? " is-active" : ""}`} />
        {edge.label && <DiagramText x={route.x} y={route.y} text={edge.label} maxWidth={180} className="edge-label" textAnchor="middle" />}
      </g>;
    })}
  </svg>;
}

function depth(node: DiagramNode, diagram: Diagram, seen = new Set<string>()): number {
  if (seen.has(node.id)) return 0;
  seen.add(node.id);
  const owner = diagram.edges.find(edge => edge.to === node.id && edge.relation === "ownership");
  const parent = owner && diagram.nodes.find(candidate => candidate.id === owner.from && candidate.group === node.group);
  return parent ? depth(parent, diagram, seen) + 1 : 0;
}

function ResourceCard({ node, diagram, selected, changing, onSelect, management }: { node: DiagramNode; diagram: Diagram; selected: boolean; changing: boolean; onSelect: () => void; management: boolean }) {
  const style: CSSProperties = { gridColumn: node.column === undefined ? undefined : node.column + 1, gridRow: management ? depth(node, diagram) + 1 : undefined };
  return <button type="button" style={style} className={`graph-node semantic-node${selected ? " is-selected" : ""}${changing ? " is-changing" : ""}`} data-diagram-node={node.id} data-resource={node.resource || "generic"} aria-label={`${node.label} の役割を確認`} aria-pressed={selected} onClick={onSelect}>
    <div className="resource-heading"><ResourceSymbol resource={node.resource} kind={node.kind} /><div><span className="resource-type">{resourceTitle(node.resource)}</span><strong className="node-label">{node.label}</strong></div></div>
    {node.namespace && <span className="namespace-badge">namespace: {node.namespace}</span>}
    {node.sublabel && <span className="resource-description">{node.sublabel}</span>}
    {!!node.contains?.length && <div className="pod-contents">{node.contains.map((child, index) => {
      const volume = child.resource === "storage.emptydir" || child.resource === "storage.volume";
      return <div className={`contained-resource${volume ? " contained-volume" : ""}`} data-container={volume ? undefined : child.label} data-volume={volume ? child.label : undefined} key={index}>
        <ResourceSymbol resource={volume ? child.resource : "container"} size={20} />
        <span><span className="contained-kind">{volume ? "volume" : "container"}</span><strong>{child.technology || child.label}</strong><span className="contained-name">{child.label}</span></span>
      </div>;
    })}</div>}
  </button>;
}

export function SemanticDiagram({ diagram, changing }: { diagram: Diagram; changing: string[] }) {
  const [viewIndex, setViewIndex] = useState(0);
  const [selected, setSelected] = useState<DiagramNode | null>(null);
  const canvasRef = useRef<HTMLDivElement>(null);
  const tabsRef = useRef<HTMLDivElement>(null);
  const view = diagram.views?.[viewIndex];
  const nodes = diagram.nodes.filter(node => !view || view.nodeIds.includes(node.id));
  const nodeIds = new Set(nodes.map(node => node.id));
  const edges = diagram.edges.filter(edge => nodeIds.has(edge.from) && nodeIds.has(edge.to) && (!view?.relations || !edge.relation || view.relations.includes(edge.relation)));
  const groups = diagram.groups || [];
  const visibleGroups = new Set(nodes.flatMap(node => {
    const ancestors: string[] = [];
    let group = groups.find(candidate => candidate.id === node.group);
    while (group && !ancestors.includes(group.id)) {
      ancestors.push(group.id);
      group = groups.find(candidate => candidate.id === group!.parentId);
    }
    return ancestors;
  }));
  const columns = nodes.some(node => node.column !== undefined) ? Math.max(1, ...nodes.map(node => (node.column ?? 0) + 1)) : Math.max(1, Math.min(nodes.length, 4));
  const renderNode = (node: DiagramNode, management = false) => <ResourceCard key={node.id} node={node} diagram={diagram} selected={selected?.id === node.id} changing={changing.includes(node.id)} onSelect={() => setSelected(node)} management={management} />;
  function renderGroup(group: DiagramGroup) {
    const children = groups.filter(candidate => candidate.parentId === group.id && visibleGroups.has(candidate.id));
    const members = nodes.filter(node => node.group === group.id);
    return <section className={`diagram-group boundary-${group.kind}`} data-boundary={group.kind} data-group={group.id} aria-label={group.label} key={group.id}>
      <header className="boundary-heading">{(group.kind === "node" || group.kind === "namespace") && <ResourceSymbol resource={`kubernetes.${group.kind}`} size={20} />}<strong>{group.label}</strong><span>{group.description || groupDescriptions[group.kind]}</span></header>
      {!!members.length && <div className="group-nodes">{members.map(node => renderNode(node, group.kind === "management"))}</div>}
      {children.map(renderGroup)}
    </section>;
  }
  const shownRelations = [...new Set(edges.map(edge => edge.relation || "traffic"))];
  const hasKubernetes = diagram.nodes.some(node => node.resource?.startsWith("kubernetes."));
  useEffect(() => setSelected(null), [viewIndex]);
  return <>
    {diagram.nodes.every(node => !node.resource) && <p className="diagram-refresh-notice">図の教材データが旧版です。新しい境界・公式アイコンを表示するには、学習ポータルを終了して起動し直してください。学習記録は残ります。</p>}
    {!!diagram.views?.length && <div className="diagram-view-header">
      <div className="diagram-tabs" role="tablist" aria-label="図で確認する関係" ref={tabsRef}>
        {diagram.views.map((candidate, index) => <button key={candidate.id} type="button" role="tab" className={index === viewIndex ? "is-active" : ""} aria-selected={index === viewIndex} tabIndex={index === viewIndex ? 0 : -1} aria-controls="diagram-panel" onClick={() => setViewIndex(index)} onKeyDown={event => {
          if (event.key !== "ArrowLeft" && event.key !== "ArrowRight" && event.key !== "Home" && event.key !== "End") return;
          event.preventDefault();
          const count = diagram.views!.length;
          const next = event.key === "Home" ? 0 : event.key === "End" ? count - 1 : (viewIndex + (event.key === "ArrowRight" ? 1 : -1) + count) % count;
          setViewIndex(next);
          tabsRef.current?.querySelectorAll<HTMLButtonElement>("button")[next]?.focus();
        }}>{candidate.title}</button>)}
      </div>
      {view && <p className="view-description">{view.description}</p>}
    </div>}
    <div className="architecture-layout" id="diagram-panel" role={view ? "tabpanel" : undefined} aria-label={view?.title || diagram.title}>
      <div className="graph-canvas semantic-scroll">
        <div className="semantic-canvas" ref={canvasRef} style={{ "--diagram-columns": columns } as CSSProperties}>
          {nodes.some(node => !node.group || !groups.some(group => group.id === node.group)) && <div className="group-nodes ungrouped-nodes">{nodes.filter(node => !node.group || !groups.some(group => group.id === node.group)).map(node => renderNode(node))}</div>}
          {groups.filter(group => !group.parentId && visibleGroups.has(group.id)).map(renderGroup)}
          <Connections edges={edges} canvasRef={canvasRef} selected={selected?.id || null} layoutKey={`${view?.id || "all"}-${nodes.map(node => node.id).join(",")}`} />
        </div>
        <div className="diagram-hint">ノードを選ぶと役割を確認できます。枠の内外と矢印の種類に注目してください。</div>
      </div>
      <div className="diagram-legend" aria-label="図の凡例">{shownRelations.map(relation => <span key={relation}><i style={{ borderColor: relations[relation].color, borderTopStyle: relations[relation].dash ? "dashed" : "solid" }} />{relations[relation].label}</span>)}</div>
      <aside className="node-detail">
        <div className="eyebrow">EXPLORE THE ARCHITECTURE</div><ResourceSymbol resource={selected?.resource || "document"} size={28} />
        <h3>{selected?.label || "枠と役割を、分けて考える。"}</h3>
        <p>{selected ? selected.description || selected.sublabel || "選択した要素の所属する枠と、矢印の関係を確認しましょう。" : hasKubernetes ? "Pod は実行の単位、その内側が container です。管理オブジェクトや Service は、それとは異なる役割を持ちます。" : "ノードを選ぶと役割を確認できます。要素ごとの記号と矢印をたどり、処理や判断の流れを見てみましょう。"}</p>
        <span className="node-kind">{selected ? resourceTitle(selected.resource) : "クリックして探索"}</span>
      </aside>
    </div>
    <div className="diagram-attribution">アイコン：<a href="https://github.com/kubernetes/community/tree/main/icons" target="_blank" rel="noopener noreferrer">Kubernetes</a><span> / </span><a href="https://aws.amazon.com/architecture/icons/" target="_blank" rel="noopener noreferrer">AWS 公式素材</a><span> / </span><a href="/icons/README.md" target="_blank" rel="noopener noreferrer">出典・利用条件</a><span>。ブラウザーと container 等は汎用記号です。</span></div>
  </>;
}
