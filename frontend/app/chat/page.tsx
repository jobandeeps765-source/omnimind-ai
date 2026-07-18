"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { api, clearToken, getToken, streamChat, uploadFile } from "@/lib/api";

type Message = { role: "user" | "assistant"; content: string; agent?: string };

const AGENT_LABELS: Record<string, string> = {
  chat: "Chat",
  coding: "Coding",
  data_analysis: "Data Analysis",
  research: "Research",
  report_writing: "Report Writing",
};

export default function ChatPage() {
  const router = useRouter();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [chatId, setChatId] = useState<string | undefined>(undefined);
  const [activeAgent, setActiveAgent] = useState<string | null>(null);
  const [activeFile, setActiveFile] = useState<{ name: string; path: string } | null>(null);
  const [sending, setSending] = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!getToken()) router.replace("/login");
  }, [router]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  function logout() {
    clearToken();
    router.push("/login");
  }

  async function handleUpload(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await uploadFile(file);
      setActiveFile({ name: res.name, path: res.path });
    } catch {
      alert("Upload failed");
    }
  }

  async function send() {
    if (!input.trim() || sending) return;
    const userMessage = input.trim();
    setInput("");
    setSending(true);
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setMessages((prev) => [...prev, { role: "assistant", content: "", agent: undefined }]);

    try {
      await streamChat(userMessage, chatId, activeFile?.path, (type, data) => {
        if (type === "routing") {
          setActiveAgent(data.agent);
          setChatId(data.chat_id);
          setMessages((prev) => {
            const copy = [...prev];
            copy[copy.length - 1] = { ...copy[copy.length - 1], agent: data.agent };
            return copy;
          });
        } else if (type === "delta") {
          setMessages((prev) => {
            const copy = [...prev];
            const last = copy[copy.length - 1];
            copy[copy.length - 1] = { ...last, content: last.content + data.text };
            return copy;
          });
        } else if (type === "done") {
          setActiveAgent(null);
        }
      });
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "Something went wrong reaching the server." },
      ]);
    } finally {
      setSending(false);
    }
  }

  return (
    <main className="flex h-screen">
      {/* Sidebar */}
      <aside className="flex w-64 flex-col border-r border-slate-800 bg-slate-900 p-4">
        <h1 className="mb-6 text-lg font-semibold">OmniMind AI</h1>

        <label className="mb-2 cursor-pointer rounded-lg border border-dashed border-slate-700 px-3 py-2 text-center text-sm text-slate-400 hover:border-slate-500">
          Upload file
          <input type="file" className="hidden" onChange={handleUpload} accept=".pdf,.docx,.csv,.xlsx,.xls,.txt" />
        </label>
        {activeFile && (
          <p className="mb-4 truncate text-xs text-emerald-400">Active: {activeFile.name}</p>
        )}

        <div className="mt-auto">
          <button onClick={logout} className="w-full rounded-lg bg-slate-800 py-2 text-sm hover:bg-slate-700">
            Log out
          </button>
        </div>
      </aside>

      {/* Chat area */}
      <section className="flex flex-1 flex-col">
        <div className="flex-1 overflow-y-auto px-6 py-6">
          {messages.length === 0 && (
            <p className="mt-20 text-center text-slate-500">
              Ask anything — I&apos;ll route it to the right agent (chat, coding, data analysis,
              research, or report writing).
            </p>
          )}

          <div className="mx-auto flex max-w-2xl flex-col gap-4">
            {messages.map((m, i) => (
              <div key={i} className={m.role === "user" ? "self-end" : "self-start"}>
                {m.role === "assistant" && m.agent && (
                  <span className="mb-1 inline-block rounded-full bg-indigo-950 px-2 py-0.5 text-xs text-indigo-300">
                    {AGENT_LABELS[m.agent] || m.agent}
                  </span>
                )}
                <div
                  className={`max-w-lg whitespace-pre-wrap rounded-2xl px-4 py-2 text-sm ${
                    m.role === "user" ? "bg-indigo-600" : "bg-slate-800"
                  }`}
                >
                  {m.content || (m.role === "assistant" ? "…" : "")}
                </div>
              </div>
            ))}
            <div ref={bottomRef} />
          </div>
        </div>

        <div className="border-t border-slate-800 p-4">
          <div className="mx-auto flex max-w-2xl gap-2">
            <input
              className="flex-1 rounded-lg border border-slate-700 bg-slate-900 px-4 py-2 text-sm"
              placeholder="Message OmniMind AI…"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && send()}
            />
            <button
              onClick={send}
              disabled={sending}
              className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium hover:bg-indigo-500 disabled:opacity-50"
            >
              Send
            </button>
          </div>
          {activeAgent && (
            <p className="mx-auto mt-2 max-w-2xl text-xs text-slate-500">
              Routed to: {AGENT_LABELS[activeAgent] || activeAgent}…
            </p>
          )}
        </div>
      </section>
    </main>
  );
}
