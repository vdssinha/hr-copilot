"use client";

import { useEffect, useState, useCallback } from "react";
import { projectsApi, ProjectItem } from "@/lib/api";
import { RefreshCw, Loader2, FolderKanban } from "lucide-react";

interface MyProjectsProps {
  token: string;
  isManager: boolean;
}

const STATUS_COLORS: Record<string, string> = {
  PLANNING:  "bg-yellow-100 text-yellow-700",
  ONGOING:   "bg-blue-100 text-blue-700",
  COMPLETED: "bg-green-100 text-green-700",
  ON_HOLD:   "bg-gray-100 text-gray-500",
};

export function MyProjects({ token, isManager }: MyProjectsProps) {
  const [items, setItems] = useState<ProjectItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = isManager
        ? await projectsApi.list(token)
        : await projectsApi.myProjects(token);
      if (res.data?.success) {
        setItems(res.data.data ?? []);
      } else {
        setError("Failed to load projects.");
      }
    } catch {
      setError("Network error loading projects.");
    } finally {
      setLoading(false);
    }
  }, [token, isManager]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="flex flex-col h-full overflow-hidden bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
        <div>
          <h2 className="text-base font-semibold text-slate-800">
            {isManager ? "All Projects" : "My Projects"}
          </h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {loading ? "Loading…" : `${items.length} project${items.length !== 1 ? "s" : ""}`}
          </p>
        </div>
        <button
          onClick={load}
          disabled={loading}
          className="flex items-center gap-1.5 rounded-md border border-slate-200 px-3 py-1.5 text-xs text-slate-600 hover:bg-slate-50 disabled:opacity-50 transition-colors"
        >
          <RefreshCw className={`h-3 w-3 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-6 py-4">
        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
          </div>
        )}

        {!loading && error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</div>
        )}

        {!loading && !error && items.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400">
            <FolderKanban className="h-10 w-10 mb-3 text-slate-300" />
            <p className="text-sm font-medium">No projects</p>
          </div>
        )}

        {!loading && !error && items.length > 0 && (
          <div className="space-y-3">
            {items.map((p, i) => {
              const name = p.name ?? p.project_name ?? `Project #${p.id ?? p.project_id}`;
              const status = p.status;
              const role = p.role;
              const date = p.created_at ?? p.assigned_at;
              return (
                <div key={p.id ?? p.project_id ?? i} className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-slate-800 flex-1 truncate">{name}</span>
                    {status && (
                      <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${STATUS_COLORS[status] ?? "bg-slate-100 text-slate-600"}`}>
                        {status}
                      </span>
                    )}
                  </div>
                  {p.description && (
                    <p className="text-xs text-slate-500 mt-1 truncate">{p.description}</p>
                  )}
                  <div className="flex items-center gap-3 mt-1.5">
                    {role && <span className="text-xs text-slate-500">Role: {role}</span>}
                    {date && (
                      <span className="text-xs text-slate-400 ml-auto">
                        {new Date(date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
