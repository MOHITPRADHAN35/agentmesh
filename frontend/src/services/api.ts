import type { ChatResponse, Conflict, Graph, Health, Memory, Resolution, Session } from "./types";
import { demo } from "./demo";

const BASE = (import.meta.env["VITE_API_BASE_URL"] as string | undefined)?.replace(/\/$/, "");
/** When no backend URL is configured, the app runs on clearly-labelled in-browser demo data. */
export const isDemo = !BASE;

async function req<T>(path: string, init?: RequestInit, timeout = 30000): Promise<T> {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), timeout);
  try {
    const res = await fetch(`${BASE}${path}`, {
      ...init,
      signal: ctrl.signal,
      headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    });
    if (!res.ok) throw new Error(`${res.status} ${res.statusText}: ${(await res.text()).slice(0, 200)}`);
    return (await res.json()) as T;
  } catch (e) {
    if ((e as Error).name === "AbortError") throw new Error(`Request timed out: ${path}`);
    throw e;
  } finally {
    clearTimeout(t);
  }
}

export const api = {
  health: (): Promise<Health> => (isDemo ? demo.health() : req("/api/health", undefined, 5000)),
  sessions: (): Promise<Session[]> => (isDemo ? demo.sessions() : req("/api/sessions")),
  createSession: (title?: string): Promise<Session> =>
    isDemo ? demo.createSession(title) : req("/api/sessions", { method: "POST", body: JSON.stringify({ title }) }),
  chat: (session_id: string, message: string): Promise<ChatResponse> =>
    isDemo ? demo.chat(session_id, message) : req("/api/chat", { method: "POST", body: JSON.stringify({ session_id, message }) }, 90000),
  messages: (session_id: string) => (isDemo ? demo.messages(session_id) : req<ChatResponse["message"][]>(`/api/sessions/${session_id}/messages`).catch(() => [])),
  memories: (query = ""): Promise<Memory[]> =>
    isDemo ? demo.memories(query) : req(`/api/memories?query=${encodeURIComponent(query)}`),
  graph: (session_id?: string): Promise<Graph> =>
    isDemo ? demo.graph(session_id) : req(`/api/graph${session_id ? `?session_id=${session_id}` : ""}`),
  conflicts: (): Promise<Conflict[]> => (isDemo ? demo.conflicts() : req("/api/conflicts")),
  resolve: (id: string, resolution: Resolution, note?: string): Promise<Conflict> =>
    isDemo ? demo.resolve(id, resolution) : req(`/api/conflicts/${id}/resolve`, { method: "POST", body: JSON.stringify({ resolution, note }) }),
  resetDemo: () => demo.reset(),
};
