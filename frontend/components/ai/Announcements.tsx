"use client";

import { useEffect, useState, useCallback } from "react";
import { announcementsApi, Announcement } from "@/lib/api";
import { RefreshCw, Loader2, Megaphone, Pin } from "lucide-react";

interface AnnouncementsProps {
  token: string;
}

const CATEGORY_COLORS: Record<string, string> = {
  GENERAL:    "bg-blue-100 text-blue-700",
  HR:         "bg-pink-100 text-pink-700",
  IT:         "bg-violet-100 text-violet-700",
  FACILITIES: "bg-orange-100 text-orange-700",
  CULTURE:    "bg-emerald-100 text-emerald-700",
};

export function Announcements({ token }: AnnouncementsProps) {
  const [items, setItems] = useState<Announcement[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await announcementsApi.list(token);
      if (res.data?.success) {
        setItems(res.data.data ?? []);
      } else {
        setError("Failed to load announcements.");
      }
    } catch {
      setError("Network error loading announcements.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="flex flex-col h-full overflow-hidden bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
        <div>
          <h2 className="text-base font-semibold text-slate-800">Announcements</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {loading ? "Loading…" : `${items.length} announcement${items.length !== 1 ? "s" : ""}`}
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
            <Megaphone className="h-10 w-10 mb-3 text-slate-300" />
            <p className="text-sm font-medium">No announcements</p>
          </div>
        )}

        {!loading && !error && items.length > 0 && (
          <div className="space-y-3">
            {items.map((ann) => (
              <div
                key={ann.id}
                className={`rounded-lg border px-4 py-3 ${ann.is_pinned ? "border-brand/30 bg-brand/5" : "border-slate-200 bg-slate-50"}`}
              >
                <div className="flex items-start gap-2 flex-wrap">
                  {ann.is_pinned && <Pin className="h-3.5 w-3.5 text-brand mt-0.5 shrink-0" />}
                  <span className="text-sm font-semibold text-slate-800 flex-1">{ann.title}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${CATEGORY_COLORS[ann.category] ?? "bg-slate-100 text-slate-600"}`}>
                    {ann.category}
                  </span>
                </div>
                <p className="text-xs text-slate-600 mt-1.5 whitespace-pre-line">{ann.content}</p>
                <p className="text-xs text-slate-400 mt-2">
                  {new Date(ann.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
