"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Trash2, Pencil } from "lucide-react";
import { admin, AdminUser, AdminRole, AdminCategory, AdminPolicy, AdminPolicyGroup } from "@/lib/api";
import { getToken, getUser, clearAuth } from "@/lib/auth";

type Tab = "users" | "documents" | "access";

const POLICY_CATEGORIES = ["LEAVE", "ATTENDANCE", "CODE_OF_CONDUCT", "BENEFITS", "COMPENSATION", "IT", "GENERAL"];
const ROLES = ["EMPLOYEE", "MANAGER", "ADMIN", "HR", "MARKETING", "C_LEVEL"];
const EMPLOYMENT_TYPES = ["FULL_TIME", "PART_TIME", "CONTRACT"];

// ── tiny helpers ──────────────────────────────────────────────────────────────

function Badge({ value, type }: { value: string; type: "role" | "category" }) {
  const roleColors: Record<string, string> = {
    ADMIN: "bg-red-100 text-red-700",
    MANAGER: "bg-blue-100 text-blue-700",
    EMPLOYEE: "bg-green-100 text-green-700",
    HR: "bg-violet-100 text-violet-700",
    MARKETING: "bg-pink-100 text-pink-700",
    C_LEVEL: "bg-yellow-100 text-yellow-800",
  };
  const catColors: Record<string, string> = {
    LEAVE: "bg-amber-100 text-amber-700",
    ATTENDANCE: "bg-orange-100 text-orange-700",
    CODE_OF_CONDUCT: "bg-purple-100 text-purple-700",
    BENEFITS: "bg-teal-100 text-teal-700",
    COMPENSATION: "bg-emerald-100 text-emerald-700",
    IT: "bg-sky-100 text-sky-700",
    GENERAL: "bg-slate-100 text-slate-700",
  };
  const color = type === "role" ? (roleColors[value] ?? "bg-gray-100 text-gray-600") : (catColors[value] ?? "bg-gray-100 text-gray-600");
  return <span className={`text-xs px-2 py-0.5 rounded-full font-medium ${color}`}>{value.replace(/_/g, " ")}</span>;
}

function Toast({ msg, ok }: { msg: string; ok: boolean }) {
  return (
    <div className={`fixed bottom-4 right-4 z-50 px-4 py-2 rounded-lg text-sm font-medium shadow-lg ${ok ? "bg-green-600 text-white" : "bg-red-600 text-white"}`}>
      {msg}
    </div>
  );
}

// ── main component ────────────────────────────────────────────────────────────

export default function AdminPage() {
  const router = useRouter();
  const [token, setToken] = useState("");
  const [myRole, setMyRole] = useState("");

  // tab + loading
  const [tab, setTab] = useState<Tab>("users");
  const [loading, setLoading] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);

  // data
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [roles, setRoles] = useState<AdminRole[]>([]);
  const [categories, setCategories] = useState<AdminCategory[]>([]);
  const [policies, setPolicies] = useState<AdminPolicy[]>([]);

  // create user form
  const [showCreateUser, setShowCreateUser] = useState(false);
  const [newUser, setNewUser] = useState({ employee_code: "", name: "", email: "", password: "", role: "EMPLOYEE", employment_type: "FULL_TIME", job_title: "" });
  const [creating, setCreating] = useState(false);

  // edit user
  const [editUserId, setEditUserId] = useState<number | null>(null);
  const [editUserFields, setEditUserFields] = useState<{ name: string; role: string; status: string; policy_group: string | null }>({ name: "", role: "", status: "", policy_group: null });
  const [savingUser, setSavingUser] = useState(false);

  // policy list filter
  const [showInactivePolcies, setShowInactivePolicies] = useState(false);

  // policy upload
  const [showUpload, setShowUpload] = useState(false);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadCategory, setUploadCategory] = useState("LEAVE");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  // policy groups
  const [policyGroups, setPolicyGroups] = useState<AdminPolicyGroup[]>([]);
  const [showNewGroup, setShowNewGroup] = useState(false);
  const [newGroupName, setNewGroupName] = useState("");
  const [newGroupCats, setNewGroupCats] = useState<string[]>([]);
  const [creatingGroup, setCreatingGroup] = useState(false);
  const [editingGroup, setEditingGroup] = useState<string | null>(null);
  const [editGroupCats, setEditGroupCats] = useState<string[]>([]);
  const [savingGroup, setSavingGroup] = useState(false);

  // role / category editing
  const [editingRole, setEditingRole] = useState<string | null>(null);
  const [editRoleCats, setEditRoleCats] = useState<string[]>([]);
  const [savingRole, setSavingRole] = useState(false);
  const [editingCat, setEditingCat] = useState<string | null>(null);
  const [editCatRoles, setEditCatRoles] = useState<string[]>([]);
  const [savingCat, setSavingCat] = useState(false);

  function showToast(msg: string, ok: boolean) {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3000);
  }

  // ── auth gate ──────────────────────────────────────────────────────────────

  useEffect(() => {
    const t = getToken();
    const u = getUser();
    if (!t || !u) { router.replace("/login"); return; }
    if (u.role !== "ADMIN") { router.replace("/ai-copilot"); return; }
    setToken(t);
    setMyRole(u.role);
  }, [router]);

  // ── data loading ───────────────────────────────────────────────────────────

  useEffect(() => {
    if (!token) return;
    loadAll();
  }, [token]);

  async function loadAll() {
    setLoading(true);
    try {
      const [u, r, c, p, g] = await Promise.all([
        admin.listUsers(token),
        admin.listRoles(token),
        admin.listCategories(token),
        admin.listPolicies(token),
        admin.listPolicyGroups(token),
      ]);
      if (u.status === 200) setUsers(u.data);
      if (r.status === 200) setRoles(r.data);
      if (c.status === 200) setCategories(c.data);
      if (p.status === 200) setPolicies(p.data);
      if (g.status === 200) setPolicyGroups(g.data);
    } finally {
      setLoading(false);
    }
  }

  // ── user actions ───────────────────────────────────────────────────────────

  async function handleCreateUser(e: React.FormEvent) {
    e.preventDefault();
    setCreating(true);
    try {
      const res = await admin.createUser(token, {
        employee_code: newUser.employee_code,
        name: newUser.name,
        email: newUser.email,
        password: newUser.password,
        role: newUser.role,
        employment_type: newUser.employment_type,
        job_title: newUser.job_title || undefined,
      });
      if (res.status === 201) {
        setUsers(prev => [...prev, res.data]);
        setShowCreateUser(false);
        setNewUser({ employee_code: "", name: "", email: "", password: "", role: "EMPLOYEE", employment_type: "FULL_TIME", job_title: "" });
        showToast("User created", true);
      } else {
        showToast((res.data as { detail?: string })?.detail ?? "Failed to create user", false);
      }
    } finally {
      setCreating(false);
    }
  }

  async function handleUpdateUser() {
    if (!editUserId) return;
    setSavingUser(true);
    try {
      const res = await admin.updateUser(token, editUserId, {
        name: editUserFields.name,
        role: editUserFields.role as AdminUser["role"],
        status: editUserFields.status as AdminUser["status"],
        policy_group: editUserFields.policy_group,
      });
      if (res.status === 200) {
        setUsers(prev => prev.map(u => u.id === editUserId ? res.data : u));
        setEditUserId(null);
        showToast("User updated", true);
      } else {
        showToast((res.data as { detail?: string })?.detail ?? "Update failed", false);
      }
    } finally {
      setSavingUser(false);
    }
  }

  async function handleDeleteUser(id: number) {
    if (!confirm("Delete this user?")) return;
    const res = await admin.deleteUser(token, id);
    if (res.status === 204) {
      setUsers(prev => prev.filter(u => u.id !== id));
      showToast("User deleted", true);
    } else {
      showToast("Delete failed", false);
    }
  }

  // ── policy actions ─────────────────────────────────────────────────────────

  async function handleUpload(e: React.FormEvent) {
    e.preventDefault();
    if (!uploadFile) return;
    setUploading(true);
    try {
      const res = await admin.uploadPolicy(token, uploadTitle, uploadCategory, uploadFile);
      if (res.status === 201) {
        showToast(`"${uploadFile.name}" queued for ingestion`, true);
        setShowUpload(false);
        setUploadTitle("");
        setUploadFile(null);
        if (fileRef.current) fileRef.current.value = "";
        const p = await admin.listPolicies(token);
        if (p.status === 200) setPolicies(p.data);
      } else {
        showToast((res.data as { detail?: string })?.detail ?? "Upload failed", false);
      }
    } finally {
      setUploading(false);
    }
  }

  async function handleDeletePolicy(id: number, title: string) {
    if (!confirm(`Delete "${title}"? This permanently removes it from the database and all vector embeddings.`)) return;
    const res = await admin.deletePolicy(token, id);
    if (res.status === 204) {
      setPolicies(prev => prev.filter(p => p.id !== id));
      showToast("Policy deleted and embeddings purged", true);
    } else {
      const detail = (res.data as unknown as { detail?: string })?.detail ?? "Delete failed";
      showToast(detail, false);
    }
  }

  async function handleReingest() {
    await admin.reingestPolicies(token);
    showToast("Re-ingestion started", true);
    const p = await admin.listPolicies(token);
    if (p.status === 200) setPolicies(p.data);
  }

  // ── role actions ───────────────────────────────────────────────────────────

  async function handleUpdateRole() {
    if (!editingRole) return;
    setSavingRole(true);
    try {
      const res = await admin.updateRole(token, editingRole, editRoleCats);
      if (res.status === 200) {
        setRoles(prev => prev.map(r => r.name === editingRole ? res.data : r));
        setEditingRole(null);
        showToast("Role access updated", true);
      } else {
        showToast("Update failed", false);
      }
    } finally {
      setSavingRole(false);
    }
  }

  async function handleUpdateCategory() {
    if (!editingCat) return;
    setSavingCat(true);
    try {
      const res = await admin.updateCategory(token, editingCat, editCatRoles);
      if (res.status === 200) {
        setCategories(prev => prev.map(c => c.name === editingCat ? res.data : c));
        setEditingCat(null);
        showToast("Category access updated", true);
      } else {
        showToast("Update failed", false);
      }
    } finally {
      setSavingCat(false);
    }
  }

  function toggleItem(list: string[], item: string, setter: (v: string[]) => void) {
    setter(list.includes(item) ? list.filter(x => x !== item) : [...list, item]);
  }

  async function handleCreateGroup(e: React.FormEvent) {
    e.preventDefault();
    const name = newGroupName.trim();
    if (!name) return;
    setCreatingGroup(true);
    try {
      const res = await admin.createPolicyGroup(token, name, newGroupCats);
      if (res.status === 201) {
        setPolicyGroups(prev => [...prev, res.data]);
        setShowNewGroup(false);
        setNewGroupName("");
        setNewGroupCats([]);
        showToast(`Group "${res.data.name}" created`, true);
      } else {
        showToast((res.data as unknown as { detail?: string })?.detail ?? "Create failed", false);
      }
    } finally {
      setCreatingGroup(false);
    }
  }

  async function handleUpdateGroup() {
    if (!editingGroup) return;
    setSavingGroup(true);
    try {
      const res = await admin.updatePolicyGroup(token, editingGroup, editGroupCats);
      if (res.status === 200) {
        setPolicyGroups(prev => prev.map(g => g.name === editingGroup ? res.data : g));
        setEditingGroup(null);
        showToast("Group access updated", true);
      } else {
        showToast("Update failed", false);
      }
    } finally {
      setSavingGroup(false);
    }
  }

  async function handleDeleteGroup(name: string) {
    if (!confirm(`Delete group "${name}"? Users assigned to this group will fall back to their system role access.`)) return;
    const res = await admin.deletePolicyGroup(token, name);
    if (res.status === 204) {
      setPolicyGroups(prev => prev.filter(g => g.name !== name));
      setUsers(prev => prev.map(u => u.policy_group === name ? { ...u, policy_group: null } : u));
      showToast(`Group "${name}" deleted`, true);
    } else {
      showToast("Delete failed", false);
    }
  }

  if (!token) return null; // redirecting

  // ── main UI ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-gray-50">
      {toast && <Toast msg={toast.msg} ok={toast.ok} />}

      {/* Header */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand">
            <span className="text-xs font-bold text-white">A</span>
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-900">NovaWorks Admin Portal</h1>
            <p className="text-xs text-slate-500">User management, policies &amp; access control</p>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <Badge value={myRole} type="role" />
          <a href="/ai-copilot" className="text-xs text-brand hover:text-brand-dark font-medium">← Copilot</a>
          <button onClick={() => { clearAuth(); router.replace("/login"); }} className="text-xs text-slate-400 hover:text-slate-600">Sign out</button>
        </div>
      </header>

      {/* Tabs */}
      <div className="bg-white border-b border-slate-200 px-6">
        <div className="flex gap-1">
          {(["users", "documents", "access"] as Tab[]).map(t => (
            <button key={t} onClick={() => setTab(t)}
              className={`px-4 py-3 text-sm font-medium capitalize border-b-2 transition ${tab === t ? "border-brand text-brand" : "border-transparent text-slate-500 hover:text-slate-700"}`}>
              {t === "access" ? "Access Control" : t}
              {t === "documents" && <span className="ml-1.5 text-xs bg-slate-100 text-slate-500 rounded-full px-1.5 py-0.5">{policies.length}</span>}
            </button>
          ))}
        </div>
      </div>

      <main className="px-6 py-6 max-w-5xl mx-auto">
        {loading ? (
          <div className="text-center text-gray-400 py-20 text-sm">Loading…</div>
        ) : tab === "users" ? (

          /* ── Users tab ─────────────────────────────────────────── */
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-semibold text-gray-900">User Management</h2>
                <p className="text-xs text-gray-400 mt-0.5">Create, edit, and remove employee accounts</p>
              </div>
              <button onClick={() => setShowCreateUser(v => !v)}
                className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-3 py-2 rounded-lg transition">
                {showCreateUser ? "Cancel" : "+ New User"}
              </button>
            </div>

            {showCreateUser && (
              <form onSubmit={handleCreateUser} className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm space-y-4">
                <p className="font-medium text-gray-800 text-sm">Create New User</p>
                <div className="grid grid-cols-2 gap-3">
                  {[
                    { label: "Employee Code", key: "employee_code", type: "text", placeholder: "EMP010" },
                    { label: "Full Name", key: "name", type: "text", placeholder: "Jane Smith" },
                    { label: "Email", key: "email", type: "email", placeholder: "jane@company.com" },
                    { label: "Password", key: "password", type: "password", placeholder: "••••••••" },
                    { label: "Job Title", key: "job_title", type: "text", placeholder: "HR Manager" },
                  ].map(f => (
                    <div key={f.key}>
                      <label className="block text-xs font-medium text-gray-600 mb-1">{f.label}</label>
                      <input type={f.type} placeholder={f.placeholder} required={f.key !== "job_title"}
                        value={(newUser as Record<string, string>)[f.key]}
                        onChange={e => setNewUser(u => ({ ...u, [f.key]: e.target.value }))}
                        className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/30" />
                    </div>
                  ))}
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Role</label>
                    <select value={newUser.role} onChange={e => setNewUser(u => ({ ...u, role: e.target.value }))}
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/30 bg-white">
                      {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Employment Type</label>
                    <select value={newUser.employment_type} onChange={e => setNewUser(u => ({ ...u, employment_type: e.target.value }))}
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/30 bg-white">
                      {EMPLOYMENT_TYPES.map(t => <option key={t} value={t}>{t.replace("_", " ")}</option>)}
                    </select>
                  </div>
                </div>
                <div className="flex justify-end">
                  <button type="submit" disabled={creating}
                    className="bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-sm font-medium px-4 py-2 rounded-lg transition">
                    {creating ? "Creating…" : "Create User"}
                  </button>
                </div>
              </form>
            )}

            <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    {["Name", "Email", "Role", "Status", "Group", ""].map(h => (
                      <th key={h} className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {users.map(u => u.id === editUserId ? (
                    <tr key={u.id} className="bg-blue-50/40">
                      <td className="px-5 py-3">
                        <input value={editUserFields.name} onChange={e => setEditUserFields(f => ({ ...f, name: e.target.value }))}
                          className="w-full px-2 py-1.5 text-sm border border-gray-300 rounded-lg" />
                      </td>
                      <td className="px-5 py-3 text-gray-500 text-xs">{u.email}</td>
                      <td className="px-5 py-3">
                        <select value={editUserFields.role} onChange={e => setEditUserFields(f => ({ ...f, role: e.target.value }))}
                          className="px-2 py-1 text-sm border border-gray-300 rounded-lg bg-white">
                          {ROLES.map(r => <option key={r} value={r}>{r}</option>)}
                        </select>
                      </td>
                      <td className="px-5 py-3">
                        <select value={editUserFields.status} onChange={e => setEditUserFields(f => ({ ...f, status: e.target.value }))}
                          className="px-2 py-1 text-sm border border-gray-300 rounded-lg bg-white">
                          {["ACTIVE", "INACTIVE", "TERMINATED"].map(s => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </td>
                      <td className="px-5 py-3">
                        <select value={editUserFields.policy_group ?? ""} onChange={e => setEditUserFields(f => ({ ...f, policy_group: e.target.value || null }))}
                          className="px-2 py-1 text-sm border border-gray-300 rounded-lg bg-white">
                          <option value="">— system role —</option>
                          {policyGroups.map(g => <option key={g.name} value={g.name}>{g.name.replace(/_/g, " ")}</option>)}
                        </select>
                      </td>
                      <td className="px-5 py-3 text-right">
                        <div className="flex gap-2 justify-end">
                          <button onClick={handleUpdateUser} disabled={savingUser}
                            className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg disabled:opacity-60">
                            {savingUser ? "Saving…" : "Save"}
                          </button>
                          <button onClick={() => setEditUserId(null)}
                            className="text-xs text-gray-500 border border-gray-200 px-3 py-1.5 rounded-lg">Cancel</button>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    <tr key={u.id} className="hover:bg-gray-50 transition-colors">
                      <td className="px-5 py-3.5 font-medium text-gray-800">{u.name}</td>
                      <td className="px-5 py-3.5 text-gray-500 text-xs">{u.email}</td>
                      <td className="px-5 py-3.5"><Badge value={u.role} type="role" /></td>
                      <td className="px-5 py-3.5 text-xs text-gray-500">{u.status}</td>
                      <td className="px-5 py-3.5">
                        {u.policy_group
                          ? <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-indigo-100 text-indigo-700">{u.policy_group.replace(/_/g, " ")}</span>
                          : <span className="text-xs text-gray-400">—</span>}
                      </td>
                      <td className="px-5 py-3.5 text-right">
                        <div className="flex gap-1 justify-end">
                          <button onClick={() => { setEditUserId(u.id); setEditUserFields({ name: u.name, role: u.role, status: u.status, policy_group: u.policy_group }); }}
                            title="Edit user"
                            className="text-gray-400 hover:text-blue-600 p-1 rounded transition">
                            <Pencil className="w-4 h-4" />
                          </button>
                          <button onClick={() => handleDeleteUser(u.id)}
                            title="Delete user"
                            className="text-gray-400 hover:text-red-500 p-1 rounded transition">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

        ) : tab === "documents" ? (

          /* ── Documents tab ─────────────────────────────────────── */
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <div>
                <h2 className="font-semibold text-gray-900">Policy Documents</h2>
                <p className="text-xs text-gray-400 mt-0.5">
                  {policies.filter(p => p.is_active).length} active ·{" "}
                  {policies.filter(p => p.is_active && p.embeddings_generated_at).length} indexed
                </p>
              </div>
              <div className="flex gap-2">
                <button onClick={() => setShowInactivePolicies(v => !v)}
                  className="text-xs text-gray-500 border border-gray-200 bg-white px-3 py-2 rounded-lg hover:bg-gray-50 transition">
                  {showInactivePolcies ? "Hide deleted" : "Show all"}
                </button>
                <button onClick={() => setShowUpload(v => !v)}
                  className="flex items-center gap-1.5 text-gray-600 text-sm font-medium px-3 py-2 border border-gray-200 bg-white rounded-lg hover:bg-gray-50 transition">
                  {showUpload ? "Cancel" : "↑ Upload"}
                </button>
                <button onClick={handleReingest}
                  className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-3 py-2 rounded-lg transition">
                  ↺ Re-ingest All
                </button>
              </div>
            </div>

            {showUpload && (
              <form onSubmit={handleUpload} className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm space-y-4">
                <p className="font-medium text-gray-800 text-sm">Upload Policy Document</p>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Title</label>
                    <input type="text" placeholder="Leave Policy 2026" required value={uploadTitle}
                      onChange={e => setUploadTitle(e.target.value)}
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/30" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Category</label>
                    <select value={uploadCategory} onChange={e => setUploadCategory(e.target.value)}
                      className="w-full px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/30 bg-white">
                      {POLICY_CATEGORIES.map(c => <option key={c} value={c}>{c.replace(/_/g, " ")}</option>)}
                    </select>
                  </div>
                  <div className="col-span-2">
                    <label className="block text-xs font-medium text-gray-600 mb-1">
                      File <span className="text-gray-400 font-normal">(.md, .txt, .pdf)</span>
                    </label>
                    <input ref={fileRef} type="file" accept=".md,.txt,.pdf" required
                      onChange={e => setUploadFile(e.target.files?.[0] ?? null)}
                      className="w-full px-3 py-1.5 text-sm border border-gray-200 rounded-lg file:mr-2 file:text-xs file:font-medium file:border-0 file:bg-gray-100 file:text-gray-600 file:rounded file:px-2 file:py-1" />
                  </div>
                </div>
                <div className="flex justify-end">
                  <button type="submit" disabled={uploading || !uploadFile}
                    className="bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-sm font-medium px-4 py-2 rounded-lg transition">
                    {uploading ? "Uploading…" : "Upload & Ingest"}
                  </button>
                </div>
              </form>
            )}

            <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-gray-100 bg-gray-50">
                    {["Title", "Category", "File", "Status", "Created", ""].map(h => (
                      <th key={h} className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {policies.filter(p => showInactivePolcies || p.is_active).length === 0 ? (
                    <tr><td colSpan={6} className="px-5 py-8 text-center text-gray-400 text-xs">No policies. Upload one above or click Re-ingest All.</td></tr>
                  ) : policies.filter(p => showInactivePolcies || p.is_active).map(p => (
                    <tr key={p.id} className={`hover:bg-gray-50 transition-colors ${!p.is_active ? "opacity-40" : ""}`}>
                      <td className="px-5 py-3.5 font-medium text-gray-800 max-w-[200px] truncate">{p.title}</td>
                      <td className="px-5 py-3.5"><Badge value={p.category} type="category" /></td>
                      <td className="px-5 py-3.5 text-gray-400 text-xs">{p.filename ?? "—"}</td>
                      <td className="px-5 py-3.5">
                        {p.is_active
                          ? <span className={`text-xs font-medium ${p.embeddings_generated_at ? "text-green-600" : "text-amber-500"}`}>
                              {p.embeddings_generated_at ? "✓ Indexed" : "⏳ Pending"}
                            </span>
                          : <span className="text-xs text-gray-400">Inactive</span>}
                      </td>
                      <td className="px-5 py-3.5 text-gray-400 text-xs">{new Date(p.created_at).toLocaleDateString()}</td>
                      <td className="px-5 py-3.5 text-right">
                        {p.is_active && (
                          <button
                            onClick={() => handleDeletePolicy(p.id, p.title)}
                            title="Delete policy and purge embeddings"
                            className="text-gray-400 hover:text-red-500 transition-colors p-1 rounded"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

        ) : (

          /* ── Access Control tab ─────────────────────────────────── */
          <div className="space-y-10">

            {/* Roles section */}
            <div className="space-y-4">
              <div>
                <h2 className="font-semibold text-gray-900">Roles</h2>
                <p className="text-xs text-gray-400 mt-0.5">Control which policy categories each role can access</p>
              </div>
              <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 bg-gray-50">
                      <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-36">Role</th>
                      <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Accessible Categories</th>
                      <th className="px-5 py-3 w-24" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {roles.map(r => r.name === editingRole ? (
                      <tr key={r.name} className="bg-blue-50/40">
                        <td className="px-5 py-4"><Badge value={r.name} type="role" /></td>
                        <td className="px-5 py-4">
                          <div className="flex flex-wrap gap-3">
                            {POLICY_CATEGORIES.map(cat => (
                              <label key={cat} className="flex items-center gap-1.5 cursor-pointer text-xs">
                                <input type="checkbox" className="accent-blue-600"
                                  checked={editRoleCats.includes(cat)}
                                  onChange={() => toggleItem(editRoleCats, cat, setEditRoleCats)} />
                                <Badge value={cat} type="category" />
                              </label>
                            ))}
                          </div>
                        </td>
                        <td className="px-5 py-4 text-right">
                          <div className="flex gap-2 justify-end">
                            <button onClick={handleUpdateRole} disabled={savingRole}
                              className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg disabled:opacity-60">
                              {savingRole ? "Saving…" : "Save"}
                            </button>
                            <button onClick={() => setEditingRole(null)}
                              className="text-xs text-gray-500 border border-gray-200 px-3 py-1.5 rounded-lg">Cancel</button>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      <tr key={r.name} className="hover:bg-gray-50 transition-colors">
                        <td className="px-5 py-4"><Badge value={r.name} type="role" /></td>
                        <td className="px-5 py-4">
                          <div className="flex flex-wrap gap-1">
                            {r.accessible_categories.length === 0
                              ? <span className="text-xs text-gray-400 italic">none</span>
                              : r.accessible_categories.map(c => <Badge key={c} value={c} type="category" />)}
                          </div>
                        </td>
                        <td className="px-5 py-4 text-right">
                          <button onClick={() => { setEditingRole(r.name); setEditRoleCats([...r.accessible_categories]); }}
                            className="text-gray-400 hover:text-blue-600 text-xs transition">Edit</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Categories section */}
            <div className="space-y-4">
              <div>
                <h2 className="font-semibold text-gray-900">Categories</h2>
                <p className="text-xs text-gray-400 mt-0.5">Control which roles can access each policy category</p>
              </div>
              <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 bg-gray-50">
                      <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-44">Category</th>
                      <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Accessible By</th>
                      <th className="px-5 py-3 w-24" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {categories.map(c => c.name === editingCat ? (
                      <tr key={c.name} className="bg-blue-50/40">
                        <td className="px-5 py-4"><Badge value={c.name} type="category" /></td>
                        <td className="px-5 py-4">
                          <div className="flex gap-3">
                            {ROLES.map(role => (
                              <label key={role} className="flex items-center gap-1.5 cursor-pointer text-xs">
                                <input type="checkbox" className="accent-blue-600"
                                  checked={editCatRoles.includes(role)}
                                  onChange={() => toggleItem(editCatRoles, role, setEditCatRoles)} />
                                <Badge value={role} type="role" />
                              </label>
                            ))}
                          </div>
                        </td>
                        <td className="px-5 py-4 text-right">
                          <div className="flex gap-2 justify-end">
                            <button onClick={handleUpdateCategory} disabled={savingCat}
                              className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg disabled:opacity-60">
                              {savingCat ? "Saving…" : "Save"}
                            </button>
                            <button onClick={() => setEditingCat(null)}
                              className="text-xs text-gray-500 border border-gray-200 px-3 py-1.5 rounded-lg">Cancel</button>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      <tr key={c.name} className="hover:bg-gray-50 transition-colors">
                        <td className="px-5 py-4"><Badge value={c.name} type="category" /></td>
                        <td className="px-5 py-4">
                          <div className="flex flex-wrap gap-1">
                            {c.accessible_by_roles.length === 0
                              ? <span className="text-xs text-gray-400 italic">none</span>
                              : c.accessible_by_roles.map(r => <Badge key={r} value={r} type="role" />)}
                          </div>
                        </td>
                        <td className="px-5 py-4 text-right">
                          <button onClick={() => { setEditingCat(c.name); setEditCatRoles([...c.accessible_by_roles]); }}
                            className="text-gray-400 hover:text-blue-600 text-xs transition">Edit</button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

            {/* Policy Groups section */}
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="font-semibold text-gray-900">Policy Groups</h2>
                  <p className="text-xs text-gray-400 mt-0.5">Dynamic groups — override system role category access per user</p>
                </div>
                <button onClick={() => setShowNewGroup(v => !v)}
                  className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-700 text-white text-sm font-medium px-3 py-2 rounded-lg transition">
                  {showNewGroup ? "Cancel" : "+ New Group"}
                </button>
              </div>

              {showNewGroup && (
                <form onSubmit={handleCreateGroup} className="bg-white border border-gray-200 rounded-xl p-5 shadow-sm space-y-4">
                  <p className="font-medium text-gray-800 text-sm">Create Policy Group</p>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-1">Group name</label>
                    <input type="text" placeholder="e.g. c_level" required value={newGroupName}
                      onChange={e => setNewGroupName(e.target.value)}
                      className="w-full max-w-xs px-3 py-2 text-sm border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500/30" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-gray-600 mb-2">Categories this group can access</label>
                    <div className="flex flex-wrap gap-3">
                      {POLICY_CATEGORIES.map(cat => (
                        <label key={cat} className="flex items-center gap-1.5 cursor-pointer text-xs">
                          <input type="checkbox" className="accent-blue-600"
                            checked={newGroupCats.includes(cat)}
                            onChange={() => toggleItem(newGroupCats, cat, setNewGroupCats)} />
                          <Badge value={cat} type="category" />
                        </label>
                      ))}
                    </div>
                  </div>
                  <div className="flex justify-end">
                    <button type="submit" disabled={creatingGroup}
                      className="bg-blue-600 hover:bg-blue-700 disabled:opacity-60 text-white text-sm font-medium px-4 py-2 rounded-lg transition">
                      {creatingGroup ? "Creating…" : "Create Group"}
                    </button>
                  </div>
                </form>
              )}

              <div className="bg-white border border-gray-200 rounded-xl shadow-sm overflow-hidden">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="border-b border-gray-100 bg-gray-50">
                      <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider w-44">Group</th>
                      <th className="text-left px-5 py-3 text-xs font-semibold text-gray-500 uppercase tracking-wider">Accessible Categories</th>
                      <th className="px-5 py-3 w-24" />
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-gray-100">
                    {policyGroups.length === 0 ? (
                      <tr><td colSpan={3} className="px-5 py-8 text-center text-gray-400 text-xs">No groups. Create one above to override system-role access for specific users.</td></tr>
                    ) : policyGroups.map(g => g.name === editingGroup ? (
                      <tr key={g.name} className="bg-blue-50/40">
                        <td className="px-5 py-4">
                          <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-indigo-100 text-indigo-700">{g.name.replace(/_/g, " ")}</span>
                        </td>
                        <td className="px-5 py-4">
                          <div className="flex flex-wrap gap-3">
                            {POLICY_CATEGORIES.map(cat => (
                              <label key={cat} className="flex items-center gap-1.5 cursor-pointer text-xs">
                                <input type="checkbox" className="accent-blue-600"
                                  checked={editGroupCats.includes(cat)}
                                  onChange={() => toggleItem(editGroupCats, cat, setEditGroupCats)} />
                                <Badge value={cat} type="category" />
                              </label>
                            ))}
                          </div>
                        </td>
                        <td className="px-5 py-4 text-right">
                          <div className="flex gap-2 justify-end">
                            <button onClick={handleUpdateGroup} disabled={savingGroup}
                              className="text-xs bg-blue-600 text-white px-3 py-1.5 rounded-lg disabled:opacity-60">
                              {savingGroup ? "Saving…" : "Save"}
                            </button>
                            <button onClick={() => setEditingGroup(null)}
                              className="text-xs text-gray-500 border border-gray-200 px-3 py-1.5 rounded-lg">Cancel</button>
                          </div>
                        </td>
                      </tr>
                    ) : (
                      <tr key={g.name} className="hover:bg-gray-50 transition-colors">
                        <td className="px-5 py-4">
                          <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-indigo-100 text-indigo-700">{g.name.replace(/_/g, " ")}</span>
                        </td>
                        <td className="px-5 py-4">
                          <div className="flex flex-wrap gap-1">
                            {g.accessible_categories.length === 0
                              ? <span className="text-xs text-gray-400 italic">none</span>
                              : g.accessible_categories.map(c => <Badge key={c} value={c} type="category" />)}
                          </div>
                        </td>
                        <td className="px-5 py-4 text-right">
                          <div className="flex gap-1 justify-end">
                            <button onClick={() => { setEditingGroup(g.name); setEditGroupCats([...g.accessible_categories]); }}
                              className="text-gray-400 hover:text-blue-600 text-xs transition">Edit</button>
                            <button onClick={() => handleDeleteGroup(g.name)}
                              className="text-gray-400 hover:text-red-500 p-1 rounded transition">
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>

          </div>
        )}
      </main>
    </div>
  );
}
