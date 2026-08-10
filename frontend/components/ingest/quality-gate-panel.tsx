import { CheckCircle2, ShieldAlert, Loader2, Clock, type LucideIcon } from "lucide-react";
import type { IngestBatch, QualityRuleResult } from "@/lib/types";

/** Batch row pass-rate at/above this curates; below it the whole batch is
 * quarantined and nothing is persisted — src/functions/quality_gate/rules.py
 * `DEFAULT_PASS_THRESHOLD`, mirrored by lib/mock/ingest.ts. */
const GATE_THRESHOLD = 90;

const STATUS_META: Record<IngestBatch["status"], { label: string; tone: string; Icon: LucideIcon }> = {
  passed: { label: "Curated", tone: "border-success/40 bg-success-soft text-success", Icon: CheckCircle2 },
  failed: { label: "Quarantined", tone: "border-danger/40 bg-danger-soft text-danger", Icon: ShieldAlert },
  running: { label: "Running", tone: "border-info/40 bg-info-soft text-info", Icon: Loader2 },
  queued: { label: "Queued", tone: "border-border-strong bg-surface-2 text-text-muted", Icon: Clock },
};

/**
 * Quality-gate pass/quarantine result for one batch, with the score formula
 * always shown alongside the number it produced — never a bare score.
 * Element 3.
 */
export function QualityGatePanel({
  quality,
  overallScore,
  status,
  rowsRaw,
  rowsCurated,
}: {
  quality: QualityRuleResult[];
  overallScore: number;
  status: IngestBatch["status"];
  rowsRaw: number;
  rowsCurated: number;
}) {
  const meta = STATUS_META[status];
  const isTerminal = status === "passed" || status === "failed";

  return (
    <div className="rounded-md border border-border-2 bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] font-semibold ${meta.tone}`}>
          <meta.Icon className={`size-3.5 ${status === "running" ? "animate-spin" : ""}`} aria-hidden />
          {meta.label}
        </span>
        {isTerminal && (
          <span className="text-[11px] text-text-muted">
            {rowsCurated.toLocaleString()} of {rowsRaw.toLocaleString()} rows curated
          </span>
        )}
      </div>

      {/* Formula — always visible, never a bare number. */}
      <div className="mt-3 rounded-md border border-dashed border-border-strong bg-surface-2 px-3 py-2">
        <p className="font-mono text-[11px] text-text-strong">
          score = 100 &times; passed_rows &divide; (passed_rows + failed_rows)
        </p>
        <p className="mt-1 text-[11px] leading-relaxed text-text-muted">
          Batches scoring <strong className="text-text-strong">&ge; {GATE_THRESHOLD}</strong> curate
          into <code className="font-mono">grants_curated</code>; below {GATE_THRESHOLD} the whole
          batch is quarantined in <code className="font-mono">grants_raw</code> — nothing persists.
        </p>
      </div>

      {isTerminal ? (
        <>
          <div className="mt-3">
            <div className="flex items-baseline justify-between">
              <span className="text-[11px] font-semibold uppercase tracking-wide text-text-subtle">Overall score</span>
              <span className="font-mono text-lg font-bold text-text-strong">{overallScore.toFixed(1)}</span>
            </div>
            <div className="relative mt-1.5 h-2 overflow-hidden rounded-full bg-surface-2">
              <div
                className={`h-full rounded-full ${overallScore >= GATE_THRESHOLD ? "bg-success" : "bg-danger"}`}
                style={{ width: `${Math.min(100, overallScore)}%` }}
              />
              <div
                className="absolute inset-y-0 border-l border-dashed border-text-subtle/60"
                style={{ left: `${GATE_THRESHOLD}%` }}
                title={`Gate threshold: ${GATE_THRESHOLD}`}
              />
            </div>
          </div>

          <ul className="mt-3 space-y-1.5">
            {quality.map((r) => (
              <li key={r.rule} className="flex items-center gap-2 text-[11.5px]">
                <span className="w-[184px] shrink-0 truncate font-mono text-text-muted">{r.rule}</span>
                <span className="relative h-1.5 flex-1 overflow-hidden rounded-full bg-surface-2">
                  <span
                    className={`absolute inset-y-0 left-0 rounded-full ${r.score >= GATE_THRESHOLD ? "bg-success" : "bg-warn"}`}
                    style={{ width: `${r.score}%` }}
                  />
                </span>
                <span className="w-12 shrink-0 text-right font-mono text-text-strong">{r.score.toFixed(1)}</span>
                <span className="w-24 shrink-0 text-right text-text-subtle">
                  {r.passed_rows}/{r.passed_rows + r.failed_rows} pass
                </span>
              </li>
            ))}
          </ul>
        </>
      ) : (
        <p className="mt-3 text-[11.5px] text-text-muted">
          {status === "queued"
            ? "Waiting to enter the Fetch stage…"
            : "Fetch and Validate are running — the quality-gate result lands once Validate completes."}
        </p>
      )}
    </div>
  );
}
