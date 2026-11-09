import { Fragment, type RefObject } from "react";
import { Button, Icon, number } from "./ui";
import type { Phase, PhaseProgress } from "./types";

const groups: Record<number, string> = { 0: "基礎をつくる", 3: "設計と運用を深める", 6: "クラウドへ広げる", 9: "選択する力をつける" };

type Props = {
  phases: Phase[];
  records: Record<string, PhaseProgress>;
  currentIndex: number;
  open: boolean;
  mobile: boolean;
  sidebarRef: RefObject<HTMLElement | null>;
  navigate: (index: number) => void;
  exportNotes: () => void;
};

export function Sidebar({ phases, records, currentIndex, open, mobile, sidebarRef, navigate, exportNotes }: Props) {
  const done = phases.filter(phase => records[phase.id].completed).length;
  return <aside id="sidebar" className={`sidebar${open ? " is-open" : ""}`} ref={sidebarRef} inert={mobile && !open}>
    <a className="brand" href="#phase-2" onClick={event => { event.preventDefault(); navigate(Math.min(2, phases.length - 1)); }}>
      <span className="brand-mark"><Icon name="layers" size={27} /></span>
      <span className="brand-copy"><strong>KUBE PATH</strong><span>LEARN. BUILD. UNDERSTAND.</span></span>
    </a>
    <div className="journey-progress">
      <div className="journey-caption"><span>あなたの学習の道のり</span><strong>{done} / {phases.length}</strong></div>
      <div className="progress-track"><div className="progress-fill" style={{ width: `${done / phases.length * 100}%` }} /></div>
    </div>
    <p className="sidebar-eyebrow">LEARNING PATH</p>
    <nav className="phase-nav" aria-label="学習フェーズ">
      {phases.map((phase, index) => <Fragment key={phase.id}>
        {groups[index] && <div className="nav-group-label">{groups[index]}</div>}
        <button type="button" className={`phase-link${index === currentIndex ? " is-current" : ""}`} aria-current={index === currentIndex ? "page" : undefined} onClick={() => navigate(index)}>
          <span className={`phase-number${records[phase.id].completed ? " done" : ""}`}>{records[phase.id].completed ? <Icon name="check" size={14} /> : number(index)}</span>
          <span className="phase-link-label">{phase.title}</span>
          {index === currentIndex && <span className="current-dot" />}
        </button>
      </Fragment>)}
    </nav>
    <div className="sidebar-footer"><Icon name="shield" size={17} /><span>あなたの端末で、あなたのペースで。</span></div>
    <Button className="export-button" icon="note" onClick={exportNotes}>学習記録をバックアップ</Button>
  </aside>;
}
