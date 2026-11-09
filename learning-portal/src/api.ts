export async function api<T>(path: string, body?: unknown, timeout = 20000): Promise<T> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeout);
  try {
    const response = await fetch(`/api${path}`, {
      method: body === undefined ? "GET" : "POST",
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal,
    });
    const result = await response.json().catch(() => null);
    if (!response.ok) {
      throw new Error(typeof result?.error === "string" ? result.error : `処理できませんでした（HTTP ${response.status}）。もう一度お試しください。`);
    }
    if (!result) throw new Error("サーバーからの応答を読み取れませんでした。");
    return result as T;
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      throw new Error("応答に時間がかかっています。入力は保持されています。少し待って再度お試しください。");
    }
    if (error instanceof TypeError) throw new Error("ローカルサーバーに接続できません。サーバーの起動状態を確認してください。入力はこの画面に保持されています。");
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}
