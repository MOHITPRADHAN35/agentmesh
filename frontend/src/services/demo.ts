/* DEMO DATA — in-browser only, persisted to localStorage. Never presented as backend state. */
import type { AgentName, AgentStep, ChatMessage, ChatResponse, Conflict, Graph, GraphEdge, GraphNode, Memory, Resolution, Session } from "./types";

interface Store { sessions: Session[]; messages: Record<string, ChatMessage[]>; memories: Memory[]; conflicts: Conflict[] }
const KEY = "agentmesh-demo-v1";
const now = () => new Date().toISOString();
const uid = (p: string) => `${p}_${Math.random().toString(36).slice(2, 8)}`;
const wait = (ms: number) => new Promise((r) => setTimeout(r, ms));

function seed(): Store {
  const s1: Session = { id: "ses_launch", title: "Q3 launch planning", created_at: "2026-10-10T09:12:00Z", message_count: 2 };
  const m = (id: string, text: string, type: string, agent: AgentName, c: number, source: string): Memory =>
    ({ id, text, type, agent, confidence: c, source, session_id: s1.id, created_at: "2026-10-10T09:14:00Z" });
  const memories = [
    m("mem_1", "Launch date is targeted for November 18.", "decision", "Planner", 0.92, "kickoff-notes.md"),
    m("mem_2", "Launch date moved to December 2 due to compliance review.", "fact", "Researcher", 0.81, "slack #launch"),
    m("mem_3", "Primary audience: platform engineering teams.", "preference", "Researcher", 0.88, "persona-doc"),
    m("mem_4", "Budget capped at $40k for launch marketing.", "constraint", "Planner", 0.95, "finance-sheet"),
  ];
  return {
    sessions: [s1],
    messages: { [s1.id]: [
      { id: "msg_0", role: "user", content: "Summarize what we know about the launch.", created_at: s1.created_at },
      { id: "msg_1", role: "assistant", provider: "demo", created_at: s1.created_at,
        content: "Launch targets platform engineering teams with a $40k budget. The date is disputed: Nov 18 vs Dec 2 — flagged for review.",
        evidence: memories.map((x) => ({ memory_id: x.id, text: x.text, source: x.source })),
        steps: [
          { agent: "Researcher", status: "done", output: "Found 4 relevant memories across 3 sources." },
          { agent: "Planner", status: "done", output: "Drafted summary; budget and audience are stable." },
          { agent: "Reviewer", status: "done", output: "Detected contradiction on launch date." },
        ] },
    ] },
    memories,
    conflicts: [{ id: "con_1", status: "open", a: memories[0]!, b: memories[1]!,
      reason: "Both statements assert a single launch date for the same release, but the dates differ by two weeks. The newer source cites a compliance review." }],
  };
}

function load(): Store {
  if (typeof window === "undefined") return seed();
  try { const r = localStorage.getItem(KEY); if (r) return JSON.parse(r); } catch { /* ignore */ }
  const s = seed(); save(s); return s;
}
function save(s: Store) { if (typeof window !== "undefined") localStorage.setItem(KEY, JSON.stringify(s)); }

export const demo = {
  async health() { await wait(150); return { status: "ok" as const, database: true, mode: "demo" as const }; },
  async sessions() { await wait(150); return [...load().sessions].reverse(); },
  async createSession(title?: string) {
    const s = load(); const ses = { id: uid("ses"), title: title || "Untitled session", created_at: now(), message_count: 0 };
    s.sessions.push(ses); s.messages[ses.id] = []; save(s); return ses;
  },
  async deleteSession(id: string) {
    const s = load();
    s.sessions = s.sessions.filter((x) => x.id !== id);
    delete s.messages[id];
    s.memories = s.memories.filter((m) => m.session_id !== id);
    save(s);
    return { success: true };
  },
  async renameSession(id: string, title: string) {
    const s = load();
    const ses = s.sessions.find((x) => x.id === id);
    if (ses) ses.title = title;
    save(s);
    return ses ?? { id, title, created_at: now(), message_count: 0 };
  },
  async messages(id: string) { await wait(100); return load().messages[id] ?? []; },
  async chat(session_id: string, message: string): Promise<ChatResponse> {
    await wait(1600);
    const s = load();
    const words = message.toLowerCase().split(/\W+/).filter((w) => w.length > 3);
    const retrieved = s.memories.filter((m) => words.some((w) => m.text.toLowerCase().includes(w))).slice(0, 4);
    const newMem: Memory = { id: uid("mem"), text: message.length > 120 ? message.slice(0, 117) + "…" : message, type: "note",
      agent: "Researcher", confidence: 0.7, source: `chat:${session_id}`, session_id, created_at: now() };
    s.memories.push(newMem);
    const steps: AgentStep[] = [
      { agent: "Researcher", status: "done", output: `Retrieved ${retrieved.length} memories; stored 1 new note.` },
      { agent: "Planner", status: "done", output: retrieved.length ? "Composed answer from prior memories." : "No prior context — answered from the message." },
      { agent: "Reviewer", status: "done", output: s.conflicts.some((c) => c.status === "open") ? "Open conflicts exist; answer caveated." : "No contradictions found." },
    ];
    const reply: ChatMessage = { id: uid("msg"), role: "assistant", provider: "demo", created_at: now(), steps,
      retrieved_memory_ids: retrieved.map((r) => r.id),
      evidence: retrieved.map((r) => ({ memory_id: r.id, text: r.text, source: r.source })),
      content: retrieved.length
        ? `Based on ${retrieved.length} stored memor${retrieved.length > 1 ? "ies" : "y"}: ${retrieved.map((r) => r.text).join(" ")}`
        : "I don't have prior memories on this yet. I've saved your message so future sessions can recall it." };
    s.messages[session_id] = [...(s.messages[session_id] ?? []),
      { id: uid("msg"), role: "user", content: message, created_at: now() }, reply];
    const ses = s.sessions.find((x) => x.id === session_id);
    if (ses) { ses.message_count = s.messages[session_id].length; if (ses.title === "Untitled session") ses.title = message.slice(0, 40); }
    save(s);
    return { session_id, message: reply, created_memory_ids: [newMem.id] };
  },
  async memories(q: string) { await wait(150); const l = q.toLowerCase(); return load().memories.filter((m) => !l || m.text.toLowerCase().includes(l) || m.type.includes(l)).reverse(); },
  async graph(session_id?: string): Promise<Graph> {
    await wait(200);
    const s = load();
    const nodes: GraphNode[] = []; const edges: GraphEdge[] = [];
    const sess = session_id ? s.sessions.filter((x) => x.id === session_id) : s.sessions;
    const ids = new Set(sess.map((x) => x.id));
    sess.forEach((x) => nodes.push({ id: x.id, type: "Session", label: x.title }));
    (["Researcher", "Planner", "Reviewer"] as const).forEach((a) => nodes.push({ id: `agent_${a}`, type: "Agent", label: a }));
    s.memories.filter((m) => ids.has(m.session_id)).forEach((m) => {
      nodes.push({ id: m.id, type: "Memory", label: m.text, data: { type: m.type, confidence: m.confidence, source: m.source } });
      edges.push({ id: `e_${m.id}_s`, source: m.session_id, target: m.id, label: "CONTAINS" });
      if (m.agent) edges.push({ id: `e_${m.id}_a`, source: `agent_${m.agent}`, target: m.id, label: "EXTRACTED" });
    });
    sess.forEach((x) => { nodes.push({ id: `task_${x.id}`, type: "Task", label: `Answer: ${x.title}` }); edges.push({ id: `e_t_${x.id}`, source: x.id, target: `task_${x.id}`, label: "HAS_TASK" }); });
    s.conflicts.filter((c) => ids.has(c.a.session_id)).forEach((c) => {
      nodes.push({ id: c.id, type: "Conflict", label: c.status === "open" ? "Open conflict" : "Resolved", data: { status: c.status } });
      edges.push({ id: `e_${c.id}_x`, source: c.a.id, target: c.b.id, label: "CONTRADICTS" });
      edges.push({ id: `e_${c.id}_a`, source: c.id, target: c.a.id, label: "INVOLVES" });
      edges.push({ id: `e_${c.id}_b`, source: c.id, target: c.b.id, label: "INVOLVES" });
      edges.push({ id: `e_${c.id}_r`, source: "agent_Reviewer", target: c.id, label: "FLAGGED" });
    });
    return { nodes, edges };
  },
  async conflicts() { await wait(150); return load().conflicts; },
  async resolve(id: string, r: Resolution) {
    await wait(500); const s = load(); const c = s.conflicts.find((x) => x.id === id);
    if (!c) throw new Error("Conflict not found");
    if (r !== "unresolved") c.status = "resolved";
    // historical memories are never deleted; the losing memory gets a lowered confidence only
    if (r === "accept_a") { const m = s.memories.find((x) => x.id === c.b.id); if (m) m.confidence = 0.2; }
    if (r === "accept_b") { const m = s.memories.find((x) => x.id === c.a.id); if (m) m.confidence = 0.2; }
    save(s); return c;
  },
  reset() { if (typeof window !== "undefined") localStorage.removeItem(KEY); },
};
