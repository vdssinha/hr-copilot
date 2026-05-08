"use client";

import { useState, useRef, useEffect } from "react";
import { SourceList } from "./SourceList";
import { SQLResultTable } from "./SQLResultTable";
import { ActionResultCard } from "./ActionResultCard";

type Mode = "router" | "policy" | "sql" | "actions";

interface Message {
  role: "user" | "assistant";
  text: string;
  // assistant extras
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

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";

async function sendMessage(mode: Mode, message: string, token: string) {
  const path = mode === "router" ? "/chat/router"
    : mode === "policy" ? "/chat/policy"
    : mode === "sql" ? "/chat/sql"
    : "/chat/actions";
  const res = await fetch(`${API}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
    body: JSON.stringify({ message }),
  });
  return res.json();
}

function extractAssistantMessage(resp: unknown, mode: Mode): Omit<Message, "role"> {
  const r = resp as Record<string, unknown>;
  if (!r.success) return { text: (r.error as string) ?? "An error occurred.", error: r.error as string };
  const data = r.data as Record<string, unknown>;

  if (mode === "policy") {
    return { text: data.answer as string, sources: data.sources as unknown[] };
  }
  if (mode === "sql") {
    return { text: data.answer as string, rows: data.rows as unknown[], sql: data.sql as string };
  }
  if (mode === "actions") {
    return {
      text: data.answer as string,
      action: data.action as string,
      actionSuccess: data.success as boolean,
      actionData: data.data as Record<string, unknown>,
    };
  }
  // router: unwrap the inner result
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
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    const text = input.trim();
    if (!text || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setLoading(true);
    try {
      const resp = await sendMessage(mode, text, token);
      const msg = extractAssistantMessage(resp, mode);
      setMessages((m) => [...m, { role: "assistant", ...msg }]);
    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "Network error. Check the backend is running." }]);
    } finally {
      setLoading(false);
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
            <div className="bg-white border border-gray-200 rounded-lg px-4 py-2 text-sm text-gray-400 shadow-sm">
              Thinking…
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
