"use client";

import { useEffect, useState, useCallback } from "react";
import { ticketsApi, Ticket } from "@/lib/api";
import { RefreshCw, Loader2, Ticket as TicketIcon } from "lucide-react";

interface MyTicketsProps {
  token: string;
}

const STATUS_COLORS: Record<string, string> = {
  OPEN:        "bg-yellow-100 text-yellow-700",
  IN_PROGRESS: "bg-blue-100 text-blue-700",
  RESOLVED:    "bg-green-100 text-green-700",
  CLOSED:      "bg-gray-100 text-gray-500",
};

const PRIORITY_COLORS: Record<string, string> = {
  LOW:      "bg-slate-100 text-slate-600",
  MEDIUM:   "bg-blue-100 text-blue-700",
  HIGH:     "bg-orange-100 text-orange-700",
  CRITICAL: "bg-red-100 text-red-700",
};

export function MyTickets({ token }: MyTicketsProps) {
  const [items, setItems] = useState<Ticket[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await ticketsApi.list(token);
      if (res.data?.success) {
        setItems(res.data.data ?? []);
      } else {
        setError("Failed to load tickets.");
      }
    } catch {
      setError("Network error loading tickets.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="flex flex-col h-full overflow-hidden bg-white">
      <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
        <div>
          <h2 className="text-base font-semibold text-slate-800">Tickets</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {loading ? "Loading…" : `${items.length} ticket${items.length !== 1 ? "s" : ""}`}
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
            <TicketIcon className="h-10 w-10 mb-3 text-slate-300" />
            <p className="text-sm font-medium">No tickets</p>
            <p className="text-xs mt-1">Use HR Tasks to create a ticket.</p>
          </div>
        )}

        {!loading && !error && items.length > 0 && (
          <div className="space-y-3">
            {items.map((t) => (
              <div key={t.id} className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-slate-800 flex-1 truncate">{t.title}</span>
                  <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${STATUS_COLORS[t.status] ?? "bg-slate-100 text-slate-600"}`}>
                    {t.status}
                  </span>
                  <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${PRIORITY_COLORS[t.priority] ?? "bg-slate-100 text-slate-600"}`}>
                    {t.priority}
                  </span>
                </div>
                <div className="flex items-center gap-3 mt-1.5">
                  <span className="text-xs text-slate-500">{t.category}</span>
                  {t.assigned_to_id && (
                    <span className="text-xs text-slate-500">Assigned to #{t.assigned_to_id}</span>
                  )}
                  <span className="text-xs text-slate-400 ml-auto">
                    {new Date(t.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
