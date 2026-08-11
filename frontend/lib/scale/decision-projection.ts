import { formatCount, formatCurrency } from "./format";
import type { ScaleRun } from "./types";

export type ScaleDecisionCard = {
  eyebrow: "What this run proved" | "Exceptions" | "Recommended next action";
  title: string;
  detail: string;
  tone: "info" | "success" | "warn" | "danger";
};

export type ScaleDecisionProjection = {
  state: "running" | "completed" | "failed" | "cancelled";
  runId: string;
  recordContext: string;
  grantsAnalyzed: number | "Pending" | "Unavailable";
  qualityScore: number | "Pending" | "Unavailable";
  quarantinedRecords: number | "Pending" | "Unavailable";
  anomalyLinkedRecords: number | "Pending" | "Unavailable";
  partitions: string;
  peakThroughput: string;
  accruedCost: string;
  progressPercent: number;
  statusLabel: string;
  proof: ScaleDecisionCard;
  exceptions: ScaleDecisionCard;
  recommendation: ScaleDecisionCard;
};

function projectionState(status: ScaleRun["status"]): ScaleDecisionProjection["state"] {
  if (status === "completed") return "completed";
  if (status === "failed") return "failed";
  if (status === "cancelled") return "cancelled";
  return "running";
}

function statusLabel(run: ScaleRun): string {
  const labels: Record<ScaleRun["status"], string> = {
    queued: "Queued",
    generating: "Generating synthetic records",
    ingesting: "Ingesting bounded partitions",
    quality: "Applying quality gates",
    intelligence: "Building aggregate intelligence",
    exporting: "Building governed export",
    cancelling: "Cancellation requested",
    cancelled: "Cancelled",
    completed: "Completed",
    failed: "Failed",
  };
  return labels[run.status];
}

export function buildScaleDecisionProjection(run: ScaleRun): ScaleDecisionProjection {
  const state = projectionState(run.status);
  const total = formatCount(run.plan.total_records);
  const pending = state === "running" ? "Pending" as const : "Unavailable" as const;
  const qualityMeasured = state === "completed" || run.quality.passed_records + run.quality.failed_records > 0;
  const intelligenceMeasured = run.intelligence.status === "completed" || (
    run.intelligence.status === "running" && run.intelligence.grants_analyzed > 0
  );
  const grantsAnalyzed = intelligenceMeasured ? run.intelligence.grants_analyzed : pending;
  const qualityScore = qualityMeasured ? run.quality.overall_score : pending;
  const quarantinedRecords = qualityMeasured ? run.quality.quarantined_records : pending;
  const anomalyLinkedRecords = intelligenceMeasured ? run.intelligence.anomalies_detected : pending;
  const partitions = state === "completed" || run.progress.partitions_completed > 0
    ? `${formatCount(run.progress.partitions_completed)} of ${formatCount(run.progress.partitions_total)}`
    : pending;
  const peakThroughput = run.progress.peak_throughput_rps > 0
    ? `${formatCount(run.progress.peak_throughput_rps)} records/sec`
    : pending;
  const accruedCost = run.costs.accrued_usd > 0
    ? formatCurrency(run.costs.accrued_usd)
    : pending;
  const generated = formatCount(run.progress.records_generated);
  const recordContext = state === "completed"
    ? `${total} synthetic records`
    : state === "failed" && run.progress.records_generated > 0
      ? `${generated} generated records recorded before failure`
      : state === "cancelled" && run.progress.records_generated > 0
        ? `${generated} generated records recorded before cancellation`
        : run.progress.records_generated > 0
          ? `${generated} synthetic records generated so far`
          : state === "running"
            ? "Synthetic records pending"
            : "Synthetic record count unavailable";
  const anomalyCount = typeof anomalyLinkedRecords === "number"
    ? formatCount(anomalyLinkedRecords)
    : anomalyLinkedRecords;
  const quarantineCount = typeof quarantinedRecords === "number"
    ? formatCount(quarantinedRecords)
    : quarantinedRecords;
  const partitionOutcome = partitions === "Unavailable"
    ? "No partition outcome was reported"
    : partitions === "Pending"
      ? "Partition outcomes are pending"
      : `${partitions} partitions reported worker outcomes`;

  let proof: ScaleDecisionCard;
  if (state === "completed") {
    proof = {
      eyebrow: "What this run proved",
      title: `${total} records completed through the bounded data path`,
      detail: `${partitions} partitions completed with ${run.quality.overall_score.toFixed(2)} quality confidence and a sealed run receipt.`,
      tone: "success",
    };
  } else if (state === "failed") {
    proof = {
      eyebrow: "What this run proved",
      title: "Scale Run stopped in a failed state",
      detail: `${partitionOutcome} before orchestration failed. Partial measures remain failure evidence only.`,
      tone: "danger",
    };
  } else if (state === "cancelled") {
    proof = {
      eyebrow: "What this run proved",
      title: "Scale Run was cancelled",
      detail: `${partitionOutcome} before cancellation. Partial measures remain cancellation evidence only.`,
      tone: "warn",
    };
  } else if (run.progress.percent > 0) {
    proof = {
      eyebrow: "What this run proved",
      title: `${run.progress.percent}% of the bounded run is in progress`,
      detail: `${partitionOutcome} while ${statusLabel(run).toLowerCase()}.`,
      tone: "info",
    };
  } else {
    proof = {
      eyebrow: "What this run proved",
      title: "Run evidence is pending",
      detail: "The bounded plan is queued. No measured corpus, quality, or intelligence receipt is available yet.",
      tone: "info",
    };
  }

  let exceptions: ScaleDecisionCard;
  if (anomalyLinkedRecords === "Pending" && quarantinedRecords === "Pending") {
    exceptions = {
      eyebrow: "Exceptions",
      title: "Exception metrics pending",
      detail: "Quality and intelligence findings will appear after their measured receipt stages run.",
      tone: "info",
    };
  } else if (anomalyLinkedRecords === "Unavailable" && quarantinedRecords === "Unavailable") {
    exceptions = {
      eyebrow: "Exceptions",
      title: "Exception metrics unavailable",
      detail: "The run ended before quality and intelligence measurements were produced.",
      tone: state === "failed" ? "danger" : "warn",
    };
  } else {
    const anomalyTitle = typeof anomalyLinkedRecords === "number"
      ? anomalyLinkedRecords > 0
        ? `${anomalyCount} anomaly-linked records detected`
        : "No anomaly-linked records detected"
      : anomalyLinkedRecords === "Pending"
        ? "Anomaly metric pending"
        : "Anomaly metric unavailable";
    const quarantineDetail = typeof quarantinedRecords === "number"
      ? `${quarantineCount} records were quarantined. These are aggregate findings recorded by the run, not a workflow disposition queue.`
      : quarantinedRecords === "Pending"
        ? "Quarantine findings are pending. Available values remain aggregate run evidence only."
        : "Quarantine findings were not produced before the run ended. Available values remain aggregate run evidence only.";
    const hasMeasuredException = (
      typeof anomalyLinkedRecords === "number" && anomalyLinkedRecords > 0
    ) || (
      typeof quarantinedRecords === "number" && quarantinedRecords > 0
    );

    exceptions = {
      eyebrow: "Exceptions",
      title: anomalyTitle,
      detail: quarantineDetail,
      tone: state === "failed"
        ? "danger"
        : state === "cancelled" || hasMeasuredException
          ? "warn"
          : state === "completed"
            ? "success"
            : "info",
    };
  }

  const recommendationByState: Record<ScaleDecisionProjection["state"], Pick<ScaleDecisionCard, "title" | "detail">> = {
    completed: {
      title: "Inspect the governed evidence",
      detail: "Open Scale Lab to inspect quality rules, cost evidence, intelligence coverage, and the export receipt.",
    },
    running: {
      title: "Wait for terminal evidence",
      detail: "Open Scale Lab to follow live progress. Use this decision context only after the run reaches a terminal state.",
    },
    failed: {
      title: "Inspect failure evidence",
      detail: "Open Scale Lab to review the failure receipt and recovery state. Partial values are failure evidence only.",
    },
    cancelled: {
      title: "Inspect cancellation evidence",
      detail: "Open Scale Lab to review the cancellation receipt. Partial values are cancellation evidence only.",
    },
  };
  const recommendation: ScaleDecisionCard = {
    eyebrow: "Recommended next action",
    ...recommendationByState[state],
    tone: "info",
  };

  return {
    state,
    runId: run.run_id,
    recordContext,
    grantsAnalyzed,
    qualityScore,
    quarantinedRecords,
    anomalyLinkedRecords,
    partitions,
    peakThroughput,
    accruedCost,
    progressPercent: run.progress.percent,
    statusLabel: statusLabel(run),
    proof,
    exceptions,
    recommendation,
  };
}
