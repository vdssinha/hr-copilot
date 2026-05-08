"use client";

import { useState, useRef, useEffect } from "react";
import { SourceList } from "./SourceList";
import { SQLResultTable } from "./SQLResultTable";
import { ActionResultCard } from "./ActionResultCard";
import { chatPolicy, chatSQL, chatActions, chatLangGraph, streamRouter, SSEEvent } from "@/lib/api";

export type Mode = "router" | "policy" | "sql" | "actions" | "langgraph";

interface Message {
  role: "user" | "assistant";
  text: string;
  statusLog?: string[];   // SSE status messages shown under assistant bubble
  sources?: unknown[];
  rows?: unknown[];
  sql?: string;
  action?: string;
  actionSuccess?: boolean;
  actionData?: Record<string, unknown>;
  error?: string;
}

interface ChatPanelProps {
  token: string;
  mode: Mode;
}

function extractFromRouterResult(data: Record<string, unknown>): Omit<Message, "role"> {
  const result = data.result as Record<string, unknown>;
  const route = data.route as Record<string, unknown>;
  const intent = route?.intent as string;
  if (intent === "POLICY_QA") return { text: result.answer as string, sources: result.sources as unknown[] };
  if (intent === "SQL_QUERY") return { text: result.answer as string, rows: result.rows as unknown[], sql: result.sql as string };
  if (intent === "HR_ACTION") return {
    text: result.answer as string,
    action: result.action as string,
    actionSuccess: result.success as boolean,
    actionData: result.data as Record<string, unknown>,
  };
  return { text: (result?.answer as string) ?? JSON.stringify(result) };
}

export function ChatPanel({ token, mode }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [statusText, setStatusText] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setLoading(true);
    setStatusText("Thinking…");

    try {
      if (mode === "router") {
        // SSE streaming path
        const statusLog: string[] = [];
        let finalMsg: Omit<Message, "role"> = { text: "" };

        await streamRouter(text, token, (event: SSEEvent) => {
          if (event.type === "status") {
            setStatusText(event.message);
            statusLog.push(event.message);
          } else if (event.type === "result") {
            const ev = event as { type: "result"; route: unknown; result: unknown };
            finalMsg = {
              ...extractFromRouterResult({ route: ev.route, result: ev.result }),
              statusLog: [...statusLog],
            };
          } else if (event.type === "error") {
            finalMsg = { text: event.message, error: event.message };
          }
        });

        setMessages((m) => [...m, { role: "assistant", ...finalMsg }]);

      } else if (mode === "policy") {
        const resp = await chatPolicy(text, token) as Record<string, unknown>;
        if (!resp.success) { setMessages((m) => [...m, { role: "assistant", text: (resp.error as string) ?? "Error" }]); return; }
        const d = resp.data as Record<string, unknown>;
        setMessages((m) => [...m, { role: "assistant", text: d.answer as string, sources: d.sources as unknown[] }]);

      } else if (mode === "sql") {
        const resp = await chatSQL(text, token) as Record<string, unknown>;
        if (!resp.success) { setMessages((m) => [...m, { role: "assistant", text: (resp.error as string) ?? "Error" }]); return; }
        const d = resp.data as Record<string, unknown>;
        setMessages((m) => [...m, { role: "assistant", text: d.answer as string, rows: d.rows as unknown[], sql: d.sql as string }]);

      } else if (mode === "actions") {
        const resp = await chatActions(text, token) as Record<string, unknown>;
        if (!resp.success) { setMessages((m) => [...m, { role: "assistant", text: (resp.error as string) ?? "Error" }]); return; }
        const d = resp.data as Record<string, unknown>;
        setMessages((m) => [...m, {
          role: "assistant",
          text: d.answer as string,
          action: d.action as string,
          actionSuccess: d.success as boolean,
          actionData: d.data as Record<string, unknown>,
        }]);

      } else if (mode === "langgraph") {
        const resp = await chatLangGraph(text, token) as Record<string, unknown>;
        if (!resp.success) { setMessages((m) => [...m, { role: "assistant", text: (resp.error as string) ?? "Error" }]); return; }
        const d = resp.data as Record<string, unknown>;
        setMessages((m) => [...m, { role: "assistant", ...extractFromRouterResult(d) }]);
      }

    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "Network error. Check the backend is running." }]);
    } finally {
      setLoading(false);
      setStatusText("");
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.length === 0 && (
          <p className="text-sm text-gray-400 text-center mt-8">Ask a question to get started.</p>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>
            <div
              className={`max-w-[80%] rounded-lg px-4 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-blue-600 text-white"
                  : "bg-white border border-gray-200 text-gray-800 shadow-sm"
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.text}</p>
              {msg.role === "assistant" && (
                <>
                  {msg.statusLog && msg.statusLog.length > 0 && (
                    <div className="mt-2 space-y-1">
                      {msg.statusLog.map((s, j) => (
                        <p key={j} className="text-xs text-gray-400 italic">↳ {s}</p>
                      ))}
                    </div>
                  )}
                  {msg.sources && <SourceList sources={msg.sources as { title: string; category: string; filename?: string }[]} />}
                  {msg.rows && msg.rows.length > 0 && (
                    <SQLResultTable rows={msg.rows as Record<string, unknown>[]} sql={msg.sql} showSQL />
                  )}
                  {msg.action && (
                    <ActionResultCard
                      action={msg.action}
                      success={msg.actionSuccess ?? false}
                      data={msg.actionData}
                    />
                  )}
                </>
              )}
            </div>
          </div>
        ))}
        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-gray-200 rounded-lg px-4 py-2 text-sm text-gray-400 shadow-sm animate-pulse">
              {statusText || "Thinking…"}
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={submit} className="border-t border-gray-200 p-3 flex gap-2 bg-white">
        <input
          className="flex-1 rounded-lg border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
          placeholder="Type your question…"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          disabled={loading}
        />
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="bg-blue-600 text-white rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50 hover:bg-blue-700 transition-colors"
        >
          Send
        </button>
      </form>
    </div>
  );
}
