import { AlertTriangle } from "lucide-react";
import type { Anomaly } from "@/lib/types";
import { explainAnomaly, friendlyAnomalyKind } from "@/components/dashboard/anomaly-explanation";

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
  const visible = sorted.slice(0, 5);
  const remaining = sorted.slice(5);

  if (anomalies.length === 0) {
    return (
      <div className="rounded-md border border-border bg-surface-2/60 p-6 text-center text-xs text-text-muted">
        No anomalies flagged for the visible portfolio.
      </div>
    );
  }

  return (
    <div className="rounded-md border border-border bg-surface">
      <div className="flex items-start gap-2 border-b border-border-2 px-4 py-3">
        <AlertTriangle className="size-3.5 text-warn" aria-hidden />
        <div>
          <p className="text-xs font-bold text-text-strong">{openCount} items need human review</p>
          <p className="mt-1 text-[11px] leading-5 text-text-muted">An anomaly means a record looks different from similar records. It is not proof that the record or project is wrong.</p>
        </div>
      </div>
      <ul className="divide-y divide-border-2">
        {visible.map((a) => <FindingRow key={a.id} anomaly={a} />)}
      </ul>
      {remaining.length > 0 ? (
        <details className="border-t border-border">
          <summary className="cursor-pointer px-4 py-3 text-xs font-bold text-gov-primary">Show {remaining.length} more findings</summary>
          <ul className="divide-y divide-border-2 border-t border-border-2">
            {remaining.map((a) => <FindingRow key={a.id} anomaly={a} />)}
          </ul>
        </details>
      ) : null}
    </div>
  );
}

function FindingRow({ anomaly }: { anomaly: Anomaly }) {
  const explanation = explainAnomaly(anomaly);
  return (
    <li className="px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <span className={`rounded-full border px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${SEVERITY_TONE[anomaly.severity]}`}>{anomaly.severity}</span>
        <p className="text-xs font-bold text-text-strong">{friendlyAnomalyKind(anomaly.kind)}</p>
        <span className={`ml-auto rounded-full border px-1.5 py-0.5 text-[10px] font-semibold capitalize ${STATUS_TONE[anomaly.status]}`}>{anomaly.status}</span>
      </div>
      <p className="mt-2 text-xs leading-5 text-text">{explanation.whatHappened}</p>
      <p className="mt-1 text-[11px] leading-5 text-text-muted"><span className="font-bold text-gov-primary">Next:</span> {explanation.recommendedAction}</p>
      <details className="mt-2">
        <summary className="cursor-pointer text-[10px] font-bold text-text-subtle">Technical reason</summary>
        <p className="mt-1 text-[10.5px] leading-5 text-text-muted">{anomaly.reason}{anomaly.grant_no ? ` | ${anomaly.grant_no}` : ""}</p>
      </details>
    </li>
  );
}
