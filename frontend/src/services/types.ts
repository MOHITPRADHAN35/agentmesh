export type NodeType = "Memory" | "Agent" | "Session" | "Task" | "Conflict";
export type AgentName = "Researcher" | "Planner" | "Reviewer";

export interface Health { status: "ok" | "degraded" | "down"; database: boolean; mode?: "live" | "demo" }
export interface Session { id: string; title: string; created_at: string; message_count?: number }
export interface Evidence { memory_id: string; text: string; source: string }
export interface AgentStep { agent: AgentName; status: "idle" | "running" | "done" | "error"; output: string }
export interface ChatMessage { id: string; role: "user" | "assistant"; content: string; created_at: string; evidence?: Evidence[]; steps?: AgentStep[]; provider?: "live" | "demo"; retrieved_memory_ids?: string[] }
export interface ChatResponse { session_id: string; message: ChatMessage; created_memory_ids: string[] }
export interface Memory { id: string; text: string; type: string; source: string; session_id: string; agent?: AgentName; created_at: string; confidence: number }
export interface GraphNode { id: string; type: NodeType; label: string; data?: Record<string, unknown> }
export interface GraphEdge { id: string; source: string; target: string; label: string }
export interface Graph { nodes: GraphNode[]; edges: GraphEdge[] }
export interface Conflict { id: string; reason: string; status: "open" | "resolved"; a: Memory; b: Memory }
export type Resolution = "accept_a" | "accept_b" | "keep_both" | "unresolved";
