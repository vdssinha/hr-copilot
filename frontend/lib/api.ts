const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

function authHeaders(token: string) {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

async function post<T>(path: string, body: unknown, token: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify(body),
  });
  return res.json();
}

// Auth
export async function login(email: string, password: string) {
  const res = await fetch(`${BASE}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  return res.json();
}

// Chat — standard JSON endpoints
export const chatPolicy = (message: string, token: string) =>
  post("/chat/policy", { message }, token);

export const chatSQL = (message: string, token: string) =>
  post("/chat/sql", { message }, token);

export const chatActions = (message: string, token: string) =>
  post("/chat/actions", { message }, token);

export const chatRouter = (message: string, token: string) =>
  post("/chat/router", { message }, token);

export const chatLangGraph = (message: string, token: string) =>
  post("/chat/langgraph", { message }, token);

// Chat — SSE streaming (router/stream)
export type SSEEvent =
  | { type: "status"; message: string }
  | { type: "result"; route: unknown; result: unknown }
  | { type: "error"; message: string }
  | { type: "done" };

export async function streamRouter(
  message: string,
  token: string,
  onEvent: (event: SSEEvent) => void,
): Promise<void> {
  const res = await fetch(`${BASE}/chat/router/stream`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ message }),
  });

  if (!res.ok || !res.body) {
    onEvent({ type: "error", message: "Stream failed" });
    return;
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    const lines = buffer.split("\n");
    buffer = lines.pop() ?? "";

    for (const line of lines) {
      const trimmed = line.trim();
      if (trimmed) {
        try {
          const event = JSON.parse(trimmed) as SSEEvent;
          onEvent(event);
        } catch {
          // skip malformed
        }
      }
    }
  }
}
