"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { Bot, Zap, Shield, FileText } from "lucide-react";
import { login } from "@/lib/api";
import { saveAuth, isAuthenticated } from "@/lib/auth";

const DEMO_ACCOUNTS = [
  {
    label: "priya.sharma",
    role: "admin",
    email: "priya.sharma@novaworks.in",
    password: "Admin@1234",
    color: "bg-violet-50 text-violet-700 border-violet-200",
  },
  {
    label: "arjun.mehta",
    role: "manager",
    email: "arjun.mehta@novaworks.in",
    password: "Manager@1234",
    color: "bg-blue-50 text-blue-700 border-blue-200",
  },
  {
    label: "rahul.verma",
    role: "employee",
    email: "rahul.verma@novaworks.in",
    password: "Employee@1234",
    color: "bg-emerald-50 text-emerald-700 border-emerald-200",
  },
  {
    label: "kavya.sundaramoorthy",
    role: "c-level",
    email: "kavya.sundaramoorthy@novaworks.in",
    password: "CLevel@1234",
    color: "bg-purple-50 text-purple-700 border-purple-200",
  },
];

const FEATURES = [
  {
    icon: Zap,
    title: "Instant answers",
    description: "Natural language queries across all HR documents and data",
  },
  {
    icon: Shield,
    title: "Role-based access",
    description: "Strict RBAC ensures you only see what you're authorised for",
  },
  {
    icon: FileText,
    title: "Cited responses",
    description: "Every answer references the source document and section",
  },
];

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (isAuthenticated()) router.replace("/ai-copilot");
  }, [router]);

  async function handleLogin(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      const resp = await login(email, password);
      if (resp.success) {
        saveAuth(resp.data.access_token, {
          name: resp.data.name,
          role: resp.data.role,
          user_id: resp.data.user_id,
        });
        router.replace("/ai-copilot");
      } else {
        setError(resp.error ?? "Invalid username or password.");
      }
    } catch {
      setError("Network error. Is the backend running?");
    } finally {
      setLoading(false);
    }
  }

  function fillDemo(acc: (typeof DEMO_ACCOUNTS)[number]) {
    setEmail(acc.email);
    setPassword(acc.password);
    setError("");
  }

  return (
    <div className="min-h-screen flex">
      {/* ── Left panel ──────────────────────────────────────────────────── */}
      <div className="hidden lg:flex lg:w-1/2 bg-sidebar flex-col justify-between p-12">
        {/* Logo */}
        <div className="flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-brand">
            <Bot className="h-5 w-5 text-white" />
          </div>
          <span className="text-lg font-semibold text-sidebar-fg">HR Copilot</span>
        </div>

        {/* Hero */}
        <div className="space-y-8">
          <div>
            <h1 className="text-4xl font-bold text-white leading-tight">
              Your intelligent<br />HR assistant
            </h1>
            <p className="mt-4 text-slate-400 text-base leading-relaxed">
              Ask questions, get cited answers — with access controls that keep
              sensitive information safe.
            </p>
          </div>

          <div className="space-y-4">
            {FEATURES.map(({ icon: Icon, title, description }) => (
              <div key={title} className="flex items-start gap-4">
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white/10">
                  <Icon className="h-4 w-4 text-slate-300" />
                </div>
                <div>
                  <p className="text-sm font-medium text-white">{title}</p>
                  <p className="text-xs text-slate-400 mt-0.5">{description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        <p className="text-xs text-slate-600">© 2025 NovaWorks Technologies</p>
      </div>

      {/* ── Right panel ─────────────────────────────────────────────────── */}
      <div className="flex-1 flex items-center justify-center p-8 bg-slate-50">
        <div className="w-full max-w-md bg-white rounded-2xl shadow-sm border border-slate-200 p-8">
          <h2 className="text-2xl font-bold text-slate-900">Sign in</h2>
          <p className="mt-1 text-sm text-slate-500">Access your NovaWorks HR knowledge base</p>

          {error && (
            <div className="mt-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-600">
              {error}
            </div>
          )}

          <form onSubmit={handleLogin} className="mt-6 space-y-4">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Email</label>
              <input
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
                autoComplete="email"
                placeholder="you@novaworks.in"
                className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm placeholder:text-slate-400 focus:outline-none focus:ring-2 focus:ring-brand/40 focus:border-brand"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-1">Password</label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                autoComplete="current-password"
                placeholder="••••••••"
                className="w-full rounded-lg border border-slate-300 px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-brand/40 focus:border-brand"
              />
            </div>
            <button
              type="submit"
              disabled={loading}
              className="w-full rounded-lg bg-brand py-2.5 text-sm font-semibold text-white hover:bg-brand-dark disabled:opacity-60 transition-colors"
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>

          {/* Demo accounts */}
          <div className="mt-6">
            <p className="text-xs font-medium text-slate-400 tracking-wider uppercase mb-3">
              Quick Access — Demo Accounts
            </p>
            <div className="flex flex-wrap gap-2">
              {DEMO_ACCOUNTS.map((acc) => (
                <button
                  key={acc.email}
                  type="button"
                  onClick={() => fillDemo(acc)}
                  className={`rounded-full border px-3 py-1 text-xs font-medium transition-opacity hover:opacity-80 ${acc.color}`}
                >
                  {acc.label}
                  <span className="ml-1.5 opacity-60">· {acc.role}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
