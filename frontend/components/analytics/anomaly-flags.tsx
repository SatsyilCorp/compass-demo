import { AlertTriangle } from "lucide-react";
import type { Anomaly } from "@/lib/types";

const SEVERITY_RANK: Record<Anomaly["severity"], number> = { critical: 0, high: 1, medium: 2, low: 3 };

const SEVERITY_TONE: Record<Anomaly["severity"], string> = {
  critical: "border-severity-critical/40 bg-severity-critical/10 text-severity-critical",
  high: "border-severity-high/40 bg-severity-high/10 text-severity-high",
  medium: "border-severity-medium/40 bg-severity-medium/10 text-severity-medium",
  low: "border-severity-low/40 bg-severity-low/10 text-severity-low",
};

const STATUS_TONE: Record<Anomaly["status"], string> = {
  open: "border-warn/40 bg-warn-soft text-warn",
  acknowledged: "border-info/30 bg-info-soft text-info",
  resolved: "border-success/40 bg-success-soft text-success",
};

/**
 * Anomaly flags surfaced alongside the topic-model run. `GET /anomalies`
 * (element 6) is portfolio-wide rather than scoped to a single analytics
 * run_id - shown here as "currently open across the visible portfolio",
 * which is what the API actually returns, not implied per-run scoping.
 */
export function AnomalyFlags({ anomalies }: { anomalies: Anomaly[] }) {
  const openCount = anomalies.filter((a) => a.status === "open").length;
  const sorted = [...anomalies].sort((a, b) => SEVERITY_RANK[a.severity] - SEVERITY_RANK[b.severity]);

  if (anomalies.length === 0) {
    return (
      <div className="rounded-md border border-border bg-surface-2/60 p-6 text-center text-xs text-text-muted">
        No anomalies flagged for the visible portfolio.
      </div>
    );
  }

  return (
    <div className="rounded-md border border-border bg-surface">
      <div className="flex items-center gap-2 border-b border-border-2 px-4 py-2.5">
        <AlertTriangle className="size-3.5 text-warn" aria-hidden />
        <p className="text-xs text-text-muted">
          <span className="font-semibold text-text-strong">{openCount}</span> open of {anomalies.length} flagged
          anomal{anomalies.length === 1 ? "y" : "ies"} across the visible portfolio.
        </p>
      </div>
      <ul className="divide-y divide-border-2">
        {sorted.map((a) => (
          <li key={a.id} className="flex items-start gap-3 px-4 py-2.5">
            <span
              className={`mt-0.5 shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${SEVERITY_TONE[a.severity]}`}
            >
              {a.severity}
            </span>
            <div className="min-w-0 flex-1">
              <p className="text-xs leading-snug text-text">{a.reason}</p>
              <p className="mt-0.5 text-[10.5px] text-text-subtle">
                {a.kind}
                {a.grant_no && (
                  <>
                    {" · "}
                    <span className="font-mono">{a.grant_no}</span>
                  </>
                )}
              </p>
            </div>
            <span
              className={`shrink-0 rounded-full border px-1.5 py-0.5 text-[10px] font-semibold capitalize ${STATUS_TONE[a.status]}`}
            >
              {a.status}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
