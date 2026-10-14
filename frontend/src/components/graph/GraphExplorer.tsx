import { useMemo, useState } from "react";
import { ReactFlow, Background, Controls, type Node, type Edge, MarkerType } from "@xyflow/react";
import type { Graph, GraphNode, NodeType } from "@/services/types";
import { X } from "lucide-react";

const TYPES: NodeType[] = ["Session", "Agent", "Memory", "Task", "Conflict"];
const COL: Record<NodeType, number> = { Session: 0, Task: 1, Memory: 2, Conflict: 3, Agent: 4 };
const COLOR: Record<NodeType, string> = {
  Memory: "var(--node-memory)", Agent: "var(--node-agent)", Session: "var(--node-session)",
  Task: "var(--node-task)", Conflict: "var(--node-conflict)",
};

export function GraphExplorer({ graph, highlight, selectedId, onSelect, large }: {
  graph: Graph; highlight: Set<string>; selectedId: string | null; onSelect: (id: string | null) => void; large?: boolean;
}) {
  const [hidden, setHidden] = useState<Set<NodeType>>(new Set());
  const visible = graph.nodes.filter((n) => !hidden.has(n.type));
  const visIds = new Set(visible.map((n) => n.id));

  const { nodes, edges } = useMemo(() => {
    const counts: Record<string, number> = {};
    const nodes: Node[] = visible.map((n) => {
      const col = COL[n.type]; const row = (counts[col] = (counts[col] ?? -1) + 1);
      const hl = highlight.has(n.id) || n.id === selectedId;
      const dim = highlight.size > 0 && !hl;
      return {
        id: n.id, position: { x: col * 260, y: row * 110 + (col % 2) * 40 },
        data: { label: <NodeCard n={n} /> },
        style: {
          width: 210, padding: 0, borderRadius: 8, background: "var(--card)",
          border: `1px solid ${hl ? COLOR[n.type] : "var(--border)"}`,
          boxShadow: hl ? `0 0 0 3px color-mix(in oklab, ${COLOR[n.type]} 25%, transparent)` : "none",
          opacity: dim ? 0.35 : 1, transition: "all .3s",
        },
      };
    });
    const edges: Edge[] = graph.edges.filter((e) => visIds.has(e.source) && visIds.has(e.target)).map((e) => {
      const c = e.label === "CONTRADICTS"; const hl = highlight.has(e.source) && highlight.has(e.target);
      return { id: e.id, source: e.source, target: e.target, label: e.label, animated: c || hl,
        style: { stroke: c ? "var(--node-conflict)" : hl ? "var(--primary)" : "color-mix(in oklab, var(--foreground) 22%, transparent)", strokeWidth: c || hl ? 2 : 1 },
        markerEnd: { type: MarkerType.ArrowClosed, width: 14, height: 14 } };
    });
    return { nodes, edges };
  }, [graph, hidden, highlight, selectedId]); // eslint-disable-line react-hooks/exhaustive-deps

  const sel = graph.nodes.find((n) => n.id === selectedId);

  return (
    <div className={`relative grain ${large ? "h-full" : "h-72"} w-full bg-surface`}>
      <div className="absolute left-3 top-3 z-10 flex flex-wrap gap-1.5">
        {TYPES.map((t) => (
          <button key={t} onClick={() => setHidden((h) => { const n = new Set(h); n.has(t) ? n.delete(t) : n.add(t); return n; })}
            className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[10px] uppercase tracking-wider transition ${hidden.has(t) ? "border-border text-muted-foreground opacity-50" : "border-border bg-card text-foreground"}`}>
            <span className="size-1.5 rounded-full" style={{ background: COLOR[t] }} />{t}
          </button>
        ))}
      </div>
      {graph.nodes.length === 0 ? (
        <div className="flex h-full items-center justify-center text-sm text-muted-foreground">No graph nodes yet — send a message to create memories.</div>
      ) : (
        <ReactFlow nodes={nodes} edges={edges} fitView minZoom={0.2} onNodeClick={(_, n) => onSelect(n.id)} onPaneClick={() => onSelect(null)} proOptions={{ hideAttribution: true }}>
          <Background gap={24} color="transparent" />
          <Controls showInteractive={false} />
        </ReactFlow>
      )}
      {sel && (
        <div className="absolute bottom-3 right-3 z-10 w-72 rounded-lg border border-border bg-popover p-4 shadow-2xl">
          <div className="mb-2 flex items-center justify-between">
            <span className="font-mono text-[10px] uppercase tracking-widest" style={{ color: COLOR[sel.type] }}>{sel.type}</span>
            <button onClick={() => onSelect(null)} aria-label="Close details"><X className="size-4 text-muted-foreground" /></button>
          </div>
          <p className="text-sm leading-relaxed">{sel.label}</p>
          <dl className="mt-3 space-y-1 font-mono text-[11px] text-muted-foreground">
            <div>id: {sel.id}</div>
            {Object.entries(sel.data ?? {}).map(([k, v]) => <div key={k}>{k}: {String(v)}</div>)}
            <div>links: {graph.edges.filter((e) => e.source === sel.id || e.target === sel.id).map((e) => e.label).join(", ") || "—"}</div>
          </dl>
        </div>
      )}
    </div>
  );
}

function NodeCard({ n }: { n: GraphNode }) {
  return (
    <div className="px-3 py-2 text-left">
      <div className="font-mono text-[9px] uppercase tracking-widest" style={{ color: COLOR[n.type] }}>{n.type}</div>
      <div className="mt-0.5 line-clamp-2 text-[11px] leading-snug text-card-foreground">{n.label}</div>
    </div>
  );
}
