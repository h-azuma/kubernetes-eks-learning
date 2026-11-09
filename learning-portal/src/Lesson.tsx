import { Button, Icon, number, SectionHeading, type Notify } from "./ui";
import type { Phase } from "./types";

function LessonSection({ section, index, notify }: { section: Phase["sections"][number]; index: number; notify: Notify }) {
  const heading = <div className="lesson-heading"><span className="lesson-number">{number(index + 1)}</span><h3>{section.title}</h3></div>;
  const body = <>
    <p className="lesson-body">{section.body}</p>
    {section.callout && <aside className="callout"><Icon name="spark" size={19} /><p>{section.callout}</p></aside>}
    {section.steps?.map((step, stepIndex) => <div className="lesson-step" key={stepIndex}>
      <h4>{step.title}</h4><p>{step.description}</p>
      {step.command && <div className="command-block">
        <div className="command-top"><span>TERMINAL</span><Button className="copy-button" onClick={async () => {
          try { await navigator.clipboard.writeText(step.command!); notify("コマンドをコピーしました。内容を確認してから実行してください。"); }
          catch { notify("コピーできませんでした。コマンドを選択してコピーしてください。", true); }
        }}>コピー</Button></div>
        <pre><code>{step.command}</code></pre>
      </div>}
      {step.expected && <p className="expected-result"><Icon name="check" size={15} /><span>期待する結果：{step.expected}</span></p>}
    </div>)}
  </>;
  return section.kind === "practice"
    ? <details className="card lesson-card practice-card"><summary className="practice-summary">{heading}<span className="badge accent">実習ガイド</span><Icon name="chevron" size={18} /></summary>{body}</details>
    : <article className="card lesson-card">{heading}{body}</article>;
}

export function Concepts({ phase }: { phase: Phase }) {
  return <section className="content-section concepts-section">
    <SectionHeading kicker="KEY CONCEPTS" title="このフェーズの、ことば。" />
    <div className="concept-grid">{phase.concepts.map((concept, index) => <article className="concept-card" key={concept.term}>
      <div className="concept-topline"><span className="concept-number">{number(index + 1)}</span><Icon name="layers" size={20} /></div>
      <h3>{concept.term}</h3><p>{concept.description}</p>
      {concept.analogy && <p className="concept-analogy">たとえるなら、{concept.analogy}</p>}
    </article>)}</div>
  </section>;
}

export function Lessons({ phase, notify }: { phase: Phase; notify: Notify }) {
  return <section id="learn" className="content-section">
    <SectionHeading kicker="02 / LEARN BY DOING" title="理解を、確かめる。" description="「なぜそうなる？」を持ったまま、ひとつずつ進めましょう。" />
    {phase.sections.map((section, index) => <LessonSection section={section} index={index} notify={notify} key={section.id} />)}
  </section>;
}

export function Sources({ phase }: { phase: Phase }) {
  return <section className="sources"><h2>もっと確かめたいときに</h2>
    <div className="source-links">{phase.sources.map(source => <a className="source-link" key={source.path} href={/^https?:\/\//.test(source.path) ? source.path : `/api/source?path=${encodeURIComponent(source.path)}`} target="_blank" rel="noopener noreferrer"><Icon name="external" size={15} /><span>{source.label}</span></a>)}</div>
  </section>;
}
