import type {
  EvidenceAuditEvent,
  EvidenceRun,
  EvidenceStage,
  SystemEvidenceResponse,
} from "@/lib/types";
import {
  getScenarioState,
  type ScenarioBatch,
} from "@/lib/mock/scenario-store";

const stages = (outcome: EvidenceRun["outcome"]): EvidenceStage[] => [
  { id: "receive", label: "Receive", status: "completed", receipt: "Object event accepted" },
  {
    id: "normalize",
    label: "Normalize",
    status: "completed",
    receipt: "Source shape mapped to the canonical contract",
  },
  {
    id: "validate",
    label: "Validate",
    status: "completed",
    receipt: "Deterministic quality rules evaluated",
  },
  { id: "gate", label: "Quality gate", status: "completed", receipt: "Batch threshold applied" },
  {
    id: "persist",
    label: "Curate",
    status: outcome === "curated" ? "completed" : "skipped",
    receipt: outcome === "curated" ? "Approved rows written under row security" : "No curated rows written",
  },
  {
    id: "evidence",
    label: "Evidence",
    status: "completed",
    receipt: "Quality, lineage, and audit receipts recorded",
  },
];

function completedAt(batch: ScenarioBatch): string {
  const elapsedSeconds = batch.status === "passed" ? 18 : 12;
  return new Date(new Date(batch.ingested_at).getTime() + elapsedSeconds * 1000).toISOString();
}

function runFromBatch(batch: ScenarioBatch): EvidenceRun {
  const outcome = batch.status === "passed" ? "curated" : "quarantined";
  return {
    run_id: batch.run_id,
    batch_id: batch.batch_id,
    started_at: batch.ingested_at,
    completed_at: completedAt(batch),
    status: "completed",
    outcome,
    quality_score: batch.overall_score,
    curated_rows: batch.rows_curated,
    stages: stages(outcome),
    source: "replay_fixture",
  };
}

const AUDIT_ACTION: Record<string, { action: string; category: string }> = {
  ingest: { action: "intake_received", category: "intake workflow" },
  quality: { action: "quality_gate_completed", category: "intake workflow" },
  analytics: { action: "analytics_run_completed", category: "model workflow" },
  anomaly: { action: "anomaly_recorded", category: "decision support" },
  approval: { action: "approval_state_changed", category: "approval decision" },
  export: { action: "export_state_changed", category: "controlled export" },
};

export function getReplaySystemEvidence(): SystemEvidenceResponse {
  const scenario = getScenarioState();
  const completedBatches = scenario.batches
    .filter((batch) => batch.status === "passed" || batch.status === "failed")
    .sort((a, b) => b.ingested_at.localeCompare(a.ingested_at));
  const recentRuns = completedBatches.slice(0, 8).map(runFromBatch);
  const workflowAudit: EvidenceAuditEvent[] = scenario.events.map((event) => {
    const classification = AUDIT_ACTION[event.kind] ?? {
      action: "workflow_state_changed",
      category: "workflow evidence",
    };
    return {
      event_id: event.id,
      action: classification.action,
      category: classification.category,
      detail: {
        status: "recorded",
        ...(event.org_unit ? { scope: event.org_unit } : {}),
      },
      at: event.at,
      source: "replay_fixture",
    };
  });
  const exportAudit: EvidenceAuditEvent[] = scenario.exports.map((evidence) => {
    const approval = evidence.approval_id
      ? scenario.approvals.find((candidate) => candidate.id === evidence.approval_id)
      : null;
    return {
      event_id: evidence.export_id,
      action: "controlled_export_released",
      category: "controlled export",
      detail: {
        subject_id: approval?.subject_id ?? "within_threshold",
        approval_id: evidence.approval_id ?? 0,
        matched_rows: evidence.row_count,
        row_count: evidence.row_count,
        format: evidence.format,
        requested_format: evidence.requested_format,
        approval_guard: Boolean(evidence.approval_id),
        status: "released",
      },
      at: evidence.created_at,
      source: "replay_fixture",
    };
  });
  const recentAudit = [...exportAudit, ...workflowAudit]
    .sort((a, b) => b.at.localeCompare(a.at))
    .filter(
      (event, index, all) => all.findIndex((candidate) => candidate.event_id === event.event_id) === index,
    )
    .slice(0, 8);
  const latestAnalysis = scenario.analytics_runs[0] ?? null;
  const curatedBatches = completedBatches.filter((batch) => batch.status === "passed");
  const failedBatches = completedBatches.filter((batch) => batch.status === "failed");
  const pendingApprovals = scenario.approvals.filter(
    (approval) => approval.state === "pending" && approval.expires_at > scenario.logical_now,
  );

  return {
    mode: "replay",
    evidence_class: "deterministic_synthetic_replay",
    generated_at: scenario.updated_at,
    deploy_revision: "replay-2026.08",
    correlation_id: `replay-request-${String(scenario.sequence).padStart(4, "0")}`,
    request: { method: "GET", route: "/system/evidence", status: 200, latency_ms: 42 },
    identity_decision: {
      authenticated: true,
      role: "poweruser",
      scope: "corporate portfolio",
      row_policy: "transaction scoped",
      column_policy: "role gated",
    },
    health: { status: "operational", database: "replay", projection_freshness: scenario.updated_at },
    metrics: {
      curated_records: curatedBatches.reduce((total, batch) => total + batch.rows_curated, 0),
      curated_batches: curatedBatches.length,
      open_anomalies: failedBatches.length,
      pending_approvals: pendingApprovals.length,
      audit_receipts: scenario.events.length,
    },
    services: [
      { id: "identity", label: "Identity boundary", purpose: "JWT and role resolution", status: "replay" },
      { id: "api", label: "API boundary", purpose: "Deny-by-default application routes", status: "replay" },
      { id: "data", label: "Data boundary", purpose: "Transaction-scoped row policy", status: "replay" },
      { id: "workflow", label: "Workflow boundary", purpose: "Intake and quality gate", status: "replay" },
      { id: "evidence", label: "Evidence boundary", purpose: "Audit and lineage projections", status: "replay" },
    ],
    recent_runs: recentRuns,
    recent_audit: recentAudit,
    latest_model_run: latestAnalysis
      ? {
          run_id: latestAnalysis.run_id,
          kind: "topic_model",
          status: latestAnalysis.status,
          created_at: latestAnalysis.created_at,
          metrics: {
            included_batch_count: latestAnalysis.included_batch_ids.length,
            curated_record_count: curatedBatches.reduce(
              (total, batch) => total + batch.rows_curated,
              0,
            ),
          },
          source: "replay_fixture",
        }
      : null,
    controls: [
      {
        id: "authz",
        label: "Deny-by-default authorization",
        status: "verified",
        evidence: "Poweruser and corporate scope resolved before data access",
      },
      {
        id: "rls",
        label: "Row policy context",
        status: "verified",
        evidence: "Organization scope bound to the database transaction",
      },
      {
        id: "cls",
        label: "Funding column policy",
        status: "verified",
        evidence: "Unmasked values require the corporate policy path",
      },
      {
        id: "audit",
        label: "Audit integrity",
        status: "configured",
        evidence: "System view reads a sanitized append-only projection",
      },
      {
        id: "boundary",
        label: "Demonstration data boundary",
        status: "verified",
        evidence: "Synthetic portfolio data only",
      },
    ],
    disclosure:
      "Replay mode uses deterministic synthetic evidence. Infrastructure identifiers, credentials, tokens, personal data, raw records, SQL, prompts, and exceptions are excluded.",
  };
}
