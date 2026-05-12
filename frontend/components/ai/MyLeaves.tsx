"use client";

import { useEffect, useState, useCallback } from "react";
import { leavesApi, LeaveRequest } from "@/lib/api";
import { RefreshCw, Loader2, Calendar } from "lucide-react";

interface MyLeavesProps {
  token: string;
}

const LEAVE_TYPE_COLORS: Record<string, string> = {
  CASUAL:  "bg-blue-100 text-blue-700",
  SICK:    "bg-red-100 text-red-700",
  ANNUAL:  "bg-green-100 text-green-700",
  UNPAID:  "bg-gray-100 text-gray-700",
};

const STATUS_COLORS: Record<string, string> = {
  PENDING:   "bg-yellow-100 text-yellow-700",
  APPROVED:  "bg-green-100 text-green-700",
  REJECTED:  "bg-red-100 text-red-700",
  CANCELLED: "bg-gray-100 text-gray-500",
};

export function MyLeaves({ token }: MyLeavesProps) {
  const [items, setItems] = useState<LeaveRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await leavesApi.myLeaves(token);
      if (res.data?.success) {
        setItems(res.data.data ?? []);
      } else {
        setError("Failed to load leave history.");
      }
    } catch {
      setError("Network error loading leave history.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="flex flex-col h-full overflow-hidden bg-white">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
        <div>
          <h2 className="text-base font-semibold text-slate-800">My Leave History</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {loading ? "Loading…" : `${items.length} request${items.length !== 1 ? "s" : ""}`}
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

      {/* Body */}
      <div className="flex-1 overflow-y-auto px-6 py-4">
        {loading && (
          <div className="flex items-center justify-center py-12">
            <Loader2 className="h-6 w-6 animate-spin text-slate-400" />
          </div>
        )}

        {!loading && error && (
          <div className="rounded-md border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        {!loading && !error && items.length === 0 && (
          <div className="flex flex-col items-center justify-center py-16 text-slate-400">
            <Calendar className="h-10 w-10 mb-3 text-slate-300" />
            <p className="text-sm font-medium">No leave requests</p>
            <p className="text-xs mt-1">You have not applied for any leave yet.</p>
          </div>
        )}

        {!loading && !error && items.length > 0 && (
          <div className="space-y-3">
            {items.map((req) => (
              <div
                key={req.id}
                className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 flex items-center gap-4"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${LEAVE_TYPE_COLORS[req.leave_type] ?? "bg-slate-100 text-slate-600"}`}>
                      {req.leave_type}
                    </span>
                    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${STATUS_COLORS[req.status] ?? "bg-slate-100 text-slate-600"}`}>
                      {req.status}
                    </span>
                  </div>
                  <p className="text-xs text-slate-700 mt-1.5 font-medium">
                    {req.start_date} → {req.end_date}
                  </p>
                  {req.reason && (
                    <p className="text-xs text-slate-500 mt-0.5 italic truncate">&quot;{req.reason}&quot;</p>
                  )}
                </div>
                <p className="text-xs text-slate-400 shrink-0">
                  {new Date(req.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
