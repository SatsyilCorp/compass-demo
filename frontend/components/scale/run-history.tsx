import { CheckCircle2, Clock3, History, PlayCircle, XCircle } from "lucide-react";
import { formatCount, formatCurrency, type ScaleRun } from "@/lib/scale";

export function RunHistory({ runs, activeRunId, onSelect }: { runs: ScaleRun[]; activeRunId: string | null; onSelect: (runId: string) => void }) {
  return (
    <section className="mt-6 rounded-xl border border-border bg-surface p-5 shadow-card" aria-labelledby="scale-run-history-heading">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-gold-ink">Durable proof list</p>
          <h2 id="scale-run-history-heading" className="mt-1 flex items-center gap-2 text-base font-bold text-text-strong"><History className="size-4 text-gov-primary" aria-hidden /> Recent workload runs</h2>
        </div>
        <span className="font-mono text-[10px] text-text-subtle">{formatCount(runs.length)} retained</span>
      </div>
      {runs.length === 0 ? (
        <div className="mt-4 rounded-lg border border-dashed border-border p-6 text-center">
          <PlayCircle className="mx-auto size-6 text-text-subtle" aria-hidden />
          <p className="mt-2 text-xs font-semibold text-text-strong">No workload receipts yet</p>
          <p className="mt-1 text-[10.5px] text-text-muted">Launch a ready profile to create the first durable proof record.</p>
        </div>
      ) : (
        <div className="mt-4 overflow-x-auto rounded-lg border border-border">
          <table className="w-full min-w-[760px] text-left text-xs">
            <thead className="bg-surface-2 text-[9px] uppercase tracking-wide text-text-subtle">
              <tr><th className="px-4 py-2.5">Run</th><th className="px-4 py-2.5">Status</th><th className="px-4 py-2.5">Profile</th><th className="px-4 py-2.5">Curated</th><th className="px-4 py-2.5">Cost</th><th className="px-4 py-2.5">Updated</th><th className="px-4 py-2.5"><span className="sr-only">Open</span></th></tr>
            </thead>
            <tbody className="divide-y divide-border-2">
              {runs.map((run) => (
                <tr key={run.run_id} className={activeRunId === run.run_id ? "bg-gov-primary-lighter/55" : "bg-white"}>
                  <td className="px-4 py-3 font-mono text-[10.5px] font-semibold text-text-strong">{run.run_id}</td>
                  <td className="px-4 py-3"><HistoryStatus run={run} /></td>
                  <td className="px-4 py-3 font-mono text-text-muted">{run.plan.profile_id.toUpperCase()}</td>
                  <td className="px-4 py-3 font-mono text-text-muted">{formatCount(run.progress.records_curated)}</td>
                  <td className="px-4 py-3 font-mono text-text-muted">{formatCurrency(run.costs.accrued_usd)}</td>
                  <td className="px-4 py-3 text-text-muted">{new Date(run.updated_at).toLocaleTimeString()}</td>
                  <td className="px-4 py-3 text-right">
                    <button type="button" onClick={() => onSelect(run.run_id)} className="min-h-10 rounded-md border border-border bg-white px-3 text-[10px] font-bold text-gov-primary hover:bg-surface-2">
                      {activeRunId === run.run_id ? "Selected" : "Open proof"}
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

function HistoryStatus({ run }: { run: ScaleRun }) {
  if (run.status === "completed") return <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-success"><CheckCircle2 className="size-3.5" aria-hidden /> Completed</span>;
  if (run.status === "failed" || run.status === "cancelled") return <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-text-muted"><XCircle className="size-3.5" aria-hidden /> {run.status === "failed" ? "Failed" : "Cancelled"}</span>;
  return <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-info"><Clock3 className="size-3.5" aria-hidden /> In progress</span>;
}
