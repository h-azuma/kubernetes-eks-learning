import { useState } from "react";
import { Button, Icon, InlineText, number, SectionHeading, type Notify } from "./ui";
import type { Phase } from "./types";

type Shell = "powershell" | "bash";
const SHELL_KEY = "workboard-portal-shell";
const SHELL_LABELS: Record<Shell, string> = { powershell: "Windows (PowerShell)", bash: "Linux / macOS / WSL (Bash)" };

function initialShell(): Shell {
  try {
    const saved = localStorage.getItem(SHELL_KEY);
    if (saved === "powershell" || saved === "bash") return saved;
  } catch { /* 保存値が無くても OS から選べる。 */ }
  return /Windows/i.test(navigator.userAgent) ? "powershell" : "bash";
}

function LessonSection({ section, index, notify, shell, onShell }: { section: Phase["sections"][number]; index: number; notify: Notify; shell: Shell; onShell: (shell: Shell) => void }) {
  const heading = <div className="lesson-heading"><span className="lesson-number">{number(index + 1)}</span><h3>{section.title}</h3></div>;
  const body = <>
    <p className="lesson-body"><InlineText text={section.body} /></p>
    {section.callout && <aside className="callout"><Icon name="spark" size={19} /><p><InlineText text={section.callout} /></p></aside>}
    {section.steps?.map((step, stepIndex) => {
      const command = shell === "bash" && step.linuxCommand ? step.linuxCommand : step.command;
      return <div className="lesson-step" key={stepIndex}>
      <h4>{step.title}</h4><p><InlineText text={step.description} /></p>
      {command && <div className="command-block">
        <div className="command-top">{step.linuxCommand
          ? <span className="shell-tabs" role="group" aria-label="シェルの選択">{(Object.keys(SHELL_LABELS) as Shell[]).map(name => <Button key={name} className="shell-tab" aria-pressed={shell === name} onClick={() => onShell(name)}>{SHELL_LABELS[name]}</Button>)}</span>
          : <span>{step.shell ? `${SHELL_LABELS[step.shell]} のみ` : "TERMINAL"}</span>}<Button className="copy-button" onClick={async () => {
          try { await navigator.clipboard.writeText(command); notify("コマンドをコピーしました。内容を確認してから実行してください。"); }
          catch { notify("コピーできませんでした。コマンドを選択してコピーしてください。", true); }
        }}>コピー</Button></div>
        <pre><code>{command}</code></pre>
      </div>}
      {step.expected && <p className="expected-result"><Icon name="check" size={15} /><span>期待する結果：<InlineText text={step.expected} /></span></p>}
    </div>;
    })}
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
      <h3>{concept.term}</h3><p><InlineText text={concept.description} /></p>
      {concept.analogy && <p className="concept-analogy">たとえるなら、<InlineText text={concept.analogy} /></p>}
    </article>)}</div>
  </section>;
}

export function Lessons({ phase, notify }: { phase: Phase; notify: Notify }) {
  const [shell, setShell] = useState<Shell>(initialShell);
  const chooseShell = (next: Shell) => {
    setShell(next);
    try { localStorage.setItem(SHELL_KEY, next); } catch { /* 保存できなくても選択は有効。 */ }
  };
  return <section id="learn" className="content-section">
    <SectionHeading kicker="02 / LEARN BY DOING" title="理解を、確かめる。" description="「なぜそうなる？」を持ったまま、ひとつずつ進めましょう。" />
    {phase.sections.map((section, index) => <LessonSection section={section} index={index} notify={notify} shell={shell} onShell={chooseShell} key={section.id} />)}
  </section>;
}

export function Sources({ phase }: { phase: Phase }) {
  return <section className="sources"><h2>もっと確かめたいときに</h2>
    <div className="source-links">{phase.sources.map(source => <a className="source-link" key={source.path} href={/^https?:\/\//.test(source.path) ? source.path : `/api/source?path=${encodeURIComponent(source.path)}`} target="_blank" rel="noopener noreferrer"><Icon name="external" size={15} /><span>{source.label}</span></a>)}</div>
  </section>;
}
