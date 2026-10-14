import { useEffect, useRef, useState } from "react";
import type { AgentName, AgentStep, ChatMessage } from "@/services/types";
import { ArrowUp, Loader2, Search, ClipboardList, ShieldCheck } from "lucide-react";

const ICON: Record<AgentName, typeof Search> = { Researcher: Search, Planner: ClipboardList, Reviewer: ShieldCheck };

export function Workspace({ messages, sending, onSend, onEvidence }: {
  messages: ChatMessage[]; sending: boolean; onSend: (t: string) => void; onEvidence: (ids: string[]) => void;
}) {
  const [text, setText] = useState("");
  const end = useRef<HTMLDivElement>(null);
  useEffect(() => { end.current?.scrollIntoView({ behavior: "smooth" }); }, [messages.length, sending]);
  const submit = () => { const t = text.trim(); if (!t || sending) return; onSend(t); setText(""); };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-y-auto px-4 py-8 md:px-10">
        {messages.length === 0 && !sending ? (
          <div className="mx-auto mt-[12vh] max-w-xl text-center">
            <h1 className="font-display text-5xl leading-[1.05] md:text-6xl">Memory that <em className="text-primary">outlives</em> the session.</h1>
            <p className="mt-4 text-muted-foreground">Ask anything. Researcher, Planner and Reviewer recall what earlier sessions learned — and flag what contradicts.</p>
            <div className="mt-6 flex flex-wrap justify-center gap-2">
              {["What's our launch date?", "Summarize the launch budget", "Who is the target audience?"].map((s) => (
                <button key={s} onClick={() => onSend(s)} className="rounded-full border border-border px-3 py-1.5 text-sm hover:border-primary hover:text-primary">{s}</button>
              ))}
            </div>
          </div>
        ) : (
          <div className="mx-auto max-w-2xl space-y-8">
            {messages.map((m) => m.role === "user" ? (
              <div key={m.id} className="flex justify-end"><div className="max-w-[85%] rounded-2xl rounded-br-sm bg-sand px-4 py-2.5 text-sm text-primary-foreground">{m.content}</div></div>
            ) : (
              <div key={m.id} className="space-y-3">
                {m.steps && <Timeline steps={m.steps} />}
                <div className="flex items-center gap-2">
                  <span className="font-display text-lg italic">AgentMesh</span>
                  <span className={`rounded px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-widest ${m.provider === "live" ? "bg-success/15 text-success" : "bg-secondary text-muted-foreground"}`}>{m.provider === "live" ? "live provider" : "demo output"}</span>
                </div>
                <p className="text-[15px] leading-relaxed">{m.content}</p>
                {!!m.evidence?.length && (
                  <div className="border-l border-primary/50 pl-3">
                    <button onClick={() => onEvidence(m.evidence!.map((e) => e.memory_id))} className="mb-1.5 font-mono text-[10px] uppercase tracking-widest text-primary hover:underline">Evidence · {m.evidence.length} → show in graph</button>
                    <ol className="space-y-1">{m.evidence.map((e, i) => (
                      <li key={e.memory_id} className="text-xs text-muted-foreground"><span className="font-mono text-foreground">[{i + 1}]</span> {e.text} <span className="font-mono text-[10px]">— {e.source}</span></li>
                    ))}</ol>
                  </div>
                )}
              </div>
            ))}
            {sending && <Timeline steps={(["Researcher", "Planner", "Reviewer"] as AgentName[]).map((a, i) => ({ agent: a, status: i === 0 ? "running" : "idle", output: i === 0 ? "Searching memory graph…" : "Waiting" }))} />}
            <div ref={end} />
          </div>
        )}
      </div>
      <div className="border-t border-border px-4 py-3 md:px-10">
        <div className="mx-auto flex max-w-2xl items-end gap-2 rounded-xl border border-input bg-card p-2 focus-within:border-primary">
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={1} placeholder="Ask the agents…"
            onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); } }}
            className="max-h-40 flex-1 resize-none bg-transparent px-2 py-1.5 text-sm outline-none placeholder:text-muted-foreground" />
          <button onClick={submit} disabled={!text.trim() || sending} aria-label="Send"
            className="flex size-8 items-center justify-center rounded-lg bg-primary text-primary-foreground transition disabled:opacity-30">
            {sending ? <Loader2 className="size-4 animate-spin" /> : <ArrowUp className="size-4" />}
          </button>
        </div>
      </div>
    </div>
  );
}

function Timeline({ steps }: { steps: AgentStep[] }) {
  return (
    <div className="grid gap-1.5 sm:grid-cols-3">
      {steps.map((s) => { const I = ICON[s.agent]; return (
        <div key={s.agent} className="rounded-lg border border-border bg-card/60 p-2.5">
          <div className="flex items-center gap-1.5 text-xs font-medium">
            <I className="size-3.5 text-primary" />{s.agent}
            <span className={`ml-auto size-1.5 rounded-full ${s.status === "running" ? "pulse-dot bg-primary" : s.status === "done" ? "bg-success" : s.status === "error" ? "bg-destructive" : "bg-muted"}`} />
          </div>
          <p className="mt-1 text-[11px] leading-snug text-muted-foreground">{s.output}</p>
        </div>
      ); })}
    </div>
  );
}
