import { useState } from "react";
import type { Conflict, Memory, Resolution } from "@/services/types";
import { AlertTriangle, Check } from "lucide-react";

export function ConflictPanel({ conflicts, onResolve }: { conflicts: Conflict[]; onResolve: (id: string, r: Resolution) => Promise<void> }) {
  const open = conflicts.filter((c) => c.status === "open");
  if (!open.length) return <p className="text-xs text-muted-foreground">No open conflicts. The reviewer will flag contradictions here.</p>;
  return <div className="space-y-4">{open.map((c) => <ConflictCard key={c.id} c={c} onResolve={onResolve} />)}</div>;
}

function ConflictCard({ c, onResolve }: { c: Conflict; onResolve: (id: string, r: Resolution) => Promise<void> }) {
  const [pending, setPending] = useState<Resolution | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const confirm = async () => {
    if (!pending) return; setBusy(true); setErr(null);
    try { await onResolve(c.id, pending); setPending(null); } catch (e) { setErr((e as Error).message); } finally { setBusy(false); }
  };
  const labels: Record<Resolution, string> = { accept_a: "Accept A", accept_b: "Accept B", keep_both: "Keep both", unresolved: "Leave open" };
  return (
    <div className="rounded-lg border border-destructive/40 bg-destructive/5 p-3">
      <div className="mb-2 flex items-center gap-2 font-mono text-[10px] uppercase tracking-widest text-destructive">
        <AlertTriangle className="size-3.5" /> Contradiction
      </div>
      <div className="grid grid-cols-2 gap-2">
        <Stmt tag="A" m={c.a} /><Stmt tag="B" m={c.b} />
      </div>
      <p className="mt-3 text-xs leading-relaxed text-muted-foreground"><span className="text-foreground">Reviewer:</span> {c.reason}</p>
      <div className="mt-3 grid grid-cols-2 gap-1.5">
        {(Object.keys(labels) as Resolution[]).map((r) => (
          <button key={r} onClick={() => setPending(r)}
            className={`rounded-md border px-2 py-1.5 text-xs transition ${pending === r ? "border-primary bg-accent text-accent-foreground" : "border-border hover:bg-secondary"}`}>{labels[r]}</button>
        ))}
      </div>
      {pending && (
        <div className="mt-2 flex items-center justify-between gap-2 rounded-md bg-surface p-2 text-[11px]">
          <span className="text-muted-foreground">History is kept. Confirm "{labels[pending]}"?</span>
          <button disabled={busy} onClick={confirm} className="flex items-center gap-1 rounded bg-primary px-2 py-1 font-medium text-primary-foreground disabled:opacity-50">
            <Check className="size-3" />{busy ? "Saving…" : "Confirm"}
          </button>
        </div>
      )}
      {err && <p className="mt-2 text-[11px] text-destructive">{err}</p>}
    </div>
  );
}

function Stmt({ tag, m }: { tag: string; m: Memory }) {
  return (
    <div className="rounded-md border border-border bg-card p-2.5">
      <div className="font-display text-xl leading-none text-primary">{tag}</div>
      <p className="mt-1.5 text-xs leading-snug">{m.text}</p>
      <div className="mt-2 space-y-0.5 font-mono text-[9px] text-muted-foreground">
        <div>{m.source}</div><div>{m.agent} · {new Date(m.created_at).toLocaleDateString()}</div>
      </div>
    </div>
  );
}
