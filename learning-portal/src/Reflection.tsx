import { useState } from "react";
import { Button, Icon, SectionHeading, type Notify } from "./ui";
import type { Bootstrap, Feedback, Phase } from "./types";
import type { LearningState } from "./useLearning";

function FeedbackCard({ phase, feedback, stale }: { phase: Phase; feedback: Feedback; stale: boolean }) {
  return <section className="feedback-card">
    <div className="feedback-heading"><div><p className="eyebrow">YOUR LEARNING REFLECTION</p><h3>理解が育っているところ。</h3></div><div className="feedback-score"><strong>{feedback.score}</strong><span>/ 100</span></div></div>
    {stale && <p className="stale-feedback">この評価の後に回答・メモが変わっています。現在の内容で振り返るには、AI ボタンをもう一度押してください。</p>}
    <p className="feedback-summary">{feedback.summary}</p>
    <div className="feedback-columns">{[
      { title: "よく理解できていること", items: feedback.strengths, className: "strengths" },
      { title: "もう一歩、考えてみたいこと", items: feedback.improvements, className: "improvements" },
    ].map(column => <div className={column.className} key={column.className}><h4>{column.title}</h4><ul>{column.items.map((item, index) => <li key={index}>{item}</li>)}</ul></div>)}</div>
    {feedback.questions.map(item => <details className="question-feedback" key={item.id}>
      <summary><span>{phase.questions.find(question => question.id === item.id)?.prompt || item.id}</span><strong>{item.score} / {item.maxScore}</strong></summary>
      <p>{item.feedback}</p>
      {item.suggestedAnswer && <div className="suggested-answer"><h4>考え方の一例</h4><p>{item.suggestedAnswer}</p></div>}
    </details>)}
    {!!feedback.nextSteps.length && <div className="next-steps"><h4>次の一歩</h4><ol>{feedback.nextSteps.map((step, index) => <li key={index}>{step}</li>)}</ol></div>}
  </section>;
}

type Props = { phase: Phase; learning: LearningState; ai: Bootstrap["ai"]; notify: Notify };

export function Goals({ phase, learning }: Pick<Props, "phase" | "learning">) {
  const record = learning.records[phase.id];
  return <section className="content-section goal-section">
    <SectionHeading kicker="CHECK YOUR UNDERSTANDING" title="ここまで、できたこと。" description="実際に確認できたものだけチェック。まだできなくても、その気づきが次の一歩です。" />
    <div className="card goal-card">{phase.goals.map((goal, index) => <label className="goal-item" key={index}>
      <input type="checkbox" checked={!!record.checklist[`goal-${index + 1}`]} onChange={event => learning.setCheck(phase.id, `goal-${index + 1}`, event.target.checked)} /><span>{goal}</span>
    </label>)}</div>
  </section>;
}

export function Reflection({ phase, learning, ai, notify }: Props) {
  const record = learning.records[phase.id];
  const grading = learning.gradingIds.includes(phase.id);
  const [saving, setSaving] = useState(false);
  const save = async () => {
    setSaving(true);
    try { await learning.save(phase.id); notify("この端末に保存しました。"); }
    catch { /* エラーは保存 hook が案内する。 */ }
    finally { setSaving(false); }
  };
  return <section id="reflection" className="content-section reflection-section">
    <SectionHeading kicker="03 / MAKE IT YOURS" title="気づきを、自分のことばに。" description="うまくいったことも、まだわからないことも。書くことで、理解の輪郭が見えてきます。">
      <span className="private-label"><Icon name="shield" size={15} />記録はこの端末に保存</span>
    </SectionHeading>
    {record.imported && <div className="import-notice"><Icon name="check" size={17} /><span>これまでの Markdown の学習記録を読み込みました。元のファイルは変更しません。</span></div>}
    <div className="card notes-card">
      <div className="reflection-card-title"><Icon name="note" size={21} /><h3>観察・学習メモ</h3><span>気づきの記録</span></div>
      {phase.memoFields.map(field => <label className="field-label" key={field.id}><span>{field.label}</span>
        <textarea className="memo-input" rows={3} maxLength={8000} value={record.notes[field.id] || ""} placeholder="実行したこと、観察した結果、気づいたことを書いてみましょう。" onChange={event => learning.setText(phase.id, "notes", field.id, event.target.value)} />
      </label>)}
    </div>
    <div className="card questions-card">
      <div className="reflection-card-title"><Icon name="book" size={21} /><h3>設計の問い</h3><span>答えより、考え方を</span></div>
      <p className="question-intro">正解を急がなくて大丈夫。理由やトレードオフを添えて、今の考えを書いてください。</p>
      {phase.questions.map((question, index) => <div className="question-field" key={question.id}>
        <label className="question-label"><span className="question-prompt"><span className="question-number">Q{index + 1}</span><span>{question.prompt}</span></span>
          <textarea className="answer-input" rows={4} maxLength={8000} value={record.answers[question.id] || ""} placeholder="私はこう考える。なぜなら…" onChange={event => learning.setText(phase.id, "answers", question.id, event.target.value)} />
        </label>
        {!!question.rubric.length && <details className="question-hint"><summary>考えるときのヒント</summary><ul>{question.rubric.map((rubric, rubricIndex) => <li key={rubricIndex}>{rubric}</li>)}</ul></details>}
      </div>)}
      <div className="reflection-actions">
        <Button className="button secondary" icon="note" disabled={saving} onClick={save}>学習記録を保存</Button>
        <Button className="button primary" icon="spark" disabled={!ai.available || grading} title={!ai.available ? ai.message || "Codex CLI に接続されていません" : undefined} onClick={() => learning.grade(phase)}>{grading ? "AI が振り返り中…" : "AI と理解を振り返る"}</Button>
      </div>
      <p className="ai-privacy"><Icon name="shield" size={15} /><span>保存はローカルのみ。AI ボタンを押したときだけ、このフェーズの回答・メモを Codex 経由でモデルサービスへ送信します。</span></p>
      {!ai.available && <p className="ai-unavailable">AI は現在未接続です。{ai.message || "Codex CLI の接続を確認してください。"} 記録の入力・保存は利用できます。</p>}
    </div>
    <div className="feedback-area" aria-live="polite">
      {grading ? <div className="grading-indicator">考え方を読み解いています。通常は数十秒ほどかかります。入力は続けられます。</div> : <>
        {learning.gradeErrors[phase.id] && <p className="feedback-error">{learning.gradeErrors[phase.id]}</p>}
        {record.feedback && <FeedbackCard phase={phase} feedback={record.feedback} stale={learning.stale(phase.id)} />}
      </>}
    </div>
    <div className="phase-complete"><div><h3>自分のことばで説明できそうですか？</h3><p>チェックと振り返りを終えたら、このフェーズを完了に。いつでも学び直せます。</p></div>
      <Button className={`button ${record.completed ? "secondary" : "primary"}`} icon="check" onClick={() => learning.toggleComplete(phase.id)}>{record.completed ? "完了済み · 元に戻す" : "このフェーズを完了する"}</Button>
    </div>
  </section>;
}
