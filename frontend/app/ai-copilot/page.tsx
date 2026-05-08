"use client";

import { useState } from "react";
import { ChatPanel } from "@/components/ai/ChatPanel";
import { login } from "@/lib/api";

type Mode = "router" | "policy" | "sql" | "actions" | "langgraph";

const MODES: { id: Mode; label: string; description: string }[] = [
  { id: "router", label: "Smart Copilot", description: "Auto-routes to the right assistant" },
  { id: "policy", label: "HR Policy", description: "Answer HR policy questions" },
  { id: "sql", label: "People & Data", description: "Query employees, projects, skills" },
  { id: "actions", label: "HR Tasks", description: "Apply leave, create tickets, and more" },
  { id: "langgraph", label: "LangGraph", description: "Multi-agent graph orchestration" },
];

export default function AICopilotPage() {
  const [token, setToken] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loginError, setLoginError] = useState("");
  const [loggingIn, setLoggingIn] = useState(false);
  const [mode, setMode] = useState<Mode>("router");
  const [userName, setUserName] = useState("");
  const [userRole, setUserRole] = useState("");

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoggingIn(true);
    setLoginError("");
    try {
      const resp = await login(email, password);
      if (resp.success) {
        setToken(resp.data.access_token);
        setUserName(resp.data.name);
        setUserRole(resp.data.role);
      } else {
        setLoginError(resp.error ?? "Login failed");
      }
    } catch {
      setLoginError("Network error. Is the backend running?");
    } finally {
      setLoggingIn(false);
    }
  }

  if (!token) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-8 w-full max-w-sm">
          <h1 className="text-xl font-bold text-gray-900 mb-1">NovaWorks HR Copilot</h1>
          <p className="text-sm text-gray-500 mb-6">Sign in to continue</p>
          <form onSubmit={handleLogin} className="space-y-4">
            <input
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              type="email" placeholder="Email" value={email}
              onChange={(e) => setEmail(e.target.value)} required
            />
            <input
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              type="password" placeholder="Password" value={password}
              onChange={(e) => setPassword(e.target.value)} required
            />
            {loginError && <p className="text-xs text-red-600">{loginError}</p>}
            <button
              type="submit" disabled={loggingIn}
              className="w-full bg-blue-600 text-white rounded-lg py-2 text-sm font-medium hover:bg-blue-700 disabled:opacity-50 transition-colors"
            >
              {loggingIn ? "Signing in…" : "Sign In"}
            </button>
          </form>
          <div className="mt-4 text-xs text-gray-400 space-y-1">
            <p>Demo accounts:</p>
            <p>priya.sharma@novaworks.in / Admin@1234</p>
            <p>arjun.mehta@novaworks.in / Manager@1234</p>
            <p>rahul.verma@novaworks.in / Employee@1234</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50 flex flex-col">
      {/* Header */}
      <header className="bg-white border-b border-gray-200 px-6 py-3 flex items-center justify-between">
        <div>
          <h1 className="text-base font-bold text-gray-900">NovaWorks HR Copilot</h1>
          <p className="text-xs text-gray-500">{userName} · <span className="uppercase">{userRole}</span></p>
        </div>
        <button
          onClick={() => { setToken(""); setUserName(""); setUserRole(""); }}
          className="text-xs text-gray-400 hover:text-gray-600"
        >
          Sign out
        </button>
      </header>

      <div className="flex flex-1 overflow-hidden">
        {/* Mode sidebar */}
        <nav className="w-56 bg-white border-r border-gray-200 p-3 flex flex-col gap-1 shrink-0">
          {MODES.map((m) => (
            <button
              key={m.id}
              onClick={() => setMode(m.id)}
              className={`rounded-lg px-3 py-2.5 text-left transition-colors ${
                mode === m.id
                  ? "bg-blue-50 text-blue-700 border border-blue-200"
                  : "text-gray-700 hover:bg-gray-50"
              }`}
            >
              <p className="text-sm font-medium">{m.label}</p>
              <p className="text-xs text-gray-500 mt-0.5">{m.description}</p>
            </button>
          ))}
        </nav>

        {/* Chat area */}
        <main className="flex-1 flex flex-col overflow-hidden">
          <div className="px-4 py-2 bg-white border-b border-gray-100">
            <p className="text-xs text-gray-500">
              Mode: <span className="font-medium text-gray-700">{MODES.find((m) => m.id === mode)?.label}</span>
              {" — "}{MODES.find((m) => m.id === mode)?.description}
            </p>
          </div>
          <ChatPanel key={mode} token={token} mode={mode} />
        </main>
      </div>
    </div>
  );
}
