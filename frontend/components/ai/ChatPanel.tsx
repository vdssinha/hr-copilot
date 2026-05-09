"use client";

import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { Send, Bot, User } from "lucide-react";
import { SourceList } from "./SourceList";
import { SQLResultTable } from "./SQLResultTable";
import { ActionResultCard } from "./ActionResultCard";
import {
  chatPolicy, chatSQL, chatActions, chatLangGraph, chatHrData,
  streamRouter, StreamEvent, HistoryMessage,
} from "@/lib/api";

export type Mode = "router" | "policy" | "sql" | "actions" | "langgraph" | "hr-data";

interface Message {
  role: "user" | "assistant";
  text: string;
  statusLog?: string[];
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

const SUGGESTIONS: Record<Mode, string[]> = {
  router:    ["What is the leave policy?", "How many engineers are in the team?", "Apply for 2 days leave", "What benefits do I have?"],
  policy:    ["What is the work from home policy?", "How many sick leaves do I get?", "What is the code of conduct?", "Explain the attendance policy"],
  sql:       ["List all employees in Engineering", "How many people joined this year?", "Show projects with active employees", "Which departments have most employees?"],
  actions:   ["Apply for 2 days of annual leave", "Create an IT support ticket", "Show my leave balance", "List my open tickets"],
  langgraph: ["What is the maternity leave policy?", "Show salary bands for engineers", "How many employees are on contract?"],
  "hr-data": ["What is my salary?", "Show my performance rating", "What is my leave balance?", "Who is my manager?"],
};

function extractFromRouterResult(data: Record<string, unknown>): Omit<Message, "role"> {
  const result = data.result as Record<string, unknown>;
  const route  = data.route  as Record<string, unknown>;
  const intent = route?.intent as string;
  if (intent === "POLICY_QA") return { text: result.answer as string, sources: result.sources as unknown[] };
  if (intent === "SQL_QUERY")  return { text: result.answer as string, rows: result.rows as unknown[], sql: result.sql as string };
  if (intent === "HR_ACTION")  return {
    text: result.answer as string,
    action: result.action as string,
    actionSuccess: result.success as boolean,
    actionData: result.data as Record<string, unknown>,
  };
  return { text: (result?.answer as string) ?? JSON.stringify(result) };
}

export function ChatPanel({ token, mode }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput]       = useState("");
  const [loading, setLoading]   = useState(false);
  const [statusText, setStatusText] = useState("");
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages, loading]);

  async function submit(e?: React.FormEvent, quickText?: string) {
    e?.preventDefault();
    const text = (quickText ?? input).trim();
    if (!text || loading) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text }]);
    setLoading(true);
    setStatusText("Thinking…");

    const history: HistoryMessage[] = messages.map((m) => ({ role: m.role, content: m.text }));

    try {
      if (mode === "router") {
        const statusLog: string[] = [];
        let finalMsg: Omit<Message, "role"> = { text: "" };
        await streamRouter(text, token, (event: StreamEvent) => {
          if (event.type === "status")   { setStatusText(event.message); statusLog.push(event.message); }
          else if (event.type === "result") {
            const ev = event as { type: "result"; route: unknown; result: unknown };
            finalMsg = { ...extractFromRouterResult({ route: ev.route, result: ev.result }), statusLog: [...statusLog] };
          } else if (event.type === "error") {
            finalMsg = { text: event.message, error: event.message };
          }
        }, history);
        setMessages((m) => [...m, { role: "assistant", ...finalMsg }]);

      } else if (mode === "policy") {
        const resp = await chatPolicy(text, token, history) as Record<string, unknown>;
        const d = resp.data as Record<string, unknown>;
        setMessages((m) => [...m, { role: "assistant", text: (d?.answer ?? resp.error ?? "Error") as string, sources: d?.sources as unknown[] }]);

      } else if (mode === "sql") {
        const resp = await chatSQL(text, token, history) as Record<string, unknown>;
        const d = resp.data as Record<string, unknown>;
        setMessages((m) => [...m, { role: "assistant", text: (d?.answer ?? resp.error ?? "Error") as string, rows: d?.rows as unknown[], sql: d?.sql as string }]);

      } else if (mode === "actions") {
        const resp = await chatActions(text, token, history) as Record<string, unknown>;
        const d = resp.data as Record<string, unknown>;
        setMessages((m) => [...m, { role: "assistant", text: (d?.answer ?? resp.error ?? "Error") as string, action: d?.action as string, actionSuccess: d?.success as boolean, actionData: d?.data as Record<string, unknown> }]);

      } else if (mode === "langgraph") {
        const resp = await chatLangGraph(text, token, history) as Record<string, unknown>;
        const d = resp.data as Record<string, unknown>;
        setMessages((m) => [...m, { role: "assistant", ...extractFromRouterResult(d) }]);

      } else if (mode === "hr-data") {
        const resp = await chatHrData(text, token, history) as Record<string, unknown>;
        const d = resp.data as Record<string, unknown>;
        setMessages((m) => [...m, { role: "assistant", text: (d?.answer ?? resp.error ?? "Error") as string }]);
      }

    } catch {
      setMessages((m) => [...m, { role: "assistant", text: "Network error. Check the backend is running.", error: "network" }]);
    } finally {
      setLoading(false);
      setStatusText("");
    }
  }

  return (
    <div className="flex flex-col h-full overflow-hidden bg-white">
      {/* ── Messages ──────────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-4 md:px-8 lg:px-16 scrollbar-thin">
        <div className="mx-auto max-w-3xl py-6">

          {/* Empty state */}
          {messages.length === 0 && !loading && (
            <div className="flex flex-col items-center gap-6 py-16 text-center">
              <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-brand/10">
                <Bot className="h-7 w-7 text-brand" />
              </div>
              <div>
                <p className="text-lg font-semibold text-slate-800">How can I help you today?</p>
                <p className="mt-1 text-sm text-slate-500">Ask a question to get started.</p>
              </div>
              <div className="grid grid-cols-2 gap-2 w-full max-w-md">
                {SUGGESTIONS[mode]?.map((s) => (
                  <button
                    key={s}
                    onClick={() => submit(undefined, s)}
                    className="rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 text-left text-xs text-slate-600 hover:border-brand/40 hover:bg-brand-light hover:text-brand transition-colors"
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Message bubbles */}
          {messages.map((msg, i) => (
            <div key={i} className={`flex items-start gap-3 py-4 ${msg.role === "user" ? "flex-row-reverse" : "flex-row"}`}>
              {/* Avatar */}
              <div className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                msg.role === "user" ? "bg-brand text-white" : "bg-brand/10 text-brand"
              }`}>
                {msg.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
              </div>

              {/* Bubble */}
              <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm shadow-sm ${
                msg.role === "user"
                  ? "rounded-tr-sm bg-brand text-white"
                  : "rounded-tl-sm border border-slate-200 bg-white text-slate-800"
              }`}>
                {msg.role === "user" ? (
                  <p className="whitespace-pre-wrap leading-relaxed">{msg.text}</p>
                ) : (
                  <div className="prose-chat">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.text}</ReactMarkdown>
                  </div>
                )}

                {/* Status log */}
                {msg.statusLog && msg.statusLog.length > 0 && (
                  <div className="mt-2 space-y-0.5 border-t border-slate-100 pt-2">
                    {msg.statusLog.map((s, j) => (
                      <p key={j} className="text-xs text-slate-400 italic">↳ {s}</p>
                    ))}
                  </div>
                )}

                {/* Rich results */}
                {msg.sources && <SourceList sources={msg.sources as { title: string; category: string; filename?: string }[]} />}
                {msg.rows && msg.rows.length > 0 && <SQLResultTable rows={msg.rows as Record<string, unknown>[]} sql={msg.sql} showSQL />}
                {msg.action && <ActionResultCard action={msg.action} success={msg.actionSuccess ?? false} data={msg.actionData} />}

                {/* Error badge */}
                {msg.error && (
                  <p className="mt-1 text-xs text-red-500">{msg.error}</p>
                )}
              </div>
            </div>
          ))}

          {/* Typing indicator */}
          {loading && (
            <div className="flex items-start gap-3 py-4">
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-brand/10 text-brand">
                <Bot className="h-4 w-4" />
              </div>
              <div className="rounded-2xl rounded-tl-sm border border-slate-200 bg-white px-4 py-3 shadow-sm">
                {statusText ? (
                  <p className="text-xs text-slate-500 italic">{statusText}</p>
                ) : (
                  <div className="flex gap-1.5 items-center h-4">
                    <span className="h-2 w-2 rounded-full bg-slate-400 animate-bounce [animation-delay:0ms]" />
                    <span className="h-2 w-2 rounded-full bg-slate-400 animate-bounce [animation-delay:150ms]" />
                    <span className="h-2 w-2 rounded-full bg-slate-400 animate-bounce [animation-delay:300ms]" />
                  </div>
                )}
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* ── Input bar ─────────────────────────────────────────────────────── */}
      <div className="border-t border-slate-200 bg-white px-4 py-4 md:px-8 lg:px-16">
        <form onSubmit={submit} className="mx-auto flex max-w-3xl items-end gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
            placeholder="Ask a question… (Enter to send, Shift+Enter for new line)"
            rows={1}
            disabled={loading}
            className="flex-1 resize-none rounded-xl border border-slate-300 px-4 py-3 text-sm leading-relaxed focus:outline-none focus:ring-2 focus:ring-brand/40 focus:border-brand disabled:opacity-50 min-h-[44px] max-h-40"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-brand text-white hover:bg-brand-dark disabled:opacity-50 transition-colors"
          >
            <Send className="h-4 w-4" />
          </button>
        </form>
      </div>
    </div>
  );
}
