import { useCallback, useEffect, useLayoutEffect, useRef, useState } from "react";
import { api } from "./api";
import { Architecture } from "./Architecture";
import { HeroArt } from "./HeroArt";
import { Concepts, Lessons, Sources } from "./Lesson";
import { Goals, Reflection } from "./Reflection";
import { Sidebar } from "./Sidebar";
import { Button, errorMessage, Icon, number, SectionHeading } from "./ui";
import { useLearning } from "./useLearning";
import type { Bootstrap } from "./types";

function indexFromHash(count: number) {
  const match = location.hash.match(/^#phase-(\d+)$/);
  return match ? Math.min(Number(match[1]), count - 1) : Math.min(2, count - 1);
}

function LearningApp({ data }: { data: Bootstrap }) {
  const [toast, setToast] = useState({ message: "", failure: false, visible: false });
  const toastTimer = useRef(0);
  const notify = useCallback((message: string, failure = false) => {
    window.clearTimeout(toastTimer.current);
    setToast({ message, failure, visible: true });
    toastTimer.current = window.setTimeout(() => setToast(value => ({ ...value, visible: false })), failure ? 9000 : 4000);
  }, []);
  const learning = useLearning(data, notify);
  const phases = data.curriculum.phases;
  const [currentIndex, setCurrentIndex] = useState(() => indexFromHash(phases.length));
  const indexRef = useRef(currentIndex);
  const navigating = useRef(false);
  const [mobile, setMobile] = useState(() => window.matchMedia("(max-width: 720px)").matches);
  const [navOpen, setNavOpen] = useState(false);
  const sidebarRef = useRef<HTMLElement>(null);
  const menuRef = useRef<HTMLButtonElement>(null);
  const mainRef = useRef<HTMLElement>(null);
  const focusHeading = useRef(false);
  const phase = phases[currentIndex];
  const pending = learning.pending(phase.id);
  const saveStatus = learning.saveStatus[phase.id];
  const saveLabel = saveStatus === "saving" ? "保存中…" : saveStatus === "error" ? "保存できません・再試行" : pending ? "未保存の変更" : "この端末に保存済み";

  const navigate = useCallback(async (index: number) => {
    if (index < 0 || index >= phases.length || navigating.current) return;
    navigating.current = true;
    try {
      await learning.save(phases[indexRef.current].id);
      indexRef.current = index;
      focusHeading.current = true;
      setCurrentIndex(index);
      setNavOpen(false);
      location.hash = `phase-${index}`;
      window.scrollTo({ top: 0, behavior: "instant" });
    } catch {
      history.replaceState(null, "", `#phase-${indexRef.current}`);
    } finally { navigating.current = false; }
  }, [learning.save, phases]);

  const closeNavigation = useCallback(() => { setNavOpen(false); menuRef.current?.focus(); }, []);

  useLayoutEffect(() => {
    document.title = `Phase ${number(currentIndex)} · ${phase.title} — KUBE PATH`;
    if (focusHeading.current) {
      mainRef.current?.querySelector<HTMLElement>("h1")?.focus({ preventScroll: true });
      focusHeading.current = false;
    }
  }, [currentIndex, phase.title]);

  useEffect(() => {
    if (navOpen) sidebarRef.current?.querySelector<HTMLButtonElement>("[aria-current=page]")?.focus();
  }, [navOpen]);

  useEffect(() => {
    const media = window.matchMedia("(max-width: 720px)");
    const resize = () => { setMobile(media.matches); setNavOpen(false); };
    media.addEventListener("change", resize);
    return () => media.removeEventListener("change", resize);
  }, []);

  useEffect(() => {
    const onHash = () => {
      const index = indexFromHash(phases.length);
      if (!navigating.current && index !== indexRef.current) navigate(index);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, [navigate, phases.length]);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") closeNavigation();
      if (event.key === "Tab" && navOpen && mobile) {
        const focusable = [...(sidebarRef.current?.querySelectorAll<HTMLElement>("a[href], button:not(:disabled)") || [])];
        const first = focusable[0];
        const last = focusable.at(-1);
        if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [closeNavigation, mobile, navOpen]);

  useEffect(() => () => window.clearTimeout(toastTimer.current), []);

  return <>
    <Sidebar phases={phases} records={learning.records} currentIndex={currentIndex} open={navOpen} mobile={mobile} sidebarRef={sidebarRef} navigate={navigate} exportNotes={() => learning.exportNotes(phase.id)} />
    <button type="button" className={`nav-scrim${navOpen ? " is-visible" : ""}`} aria-label="目次を閉じる" onClick={closeNavigation} />
    <main id="main" className="main" ref={mainRef}>
      <header className="topbar">
        <button type="button" className="menu-toggle" ref={menuRef} aria-expanded={navOpen} aria-controls="sidebar" onClick={() => setNavOpen(value => !value)}><Icon name="menu" size={18} /><span>目次</span></button>
        <div className="breadcrumbs"><Icon name="book" size={17} /><span>Kubernetes・EKS 学習ノート</span><span className="breadcrumb-divider">/</span><strong>Phase {number(currentIndex)}</strong></div>
        <button type="button" className={`save-state${pending ? " pending" : ""}${saveStatus === "error" ? " error" : ""}`} aria-live="polite" title="学習記録を保存・再試行" onClick={() => learning.save(phase.id).then(() => notify("この端末に保存しました。")).catch(() => {})}><Icon name={saveStatus === "error" ? "note" : "check"} size={15} /><span>{saveLabel}</span></button>
      </header>
      <div className="page-content" key={phase.id}>
        <section className="hero">
          <div className="hero-copy">
            <div className="hero-eyebrow"><span className="phase-tag">PHASE {number(currentIndex)}</span><span className="hero-line" /><span>{phase.level}</span></div>
            <h1 tabIndex={-1}>{phase.title}</h1><p className="hero-subtitle">{phase.subtitle}</p><p className="hero-summary">{phase.summary}</p>
            <div className="hero-meta"><span className="meta-item"><Icon name="clock" size={15} />約 {phase.estimatedMinutes} 分</span><span className={`badge ${phase.implemented ? "accent" : "amber"}`}>{phase.implemented ? "実環境の教材あり" : "予習 · 実環境は未実装"}</span></div>
          </div>
          <HeroArt />
        </section>
        <nav className="page-route" aria-label="このページの目次">{[["overview", "構成を理解する", "layers"], ["learn", "手を動かす", "terminal"], ["reflection", "考えを残す", "note"]].map(([anchor, label, name]) => <a href={`#${anchor}`} key={anchor} onClick={event => { event.preventDefault(); document.getElementById(anchor)?.scrollIntoView({ behavior: "smooth", block: "start" }); }}><Icon name={name} size={16} />{label}</a>)}</nav>
        <section id="overview" className="content-section">
          <SectionHeading kicker="01 / THE BIG PICTURE" title="点をつなげて、全体像へ。" description="仕組みを覚える前に、役割とつながりを見てみましょう。" />
          <Architecture diagram={phase.diagram} />
        </section>
        <Concepts phase={phase} />
        <Lessons phase={phase} notify={notify} />
        <Goals phase={phase} learning={learning} />
        <Reflection phase={phase} learning={learning} ai={data.ai} notify={notify} />
        <Sources phase={phase} />
        <nav className="chapter-navigation" aria-label="前後のフェーズ">
          {currentIndex > 0 ? <button type="button" className="chapter-prev" onClick={() => navigate(currentIndex - 1)}><Icon name="arrow" size={18} /><span>前のフェーズ</span><strong>{phases[currentIndex - 1].title}</strong></button> : <span />}
          {currentIndex < phases.length - 1 && <button type="button" className="chapter-next" onClick={() => navigate(currentIndex + 1)}><Icon name="arrow" size={18} /><span>次のフェーズへ</span><strong>{phases[currentIndex + 1].title}</strong></button>}
        </nav>
        <footer className="page-footer"><span>KUBE PATH</span><span>小さく試す。深くわかる。自分のことばで残す。</span></footer>
      </div>
    </main>
    <div className={`toast${toast.failure ? " error" : ""}${toast.visible ? " is-visible" : ""}`} role="status" aria-live="polite">{toast.message}</div>
  </>;
}

export default function App() {
  const [data, setData] = useState<Bootstrap | null>(null);
  const [failure, setFailure] = useState("");
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    setFailure("");
    api<Bootstrap>("/bootstrap").then(result => {
      if (!result.curriculum?.phases?.length) throw new Error("教材が見つかりません。ローカルサーバーの教材設定を確認してください。");
      const normalized = { ...result, curriculum: { ...result.curriculum, phases: result.curriculum.phases.map(phase => ({ ...phase, id: String(phase.id) })) } };
      if (active) setData(normalized);
    }).catch(error => { if (active) setFailure(errorMessage(error)); });
    return () => { active = false; };
  }, [attempt]);
  if (data) return <LearningApp data={data} />;
  return <div className="loading-screen"><div className="loading-mark">K</div><h1>{failure ? "学習ノートに接続できません。" : "学びの続きを、ここから。"}</h1><p>{failure || "ローカルの教材と学習記録を読み込んでいます。"}</p>{failure && <Button className="button primary" icon="refresh" onClick={() => setAttempt(value => value + 1)}>もう一度読み込む</Button>}</div>;
}
