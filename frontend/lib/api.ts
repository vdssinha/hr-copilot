const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

function authHeaders(token: string) {
  return { "Content-Type": "application/json", Authorization: `Bearer ${token}` };
}

async function request<T>(
  path: string,
  options: RequestInit,
  token: string,
): Promise<{ status: number; data: T }> {
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }
  const res = await fetch(`${BASE}${path}`, { ...options, headers: { ...headers, ...(options.headers as Record<string, string> ?? {}) } });
  const data = res.status === 204 ? null : await res.json();
  return { status: res.status, data: data as T };
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

export const chatHrData = (message: string, token: string) =>
  post("/chat/hr-data", { message }, token);

// Chat — SSE streaming (router/stream)
export type SSEEvent =
  | { type: "status"; message: string }
  | { type: "result"; route: unknown; result: unknown }
  | { type: "error"; message: string }
  | { type: "done" };

// ── Admin types ───────────────────────────────────────────────────────────────

export interface AdminUser {
  id: number;
  employee_code: string;
  name: string;
  email: string;
  role: string;
  job_title: string | null;
  department_id: number | null;
  employment_type: string;
  status: string;
  joining_date: string | null;
  policy_group: string | null;
}

export interface AdminPolicyGroup {
  name: string;
  accessible_categories: string[];
}

export interface AdminRole {
  name: string;
  accessible_categories: string[];
}

export interface AdminCategory {
  name: string;
  accessible_by_roles: string[];
}

export interface AdminPolicy {
  id: number;
  title: string;
  category: string;
  filename: string | null;
  is_active: boolean;
  embeddings_generated_at: string | null;
  created_at: string;
}

// ── Admin API ─────────────────────────────────────────────────────────────────

export const admin = {
  listUsers: (token: string) =>
    request<AdminUser[]>("/admin/users", { method: "GET" }, token),

  createUser: (token: string, payload: {
    employee_code: string; name: string; email: string; password: string;
    role: string; job_title?: string; department_id?: number; employment_type: string;
  }) => request<AdminUser>("/admin/users", { method: "POST", body: JSON.stringify(payload) }, token),

  updateUser: (token: string, id: number, payload: Partial<Pick<AdminUser, "name" | "email" | "role" | "job_title" | "status" | "policy_group">>) =>
    request<AdminUser>(`/admin/users/${id}`, { method: "PATCH", body: JSON.stringify(payload) }, token),

  deleteUser: (token: string, id: number) =>
    request<null>(`/admin/users/${id}`, { method: "DELETE" }, token),

  listRoles: (token: string) =>
    request<AdminRole[]>("/admin/roles", { method: "GET" }, token),

  updateRole: (token: string, name: string, accessible_categories: string[]) =>
    request<AdminRole>(`/admin/roles/${name}`, { method: "PATCH", body: JSON.stringify({ accessible_categories }) }, token),

  listCategories: (token: string) =>
    request<AdminCategory[]>("/admin/categories", { method: "GET" }, token),

  updateCategory: (token: string, name: string, accessible_by_roles: string[]) =>
    request<AdminCategory>(`/admin/categories/${name}`, { method: "PATCH", body: JSON.stringify({ accessible_by_roles }) }, token),

  listPolicies: (token: string) =>
    request<AdminPolicy[]>("/admin/policies", { method: "GET" }, token),

  uploadPolicy: (token: string, title: string, category: string, file: File) => {
    const form = new FormData();
    form.append("title", title);
    form.append("category", category);
    form.append("file", file);
    return request<{ success: boolean; data: { policy_id: number; status: string } }>(
      "/admin/policies/upload", { method: "POST", body: form }, token,
    );
  },

  deletePolicy: (token: string, id: number) =>
    request<null>(`/admin/policies/${id}`, { method: "DELETE" }, token),

  reingestPolicies: (token: string) =>
    post("/chat/policy/ingest", {}, token),

  listPolicyGroups: (token: string) =>
    request<AdminPolicyGroup[]>("/admin/policy-groups", { method: "GET" }, token),

  createPolicyGroup: (token: string, name: string, accessible_categories: string[]) =>
    request<AdminPolicyGroup>("/admin/policy-groups", { method: "POST", body: JSON.stringify({ name, accessible_categories }) }, token),

  updatePolicyGroup: (token: string, name: string, accessible_categories: string[]) =>
    request<AdminPolicyGroup>(`/admin/policy-groups/${name}`, { method: "PATCH", body: JSON.stringify({ accessible_categories }) }, token),

  deletePolicyGroup: (token: string, name: string) =>
    request<null>(`/admin/policy-groups/${name}`, { method: "DELETE" }, token),
};

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
