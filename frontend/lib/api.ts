export type TaskKind = "update-data" | "run-backtest" | "plan-weekly" | "run-paper";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {})
    },
    credentials: "include"
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || `请求失败：${res.status}`);
  }
  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return (await res.json()) as T;
  return (await res.text()) as unknown as T;
}

export const api = {
  me: () => request<{ authed: boolean; user?: string }>("/api/auth/me"),
  login: (username: string, password: string) =>
    request<{ ok: boolean; user: string }>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify({ username, password })
    }),
  logout: () => request<{ ok: boolean }>("/api/auth/logout", { method: "POST" }),

  getConfig: () => request<{ path: string; yaml: string }>("/api/config"),
  putConfig: (yaml: string) =>
    request<{ ok: boolean; backup: string }>("/api/config", {
      method: "PUT",
      body: JSON.stringify({ yaml })
    }),

  createTask: (kind: TaskKind) =>
    request<{ task_id: string }>(`/api/tasks/${kind}`, { method: "POST", body: "{}" }),
  getTask: (id: string) =>
    request<{
      id: string;
      kind: TaskKind;
      status: string;
      message: string;
      error?: string | null;
      outputs?: unknown;
    }>(`/api/tasks/${id}`),
  listTasks: () =>
    request<{ tasks: Array<{ id: string; kind: TaskKind; status: string; message: string }> }>("/api/tasks"),

  listArtifacts: () =>
    request<{ artifacts: Array<{ name: string; size: number; mtime: number }> }>("/api/artifacts"),
  tailLogs: (lines = 300) => request<string>(`/api/logs/tail?lines=${lines}`)
};

