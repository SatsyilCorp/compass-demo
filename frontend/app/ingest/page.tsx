"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import Link from "next/link";
import { RefreshCw, UploadCloud, Loader2, ArrowUpRight } from "lucide-react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { RoleGate } from "@/components/shell/role-gate";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import { USE_MOCK, getIngestStatus, postIngestSimulate } from "@/lib/api";
import { buildQualityRows, overallScore as computeOverallScore } from "@/lib/mock/quality";
import type { IngestBatch, IngestSimulateResponse } from "@/lib/types";
import { BatchRow } from "@/components/ingest/batch-row";
import { VelocityLegend } from "@/components/ingest/velocity-legend";
import { StreamTicker } from "@/components/ingest/stream-ticker";
import { hashStr } from "@/components/ingest/velocity";

/** Batch row pass-rate at/above this curates — mirrors
 * src/functions/quality_gate/rules.py DEFAULT_PASS_THRESHOLD (90). */
const GATE_THRESHOLD = 90;
const STATUS_POLL_MS = 20_000;

function draftBatch(res: IngestSimulateResponse): IngestBatch {
  return {
    batch_id: res.batch_id,
    run_id: res.run_id,
    source_file: res.source_file,
    ingested_at: res.triggered_at,
    status: res.status,
    rows_raw: 0,
    rows_curated: 0,
    quality: [],
    overall_score: 0,
  };
}

export default function IngestPage() {
  const auth = useAppAuth();
  const [batches, setBatches] = useState<IngestBatch[]>([]);
  const [simulated, setSimulated] = useState<IngestBatch[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [simPending, setSimPending] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);
  const pendingTimeouts = useRef<ReturnType<typeof setTimeout>[]>([]);

  const refresh = useCallback(async (opts: { silent?: boolean } = {}) => {
    if (!opts.silent) setRefreshing(true);
    try {
      const res = await getIngestStatus();
      setBatches(res.batches);
      setLastRefreshed(new Date());
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
    // Re-pull whenever the persona (role/org_unit) changes — the RLS-scoped
    // batch list should change with it, same as every other element page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [auth.role, auth.orgUnit]);

  useEffect(() => {
    const t = setInterval(() => void refresh({ silent: true }), STATUS_POLL_MS);
    return () => clearInterval(t);
  }, [refresh]);

  useEffect(() => {
    const timeouts = pendingTimeouts.current;
    return () => {
      timeouts.forEach(clearTimeout);
    };
  }, []);

  const patchSimulated = useCallback((batchId: string, patch: Partial<IngestBatch>) => {
    setSimulated((prev) => prev.map((b) => (b.batch_id === batchId ? { ...b, ...patch } : b)));
  }, []);

  const handleSimulate = useCallback(async () => {
    setSimPending(true);
    try {
      const res = await postIngestSimulate();
      setSimulated((prev) => [draftBatch(res), ...prev].slice(0, 6));

      if (USE_MOCK) {
        // The mock POST /ingest/simulate is a "just triggered" convenience —
        // it deliberately never mutates the fixture batch list (see
        // lib/mock/ingest.ts). Animate the same Fetch -> Validate ->
        // Persist/Quarantine progression client-side, using the exact score
        // formula the rest of the app renders (lib/mock/quality.ts), so the
        // demo shows a real batch moving through the real gate.
        const t1 = setTimeout(() => patchSimulated(res.batch_id, { status: "running" }), 900);
        const t2 = setTimeout(() => {
          const rowCount = 28 + (hashStr(res.batch_id) % 84);
          const quality = buildQualityRows(res.batch_id, rowCount);
          const score = computeOverallScore(quality);
          const passed = score >= GATE_THRESHOLD;
          patchSimulated(res.batch_id, {
            status: passed ? "passed" : "failed",
            rows_raw: rowCount,
            // Quarantine (statemachines/intake.asl.yaml) never reaches
            // Persist — a quarantined batch curates zero rows.
            rows_curated: passed ? rowCount : 0,
            quality,
            overall_score: score,
          });
        }, 2600);
        pendingTimeouts.current.push(t1, t2);
      } else {
        // Live mode: the real Step Functions execution owns the progression.
        // Give it a moment, then let the next status poll pick up whatever
        // Fetch/Validate/Persist have actually completed.
        const t = setTimeout(() => void refresh({ silent: true }), 3000);
        pendingTimeouts.current.push(t);
      }
    } finally {
      setSimPending(false);
    }
  }, [patchSimulated, refresh]);

  const combined = [...simulated, ...batches];
  const simulatedIds = new Set(simulated.map((b) => b.batch_id));

  return (
    <AppShell>
      <PageHeader
        kicker="Element 3 · Ingest"
        title="Ingest & quality gate"
        lead="Every drop — batch, interval, or on-demand — runs the same Fetch → Validate → Persist/Quarantine state machine."
        icon={<UploadCloud className="size-4" aria-hidden />}
        actions={
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => void refresh()}
              disabled={refreshing}
              className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-2 text-[12.5px] font-medium text-text-muted transition-colors hover:border-border-strong hover:text-text-strong disabled:opacity-50"
            >
              <RefreshCw className={`size-3.5 ${refreshing ? "animate-spin" : ""}`} aria-hidden />
              Refresh
            </button>
            <button
              type="button"
              onClick={() => void handleSimulate()}
              disabled={simPending}
              className="inline-flex items-center gap-1.5 rounded-md bg-gov-primary px-4 py-2 text-[12.5px] font-semibold text-white shadow-card transition-colors hover:bg-action-hover disabled:opacity-60"
            >
              {simPending ? (
                <Loader2 className="size-3.5 animate-spin" aria-hidden />
              ) : (
                <UploadCloud className="size-3.5" aria-hidden />
              )}
              Drop a file (simulate)
            </button>
          </div>
        }
      />

      <RoleGate allow={["poweruser"]}>
        <p className="mt-3 text-[11.5px] text-text-muted">
          The full deployed intake state machine — every stage, its Lambda, and retry/catch policy —
          is under{" "}
          <Link href="/admin/pipeline/" className="inline-flex items-center gap-0.5 font-medium text-gov-primary hover:underline">
            Admin → Pipeline Config <ArrowUpRight className="size-3" aria-hidden />
          </Link>
          .
        </p>
      </RoleGate>

      <div className="mt-6 grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_340px]">
        <div className="space-y-5">
          <VelocityLegend />

          <section aria-label="Batch status">
            <div className="flex items-center justify-between">
              <h2 className="text-[13px] font-semibold text-text-strong">Live batch status</h2>
              {lastRefreshed && (
                <span className="text-[10.5px] text-text-subtle">updated {lastRefreshed.toLocaleTimeString()}</span>
              )}
            </div>
            {loading ? (
              <div className="mt-3 space-y-2">
                {[0, 1, 2].map((i) => (
                  <div key={i} className="skeleton h-16 rounded-lg" />
                ))}
              </div>
            ) : combined.length === 0 ? (
              <p className="mt-3 rounded-lg border border-dashed border-border-strong bg-surface-2 px-4 py-6 text-center text-[12.5px] text-text-muted">
                No batches visible for your org_unit yet.
              </p>
            ) : (
              <ul className="mt-3 space-y-2">
                {combined.map((b) => {
                  const isNew = simulatedIds.has(b.batch_id);
                  return (
                    <BatchRow
                      key={b.batch_id}
                      batch={b}
                      velocity={isNew ? "on-demand" : undefined}
                      isNew={isNew}
                      defaultOpen={isNew}
                    />
                  );
                })}
              </ul>
            )}
          </section>
        </div>

        <div className="space-y-5">
          <StreamTicker />
        </div>
      </div>
    </AppShell>
  );
}
