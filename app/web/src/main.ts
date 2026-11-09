import "./style.css";

const statuses = { TODO: "未着手", IN_PROGRESS: "進行中", DONE: "完了" } as const;
type Status = keyof typeof statuses;
type Task = {
  id: string;
  title: string;
  description: string | null;
  status: Status;
  updated_at: string;
};

const form = document.querySelector<HTMLFormElement>("#task-form")!;
const title = document.querySelector<HTMLInputElement>("#title")!;
const description = document.querySelector<HTMLTextAreaElement>("#description")!;
const status = document.querySelector<HTMLSelectElement>("#status")!;
const filter = document.querySelector<HTMLSelectElement>("#filter")!;
const tasks = document.querySelector<HTMLUListElement>("#tasks")!;
const message = document.querySelector<HTMLParagraphElement>("#message")!;
const save = document.querySelector<HTMLButtonElement>("#save")!;
const cancel = document.querySelector<HTMLButtonElement>("#cancel")!;
let editingId: string | null = null;
let requestNumber = 0;

for (const [value, label] of Object.entries(statuses)) {
  status.add(new Option(label, value));
  filter.add(new Option(label, value));
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await fetch(`/api/v1/tasks${path}`, options);
  if (!response.ok) {
    throw new Error(`操作に失敗しました（HTTP ${response.status}）。入力内容や API・DB の状態を確認してください。`);
  }
  return response.status === 204 ? undefined as T : response.json();
}

function report(error: unknown) {
  message.textContent = error instanceof Error ? error.message : "通信に失敗しました。";
}

function resetForm() {
  editingId = null;
  form.reset();
  save.textContent = "作成";
  cancel.hidden = true;
  document.querySelector("#form-heading")!.textContent = "タスクを作成";
}

function button(label: string, action: () => Promise<void> | void): HTMLButtonElement {
  const element = document.createElement("button");
  element.type = "button";
  element.textContent = label;
  element.addEventListener("click", async () => {
    element.disabled = true;
    try { await action(); } catch (error) { report(error); }
    finally { element.disabled = false; }
  });
  return element;
}

function renderTask(task: Task): HTMLLIElement {
  const item = document.createElement("li");
  const heading = document.createElement("h3");
  heading.textContent = task.title;
  const details = document.createElement("p");
  details.textContent = task.description || "説明なし";
  const meta = document.createElement("p");
  meta.textContent = `${statuses[task.status]} · 更新 ${new Date(task.updated_at).toLocaleString("ja-JP")}`;
  const actions = document.createElement("div");
  actions.className = "actions";
  actions.append(
    button("編集", () => {
      editingId = task.id;
      title.value = task.title;
      description.value = task.description || "";
      status.value = task.status;
      save.textContent = "更新";
      cancel.hidden = false;
      document.querySelector("#form-heading")!.textContent = "タスクを編集";
      title.focus();
    }),
    button("削除", async () => {
      if (!window.confirm(`「${task.title}」を削除しますか？`)) return;
      await request(`/${task.id}`, { method: "DELETE" });
      if (editingId === task.id) resetForm();
      message.textContent = "削除しました。";
      await loadTasks();
    }),
  );
  item.append(heading, details, meta, actions);
  return item;
}

async function loadTasks() {
  const current = ++requestNumber;
  const query = filter.value ? `?status=${encodeURIComponent(filter.value)}` : "";
  const list = await request<Task[]>(query);
  if (current !== requestNumber) return;
  tasks.replaceChildren(...list.map(renderTask));
  document.querySelector<HTMLElement>("#empty")!.hidden = list.length > 0;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  save.disabled = true;
  try {
    await request(editingId ? `/${editingId}` : "", {
      method: editingId ? "PATCH" : "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title: title.value, description: description.value || null, status: status.value }),
    });
    resetForm();
    message.textContent = "保存しました。";
    await loadTasks();
  } catch (error) { report(error); }
  finally { save.disabled = false; }
});

cancel.addEventListener("click", resetForm);
filter.addEventListener("change", () => { loadTasks().catch(report); });
document.querySelector("#refresh")!.addEventListener("click", () => { loadTasks().catch(report); });
loadTasks().catch(report);
