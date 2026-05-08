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

// Chat
export const chatPolicy = (message: string, token: string) =>
  post("/chat/policy", { message }, token);

export const chatSQL = (message: string, token: string) =>
  post("/chat/sql", { message }, token);

export const chatActions = (message: string, token: string) =>
  post("/chat/actions", { message }, token);

export const chatRouter = (message: string, token: string) =>
  post("/chat/router", { message }, token);
