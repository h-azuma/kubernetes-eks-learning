import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { errorMessage, type Notify } from "./ui";
import type { Bootstrap, Feedback, Phase, PhaseProgress } from "./types";

const draftKey = "kube-path-emergency-drafts-v1";
const signature = (value: PhaseProgress) => JSON.stringify({ notes: value.notes, answers: value.answers, checklist: value.checklist, completed: value.completed });
const answerSignature = (value: PhaseProgress) => JSON.stringify({ notes: value.notes, answers: value.answers });
type ProgressMap = Record<string, PhaseProgress>;

function initialRecords(data: Bootstrap) {
  const records: ProgressMap = {};
  const saved = new Map<string, string>();
  const feedbackInputs = new Map<string, string>();
  for (const phase of data.curriculum.phases) {
    const value = data.progress[phase.id] || { notes: {}, answers: {}, checklist: {}, completed: false, updatedAt: null, feedback: null };
    records[phase.id] = value;
    saved.set(phase.id, signature(value));
    feedbackInputs.set(phase.id, answerSignature(value));
  }
  let restored = false;
  try {
    const drafts = JSON.parse(localStorage.getItem(draftKey) || "{}");
    for (const phase of data.curriculum.phases) {
      const draft = drafts[phase.id];
      if (draft?.value && draft.savedAt > Date.parse(records[phase.id].updatedAt || "1970-01-01")) {
        const value = draft.value;
        if (value.notes && value.answers && value.checklist && typeof value.completed === "boolean") {
          records[phase.id] = { ...records[phase.id], notes: value.notes, answers: value.answers, checklist: value.checklist, completed: value.completed };
          restored = true;
        }
      }
    }
  } catch { /* 読めない下書きは使わず、サーバーの保存内容を表示する。 */ }
  return { records, saved, feedbackInputs, restored };
}

export function useLearning(data: Bootstrap, notify: Notify) {
  const [initial] = useState(() => initialRecords(data));
  const [records, setRecords] = useState(initial.records);
  const recordsRef = useRef(records);
  const savedRef = useRef(initial.saved);
  const feedbackInputsRef = useRef(initial.feedbackInputs);
  const [saveStatus, setSaveStatus] = useState<Record<string, "saving" | "error" | undefined>>({});
  const [gradingIds, setGradingIds] = useState<string[]>([]);
  const gradingRef = useRef(new Set<string>());
  const [gradeErrors, setGradeErrors] = useState<Record<string, string>>({});
  const queueRef = useRef<Promise<void>>(Promise.resolve());
  const timerRef = useRef(0);

  const update = useCallback((id: string, change: (value: PhaseProgress) => PhaseProgress) => {
    const next = { ...recordsRef.current, [id]: change(recordsRef.current[id]) };
    recordsRef.current = next;
    setRecords(next);
  }, []);

  const backupDrafts = useCallback(() => {
    try {
      const drafts: Record<string, { value: PhaseProgress; savedAt: number }> = {};
      for (const [id, value] of Object.entries(recordsRef.current)) {
        if (signature(value) !== savedRef.current.get(id)) drafts[id] = { value, savedAt: Date.now() };
      }
      if (Object.keys(drafts).length) localStorage.setItem(draftKey, JSON.stringify(drafts));
      else localStorage.removeItem(draftKey);
    } catch { /* ローカルストレージが使えなくてもサーバーへの保存は続ける。 */ }
  }, []);

  const save = useCallback((id: string): Promise<void> => {
    window.clearTimeout(timerRef.current);
    const task = queueRef.current.catch(() => {}).then(async () => {
      const snapshot = signature(recordsRef.current[id]);
      if (savedRef.current.get(id) === snapshot) return;
      setSaveStatus(value => ({ ...value, [id]: "saving" }));
      try {
        const result = await api<{ progress: PhaseProgress }>(`/progress/${encodeURIComponent(id)}`, JSON.parse(snapshot));
        savedRef.current.set(id, snapshot);
        // 応答を待つ間にも入力できるため、本文は最新の state/ref を保持する。
        update(id, value => ({ ...value, updatedAt: result.progress.updatedAt, imported: result.progress.imported }));
        backupDrafts();
        setSaveStatus(value => ({ ...value, [id]: undefined }));
      } catch (error) {
        backupDrafts();
        setSaveStatus(value => ({ ...value, [id]: "error" }));
        notify(errorMessage(error), true);
        throw error;
      }
    });
    queueRef.current = task;
    return task;
  }, [backupDrafts, notify, update]);

  const flush = useCallback(async (id: string) => {
    do { await save(id); }
    while (signature(recordsRef.current[id]) !== savedRef.current.get(id));
  }, [save]);

  const edit = useCallback((id: string, change: (value: PhaseProgress) => PhaseProgress) => {
    update(id, change);
    setSaveStatus(value => ({ ...value, [id]: undefined }));
    backupDrafts();
    window.clearTimeout(timerRef.current);
    timerRef.current = window.setTimeout(() => { save(id).catch(() => {}); }, 1100);
  }, [backupDrafts, save, update]);

  const setText = useCallback((id: string, group: "notes" | "answers", field: string, text: string) => {
    edit(id, value => ({ ...value, [group]: { ...value[group], [field]: text } }));
  }, [edit]);

  const setCheck = useCallback((id: string, field: string, checked: boolean) => {
    edit(id, value => ({ ...value, checklist: { ...value.checklist, [field]: checked } }));
  }, [edit]);

  const toggleComplete = useCallback(async (id: string) => {
    edit(id, value => ({ ...value, completed: !value.completed }));
    try {
      await flush(id);
      notify(recordsRef.current[id].completed ? "ひとつ前へ進みました。おつかれさまでした。" : "完了状態を解除しました。");
    } catch { /* 保存失敗の案内は save が表示する。 */ }
  }, [edit, flush, notify]);

  const grade = useCallback(async (phase: Phase, provider: string) => {
    const id = phase.id;
    if (gradingRef.current.has(id)) return;
    if (!Object.values(recordsRef.current[id].answers).some(answer => answer.trim())) {
      notify("設計の問いにひとつ以上回答してから、AI と振り返ってみましょう。", true);
      return;
    }
    gradingRef.current.add(id);
    setGradingIds([...gradingRef.current]);
    setGradeErrors(value => ({ ...value, [id]: "" }));
    try {
      await flush(id);
      const snapshot = answerSignature(recordsRef.current[id]);
      const result = await api<{ feedback: Feedback; progress?: PhaseProgress }>(`/grade/${encodeURIComponent(id)}`, { ...JSON.parse(snapshot), provider }, 270000);
      feedbackInputsRef.current.set(id, snapshot);
      update(id, value => ({ ...value, feedback: result.feedback }));
      notify("振り返りが届きました。良かった点と、次の一歩を見てみましょう。");
    } catch (error) {
      setGradeErrors(value => ({ ...value, [id]: errorMessage(error) }));
      notify(errorMessage(error), true);
    } finally {
      gradingRef.current.delete(id);
      setGradingIds([...gradingRef.current]);
    }
  }, [flush, notify, update]);

  const exportNotes = useCallback(async (id: string) => {
    try {
      await flush(id);
      const blob = new Blob([JSON.stringify({ exportedAt: new Date().toISOString(), progress: recordsRef.current }, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `kube-path-notes-${new Date().toISOString().slice(0, 10)}.json`;
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
      notify("学習記録を JSON ファイルに書き出しました。");
    } catch { /* 保存エラーは save が表示する。 */ }
  }, [flush, notify]);

  useEffect(() => {
    if (initial.restored) notify("前回保存できなかった下書きを復元しました。「学習記録を保存」で確定できます。");
  }, [initial.restored, notify]);

  useEffect(() => {
    const beforeUnload = (event: BeforeUnloadEvent) => {
      if (Object.entries(recordsRef.current).some(([id, value]) => signature(value) !== savedRef.current.get(id))) {
        backupDrafts();
        event.preventDefault();
      }
    };
    window.addEventListener("beforeunload", beforeUnload);
    return () => { window.removeEventListener("beforeunload", beforeUnload); window.clearTimeout(timerRef.current); };
  }, [backupDrafts]);

  return {
    records, saveStatus, gradingIds, gradeErrors,
    pending: (id: string) => signature(records[id]) !== savedRef.current.get(id),
    stale: (id: string) => feedbackInputsRef.current.get(id) !== answerSignature(records[id]),
    save: flush, setText, setCheck, toggleComplete, grade, exportNotes,
  };
}

export type LearningState = ReturnType<typeof useLearning>;
