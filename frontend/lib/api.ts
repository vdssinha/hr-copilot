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
export type HistoryMessage = { role: "user" | "assistant"; content: string };

export const chatPolicy = (message: string, token: string, history: HistoryMessage[] = []) =>
  post("/chat/policy", { message, history }, token);

export const chatSQL = (message: string, token: string, history: HistoryMessage[] = []) =>
  post("/chat/sql", { message, history }, token);

export const chatActions = (message: string, token: string, history: HistoryMessage[] = [], confirmed = false) =>
  post("/chat/actions", { message, history, confirmed }, token);

export const chatRouter = (message: string, token: string, history: HistoryMessage[] = []) =>
  post("/chat/router", { message, history }, token);

export const chatLangGraph = (message: string, token: string, history: HistoryMessage[] = []) =>
  post("/chat/langgraph", { message, history }, token);

export const chatHrData = (message: string, token: string, history: HistoryMessage[] = []) =>
  post("/chat/hr-data", { message, history }, token);

// Chat — Streamable HTTP / NDJSON streaming (router/stream)
export type StreamEvent =
  | { type: "status"; message: string }
  | { type: "result"; route: unknown; result: unknown }
  | { type: "error"; message: string }
  | { type: "done" };

// ── Leaves API ───────────────────────────────────────────────────────────────

export interface LeaveRequest {
  id: number;
  employee_id: number;
  employee_name?: string;
  leave_type: string;
  start_date: string;
  end_date: string;
  reason: string | null;
  status: string;
  created_at: string;
}

// ── Announcements API ─────────────────────────────────────────────────────────

export interface Announcement {
  id: number;
  title: string;
  content: string;
  category: string;
  is_pinned: boolean;
  created_by_id: number;
  created_at: string;
}

export const announcementsApi = {
  list: (token: string, limit = 50) =>
    request<{ success: boolean; data: Announcement[] }>(`/announcements?limit=${limit}`, { method: "GET" }, token),
};

// ── Tickets API ───────────────────────────────────────────────────────────────

export interface Ticket {
  id: number;
  title: string;
  status: string;
  priority: string;
  category: string;
  created_by_id: number;
  assigned_to_id: number | null;
  created_at: string;
}

export const ticketsApi = {
  list: (token: string, limit = 50) =>
    request<{ success: boolean; data: Ticket[] }>(`/tickets?limit=${limit}`, { method: "GET" }, token),
};

// ── Projects API ──────────────────────────────────────────────────────────────

export interface ProjectItem {
  id?: number;
  project_id?: number;
  name?: string;
  project_name?: string;
  description?: string;
  status?: string;
  start_date?: string | null;
  end_date?: string | null;
  role?: string;
  assigned_at?: string;
  created_at?: string;
}

export const projectsApi = {
  myProjects: (token: string) =>
    request<{ success: boolean; data: ProjectItem[] }>("/projects/my", { method: "GET" }, token),
  list: (token: string) =>
    request<{ success: boolean; data: ProjectItem[] }>("/projects", { method: "GET" }, token),
};

export const leavesApi = {
  myLeaves: (token: string) =>
    request<{ success: boolean; data: LeaveRequest[] }>("/leaves/requests/my", { method: "GET" }, token),

  pendingApprovals: (token: string) =>
    request<{ success: boolean; data: LeaveRequest[] }>("/leaves/requests/pending", { method: "GET" }, token),

  approve: (token: string, requestId: number) =>
    request<{ success: boolean; data: unknown }>(`/leaves/requests/${requestId}`, {
      method: "PATCH",
      body: JSON.stringify({ action: "approve" }),
    }, token),

  reject: (token: string, requestId: number) =>
    request<{ success: boolean; data: unknown }>(`/leaves/requests/${requestId}`, {
      method: "PATCH",
      body: JSON.stringify({ action: "reject" }),
    }, token),
};

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
  onEvent: (event: StreamEvent) => void,
  history: HistoryMessage[] = [],
): Promise<void> {
  const res = await fetch(`${BASE}/chat/router/stream`, {
    method: "POST",
    headers: authHeaders(token),
    body: JSON.stringify({ message, history }),
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
          const event = JSON.parse(trimmed) as StreamEvent;
          onEvent(event);
        } catch {
          // skip malformed
        }
      }
    }
  }
}
