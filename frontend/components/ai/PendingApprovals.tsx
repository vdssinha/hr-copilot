"use client";

import { useEffect, useState, useCallback } from "react";
import { leavesApi, LeaveRequest } from "@/lib/api";
import { CheckCircle, XCircle, RefreshCw, Loader2 } from "lucide-react";

interface PendingApprovalsProps {
  token: string;
}

const STATUS_COLORS: Record<string, string> = {
  CASUAL:  "bg-blue-100 text-blue-700",
  SICK:    "bg-red-100 text-red-700",
  ANNUAL:  "bg-green-100 text-green-700",
  UNPAID:  "bg-gray-100 text-gray-700",
};

export function PendingApprovals({ token }: PendingApprovalsProps) {
  const [items, setItems] = useState<LeaveRequest[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [acting, setActing] = useState<number | null>(null);
  const [toast, setToast] = useState<{ id: number; msg: string; ok: boolean } | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await leavesApi.pendingApprovals(token);
      if (res.data?.success) {
        setItems(res.data.data ?? []);
      } else {
        setError("Failed to load pending approvals.");
      }
    } catch {
      setError("Network error loading pending approvals.");
    } finally {
      setLoading(false);
    }
  }, [token]);

  useEffect(() => { load(); }, [load]);

  async function act(requestId: number, action: "approve" | "reject") {
    setActing(requestId);
    try {
      const res = action === "approve"
        ? await leavesApi.approve(token, requestId)
        : await leavesApi.reject(token, requestId);

      const ok = res.data?.success ?? false;
      setToast({ id: Date.now(), msg: ok ? `Request ${action}d.` : "Action failed.", ok });
      if (ok) setItems((prev) => prev.filter((r) => r.id !== requestId));
    } catch {
      setToast({ id: Date.now(), msg: "Network error.", ok: false });
    } finally {
      setActing(null);
      setTimeout(() => setToast(null), 3000);
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden bg-white">
      {/* Header */}
      <div className="flex items-center justify-between border-b border-slate-200 px-6 py-4">
        <div>
          <h2 className="text-base font-semibold text-slate-800">Pending Leave Approvals</h2>
          <p className="text-xs text-slate-500 mt-0.5">
            {loading ? "Loading…" : `${items.length} pending request${items.length !== 1 ? "s" : ""}`}
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

      {/* Toast */}
      {toast && (
        <div className={`mx-6 mt-3 rounded-md px-3 py-2 text-xs font-medium ${toast.ok ? "bg-green-50 text-green-700 border border-green-200" : "bg-red-50 text-red-700 border border-red-200"}`}>
          {toast.msg}
        </div>
      )}

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
            <CheckCircle className="h-10 w-10 mb-3 text-green-300" />
            <p className="text-sm font-medium">No pending approvals</p>
            <p className="text-xs mt-1">All leave requests have been processed.</p>
          </div>
        )}

        {!loading && !error && items.length > 0 && (
          <div className="space-y-3">
            {items.map((req) => (
              <div
                key={req.id}
                className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3 flex items-start gap-4"
              >
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <span className="text-sm font-semibold text-slate-800 truncate">
                      {req.employee_name ?? `Employee #${req.employee_id}`}
                    </span>
                    <span className={`text-xs px-1.5 py-0.5 rounded font-medium ${STATUS_COLORS[req.leave_type] ?? "bg-slate-100 text-slate-600"}`}>
                      {req.leave_type}
                    </span>
                  </div>
                  <p className="text-xs text-slate-600 mt-1">
                    {req.start_date} → {req.end_date}
                  </p>
                  {req.reason && (
                    <p className="text-xs text-slate-500 mt-1 italic truncate">"{req.reason}"</p>
                  )}
                </div>

                <div className="flex gap-2 shrink-0">
                  <button
                    onClick={() => act(req.id, "approve")}
                    disabled={acting === req.id}
                    className="flex items-center gap-1 rounded-md bg-green-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-green-700 disabled:opacity-50 transition-colors"
                  >
                    {acting === req.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <CheckCircle className="h-3 w-3" />}
                    Approve
                  </button>
                  <button
                    onClick={() => act(req.id, "reject")}
                    disabled={acting === req.id}
                    className="flex items-center gap-1 rounded-md bg-red-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-red-700 disabled:opacity-50 transition-colors"
                  >
                    {acting === req.id ? <Loader2 className="h-3 w-3 animate-spin" /> : <XCircle className="h-3 w-3" />}
                    Reject
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
