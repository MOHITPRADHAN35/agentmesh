import { createFileRoute } from "@tanstack/react-router";
import { useCallback, useEffect, useState } from "react";
import { api, isDemo } from "@/services/api";
import type { ChatMessage, Conflict, Graph, Health, Memory, Resolution, Session } from "@/services/types";
import { Workspace } from "@/components/chat/Workspace";
import { GraphExplorer } from "@/components/graph/GraphExplorer";
import { ConflictPanel } from "@/components/conflicts/ConflictPanel";
import { Plus, Menu, PanelRight, Maximize2, Minimize2, RotateCcw, Database, X, Search } from "lucide-react";

export const Route = createFileRoute("/")({
  head: () => ({
    meta: [
      { title: "AgentMesh — Persistent memory for AI agents" },
      { name: "description", content: "Multi-agent workspace with graph-backed memory, evidence trails and conflict resolution." },
      { property: "og:title", content: "AgentMesh — Persistent memory for AI agents" },
      { property: "og:description", content: "Researcher, Planner and Reviewer agents sharing a persistent knowledge graph." },
      { property: "og:type", content: "website" },
      { name: "twitter:card", content: "summary_large_image" },
    ],
  }),
  component: App,
});

function App() {
  const [health, setHealth] = useState<Health | null>(null);
  const [sessions, setSessions] = useState<Session[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [memories, setMemories] = useState<Memory[]>([]);
  const [query, setQuery] = useState("");
  const [graph, setGraph] = useState<Graph>({ nodes: [], edges: [] });
  const [graphErr, setGraphErr] = useState<string | null>(null);
  const [conflicts, setConflicts] = useState<Conflict[]>([]);
  const [highlight, setHighlight] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [lastWrite, setLastWrite] = useState<number | null>(null);
  const [graphBig, setGraphBig] = useState(false);
  const [graphScope, setGraphScope] = useState<"all" | "session">("all");
  const [leftOpen, setLeftOpen] = useState(false);
  const [rightOpen, setRightOpen] = useState(false);

  const refreshSide = useCallback(async () => {
    const [c, g] = await Promise.allSettled([api.conflicts(), api.graph(graphScope === "session" ? active ?? undefined : undefined)]);
    if (c.status === "fulfilled") setConflicts(c.value);
    if (g.status === "fulfilled") { setGraph(g.value); setGraphErr(null); } else setGraphErr((g.reason as Error).message);
  }, [active, graphScope]);

  useEffect(() => {
    api.health().then(setHealth).catch(() => setHealth({ status: "down", database: false }));
    api.sessions().then((s) => { setSessions(s); if (s[0]) setActive(s[0].id); }).catch((e) => setError(e.message));
  }, []);
  useEffect(() => { if (active) api.messages(active).then(setMessages).catch(() => setMessages([])); else setMessages([]); }, [active]);
  useEffect(() => { refreshSide(); }, [refreshSide]);
  useEffect(() => { const t = setTimeout(() => api.memories(query).then(setMemories).catch(() => {}), 200); return () => clearTimeout(t); }, [query, lastWrite]);

  const newSession = async () => {
    const s = await api.createSession(); setSessions((p) => [s, ...p]); setActive(s.id); setLeftOpen(false); setHighlight(new Set());
  };
  const send = async (text: string) => {
    let sid = active;
    if (!sid) { const s = await api.createSession(); setSessions((p) => [s, ...p]); sid = s.id; setActive(sid); }
    setSending(true); setError(null);
    setMessages((m) => [...m, { id: `tmp_${Date.now()}`, role: "user", content: text, created_at: new Date().toISOString() }]);
    try {
      const r = await api.chat(sid, text);
      const fresh = await api.messages(sid).catch(() => [] as ChatMessage[]);
      setMessages(fresh.length ? fresh : (prev) => [...prev, r.message]);
      if (r.created_memory_ids.length) setLastWrite(Date.now());
      setHighlight(new Set([...(r.message.retrieved_memory_ids ?? []), ...r.created_memory_ids]));
      api.sessions().then(setSessions);
      refreshSide();
    } catch (e) { setError((e as Error).message); } finally { setSending(false); }
  };
  const resolve = async (id: string, r: Resolution) => { await api.resolve(id, r); setLastWrite(Date.now()); await refreshSide(); };
  const reset = () => { if (confirm("Reset the demo sample project?")) { api.resetDemo(); location.reload(); } };
  const focusMemory = (id: string) => { setHighlight(new Set([id])); setSelected(id); };

  const openConflicts = conflicts.filter((c) => c.status === "open").length;
  const retrievedIds = new Set(messages.flatMap((m) => m.retrieved_memory_ids ?? m.evidence?.map((e) => e.memory_id) ?? []));
  const priorMem = memories.filter((m) => retrievedIds.has(m.id) && m.session_id !== active);

  const sidebar = (
    <aside className="flex h-full w-64 flex-col border-r border-border bg-surface">
      <div className="flex items-center justify-between px-5 pb-4 pt-5">
        <div className="font-display text-2xl tracking-tight">Agent<em className="text-primary">Mesh</em></div>
        <button className="md:hidden" onClick={() => setLeftOpen(false)} aria-label="Close"><X className="size-4" /></button>
      </div>
      <div className="px-3">
        <select className="w-full rounded-md border border-input bg-card px-2.5 py-1.5 text-sm outline-none" aria-label="Project"><option>Q3 Launch · sample</option></select>
        <button onClick={newSession} className="mt-2 flex w-full items-center justify-center gap-1.5 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"><Plus className="size-4" />New session</button>
      </div>
      <div className="mt-6 px-5 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Recent sessions</div>
      <nav className="mt-2 min-h-0 flex-1 space-y-0.5 overflow-y-auto px-2">
        {sessions.length === 0 && <p className="px-3 text-xs text-muted-foreground">No sessions yet.</p>}
        {sessions.map((s) => (
          <button key={s.id} onClick={() => { setActive(s.id); setLeftOpen(false); setHighlight(new Set()); }}
            className={`block w-full truncate rounded-md px-3 py-2 text-left text-sm transition ${s.id === active ? "bg-secondary text-foreground" : "text-muted-foreground hover:bg-secondary/60"}`}>
            {s.title}<span className="block font-mono text-[10px] opacity-60">{new Date(s.created_at).toLocaleDateString()} · {s.message_count ?? 0} msgs</span>
          </button>
        ))}
      </nav>
      <div className="space-y-2 border-t border-border p-4 font-mono text-[10px]">
        <div className="flex items-center gap-2">
          <span className={`size-1.5 rounded-full ${health?.status === "ok" ? "bg-success" : health ? "bg-destructive" : "pulse-dot bg-muted-foreground"}`} />
          API {health?.status ?? "checking"} · DB {health ? (health.database ? "connected" : "offline") : "…"}
        </div>
        {isDemo && <div className="flex items-center justify-between text-primary">DEMO DATA · local only<button onClick={reset} className="flex items-center gap-1 hover:underline"><RotateCcw className="size-3" />reset</button></div>}
      </div>
    </aside>
  );

  const context = (
    <aside className="flex h-full w-full flex-col overflow-y-auto border-l border-border bg-surface md:w-[340px]">
      <div className="flex items-center justify-between px-5 pt-5 md:hidden"><span className="font-display text-xl">Context</span><button onClick={() => setRightOpen(false)} aria-label="Close"><X className="size-4" /></button></div>
      <section className="p-5">
        <h2 className="mb-3 flex items-center justify-between font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Conflicts {openConflicts > 0 && <span className="rounded-full bg-destructive px-1.5 text-destructive-foreground">{openConflicts}</span>}</h2>
        <ConflictPanel conflicts={conflicts} onResolve={resolve} />
      </section>
      {priorMem.length > 0 && (
        <section className="border-t border-border p-5">
          <h2 className="mb-2 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Recalled from earlier sessions</h2>
          {priorMem.map((m) => <p key={m.id} className="text-xs text-muted-foreground">↺ {m.text}</p>)}
        </section>
      )}
      <section className="border-t border-border p-5">
        <h2 className="mb-3 font-mono text-[10px] uppercase tracking-widest text-muted-foreground">Memories</h2>
        <div className="mb-3 flex items-center gap-2 rounded-md border border-input bg-card px-2.5">
          <Search className="size-3.5 text-muted-foreground" />
          <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search memories" className="w-full bg-transparent py-1.5 text-sm outline-none" />
        </div>
        <div className="space-y-2">
          {memories.length === 0 && <p className="text-xs text-muted-foreground">No memories match.</p>}
          {memories.map((m) => (
            <button key={m.id} onClick={() => focusMemory(m.id)} className={`block w-full rounded-md border p-2.5 text-left transition ${highlight.has(m.id) ? "border-primary bg-accent" : "border-border bg-card hover:border-primary/50"}`}>
              <p className="text-xs leading-snug">{m.text}</p>
              <div className="mt-1.5 flex flex-wrap gap-x-2 font-mono text-[9px] text-muted-foreground">
                <span className="text-primary">{m.type}</span><span>{m.source}</span><span>{Math.round(m.confidence * 100)}%</span><span>{new Date(m.created_at).toLocaleDateString()}</span>
              </div>
            </button>
          ))}
        </div>
      </section>
    </aside>
  );

  return (
    <div className="flex h-screen overflow-hidden">
      <div className="hidden md:block">{sidebar}</div>
      {leftOpen && <div className="fixed inset-0 z-40 flex bg-background/70 md:hidden" onClick={() => setLeftOpen(false)}><div onClick={(e) => e.stopPropagation()}>{sidebar}</div></div>}

      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-3 border-b border-border px-4 py-2.5">
          <button className="md:hidden" onClick={() => setLeftOpen(true)} aria-label="Menu"><Menu className="size-5" /></button>
          <h1 className="truncate text-sm font-medium">{sessions.find((s) => s.id === active)?.title ?? "New workspace"}</h1>
          {lastWrite && <span className="flex items-center gap-1 rounded-full bg-success/10 px-2 py-0.5 font-mono text-[10px] text-success"><Database className="size-3" />memory saved {new Date(lastWrite).toLocaleTimeString()}</span>}
          <button className="ml-auto lg:hidden relative" onClick={() => setRightOpen(true)} aria-label="Context"><PanelRight className="size-5" />{openConflicts > 0 && <span className="absolute -right-1 -top-1 size-2 rounded-full bg-destructive" />}</button>
        </header>
        {error && <div className="border-b border-destructive/30 bg-destructive/10 px-4 py-2 text-xs text-destructive">{error}</div>}

        <div className={`min-h-0 ${graphBig ? "hidden" : "flex-1"}`}>
          <Workspace messages={messages} sending={sending} onSend={send} onEvidence={(ids) => setHighlight(new Set(ids))} />
        </div>

        <div className={`flex flex-col border-t border-border ${graphBig ? "min-h-0 flex-1" : ""}`}>
          <div className="flex items-center gap-3 px-4 py-2">
            <span className="font-display text-lg italic">Knowledge graph</span>
            <span className="font-mono text-[10px] text-muted-foreground">{graph.nodes.length} nodes · {graph.edges.length} edges</span>
            <div className="ml-auto flex items-center gap-2">
              <select value={graphScope} onChange={(e) => setGraphScope(e.target.value as "all" | "session")} className="rounded border border-input bg-card px-1.5 py-0.5 text-xs outline-none" aria-label="Session filter">
                <option value="all">All sessions</option><option value="session">This session</option>
              </select>
              {highlight.size > 0 && <button onClick={() => setHighlight(new Set())} className="text-xs text-muted-foreground hover:text-foreground">clear highlight</button>}
              <button onClick={() => setGraphBig((b) => !b)} aria-label="Toggle graph size">{graphBig ? <Minimize2 className="size-4" /> : <Maximize2 className="size-4" />}</button>
            </div>
          </div>
          <div className={graphBig ? "min-h-0 flex-1" : ""}>
            {graphErr ? <div className="flex h-72 items-center justify-center text-sm text-destructive">Graph failed to load: {graphErr}</div>
              : <GraphExplorer graph={graph} highlight={highlight} selectedId={selected} onSelect={setSelected} large={graphBig} />}
          </div>
        </div>
      </main>

      <div className="hidden lg:block">{context}</div>
      {rightOpen && <div className="fixed inset-0 z-40 flex justify-end bg-background/70 lg:hidden" onClick={() => setRightOpen(false)}><div className="w-[90vw] max-w-sm" onClick={(e) => e.stopPropagation()}>{context}</div></div>}
    </div>
  );
}
