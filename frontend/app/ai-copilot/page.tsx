"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Bot, Zap, FileText, Database, ListTodo, Users,
  LogOut, ChevronRight, Settings, Calendar, ClipboardCheck,
} from "lucide-react";
import { ChatPanel } from "@/components/ai/ChatPanel";
import { PendingApprovals } from "@/components/ai/PendingApprovals";
import { MyLeaves } from "@/components/ai/MyLeaves";
import { getToken, getUser, clearAuth } from "@/lib/auth";

type Mode = "router" | "policy" | "sql" | "actions" | "hr-data" | "my-leaves" | "pending-approvals";

const MANAGER_ROLES = new Set(["MANAGER", "HR", "ADMIN", "C_LEVEL"]);

const ALL_MODES: { id: Mode; label: string; description: string; icon: React.ElementType; managerOnly?: boolean }[] = [
  { id: "router",             label: "Smart Copilot",       description: "Auto-routes to the right assistant",       icon: Zap },
  { id: "policy",             label: "HR Policy",           description: "Answer HR policy questions",               icon: FileText },
  { id: "sql",                label: "People & Data",       description: "Query employees, projects, skills",        icon: Database },
  { id: "actions",            label: "HR Tasks",            description: "Apply leave, create tickets, and more",    icon: ListTodo },
  { id: "hr-data",            label: "HR Employee Data",    description: "Semantic search over employee records",    icon: Users },
  { id: "my-leaves",          label: "My Leaves",           description: "View your leave history and status",       icon: Calendar },
  { id: "pending-approvals",  label: "Pending Approvals",   description: "Approve or reject team leave requests",    icon: ClipboardCheck, managerOnly: true },
];

const ROLE_COLORS: Record<string, string> = {
  ADMIN:     "bg-violet-100 text-violet-700",
  MANAGER:   "bg-blue-100 text-blue-700",
  EMPLOYEE:  "bg-emerald-100 text-emerald-700",
  HR:        "bg-pink-100 text-pink-700",
  MARKETING: "bg-orange-100 text-orange-700",
  C_LEVEL:   "bg-purple-100 text-purple-700",
};

const CHAT_MODES = new Set(["router", "policy", "sql", "actions", "hr-data"]);

export default function AICopilotPage() {
  const router = useRouter();
  const [token, setToken]     = useState<string | null>(null);
  const [mode, setMode]       = useState<Mode>("router");
  const [userName, setUserName] = useState("");
  const [userRole, setUserRole] = useState("");
  const [ready, setReady]     = useState(false);

  useEffect(() => {
    const t = getToken();
    const u = getUser();
    if (!t || !u) {
      router.replace("/login");
      return;
    }
    setToken(t);
    setUserName(u.name);
    setUserRole(u.role);
    setReady(true);
  }, [router]);

  function handleSignOut() {
    clearAuth();
    router.replace("/login");
  }

  if (!ready) return null;

  const isManager = MANAGER_ROLES.has(userRole);
  const MODES = ALL_MODES.filter((m) => !m.managerOnly || isManager);
  const activeMode = MODES.find((m) => m.id === mode) ?? MODES[0];

  return (
    <div className="flex h-screen overflow-hidden bg-slate-50">
      {/* ── Sidebar ───────────────────────────────────────────────────────── */}
      <aside className="flex h-full w-60 shrink-0 flex-col bg-sidebar">
        {/* Logo */}
        <div className="flex items-center gap-2.5 px-4 py-5">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-brand">
            <Bot className="h-4 w-4 text-white" />
          </div>
          <div>
            <p className="text-sm font-semibold text-sidebar-fg">HR Copilot</p>
            <p className="text-xs text-slate-500">NovaWorks</p>
          </div>
        </div>

        <div className="mx-4 h-px bg-white/10" />

        {/* Nav modes */}
        <nav className="flex-1 overflow-y-auto px-2 py-3 space-y-0.5 scrollbar-thin">
          {MODES.map(({ id, label, description, icon: Icon }) => {
            const active = mode === id;
            return (
              <button
                key={id}
                onClick={() => setMode(id)}
                className={`group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors ${
                  active
                    ? "bg-brand text-white"
                    : "text-slate-400 hover:bg-white/10 hover:text-slate-200"
                }`}
              >
                <Icon className={`h-4 w-4 shrink-0 ${active ? "text-white" : "text-slate-500 group-hover:text-slate-300"}`} />
                <div className="min-w-0">
                  <p className={`text-sm font-medium truncate ${active ? "text-white" : ""}`}>{label}</p>
                  <p className={`text-xs truncate mt-0.5 ${active ? "text-white/70" : "text-slate-600"}`}>{description}</p>
                </div>
                {active && <ChevronRight className="ml-auto h-3.5 w-3.5 shrink-0 text-white/60" />}
              </button>
            );
          })}
        </nav>

        {userRole === "ADMIN" && (
          <>
            <div className="mx-4 h-px bg-white/10" />
            <div className="px-2 py-2">
              <a
                href="/admin"
                className="group flex w-full items-center gap-3 rounded-lg px-3 py-2.5 text-left transition-colors text-slate-400 hover:bg-white/10 hover:text-slate-200"
              >
                <Settings className="h-4 w-4 shrink-0 text-slate-500 group-hover:text-slate-300" />
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">Admin Panel</p>
                  <p className="text-xs truncate mt-0.5 text-slate-600">Users, docs &amp; access control</p>
                </div>
              </a>
            </div>
          </>
        )}

        <div className="mx-4 h-px bg-white/10" />

        {/* User info + logout */}
        <div className="px-3 py-4 flex items-center gap-3">
          <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand/20 text-sm font-semibold text-brand-light">
            {userName.charAt(0).toUpperCase()}
          </div>
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium text-slate-200 truncate">{userName}</p>
            <span className={`inline-block text-xs px-1.5 py-0.5 rounded font-medium mt-0.5 ${ROLE_COLORS[userRole] ?? "bg-slate-100 text-slate-600"}`}>
              {userRole}
            </span>
          </div>
          <button
            onClick={handleSignOut}
            title="Sign out"
            className="shrink-0 text-slate-600 hover:text-slate-300 transition-colors"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </aside>

      {/* ── Main area ─────────────────────────────────────────────────────── */}
      <main className="flex flex-1 flex-col overflow-hidden">
        {/* Mode header bar */}
        <header className="flex items-center gap-3 border-b border-slate-200 bg-white px-6 py-3">
          <activeMode.icon className="h-4 w-4 text-brand shrink-0" />
          <div>
            <p className="text-sm font-semibold text-slate-800">{activeMode.label}</p>
            <p className="text-xs text-slate-500">{activeMode.description}</p>
          </div>
        </header>

        {/* Route to correct panel */}
        {CHAT_MODES.has(mode) && (
          <ChatPanel key={mode} token={token!} mode={mode as Parameters<typeof ChatPanel>[0]["mode"]} />
        )}
        {mode === "my-leaves" && <MyLeaves token={token!} />}
        {mode === "pending-approvals" && <PendingApprovals token={token!} />}
      </main>
    </div>
  );
}
