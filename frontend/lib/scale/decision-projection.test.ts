import assert from "node:assert/strict";
import test from "node:test";

import { buildScaleDecisionProjection } from "./decision-projection";
import type { ScaleRun } from "./types";

function scaleRun(overrides: Partial<ScaleRun> = {}): ScaleRun {
  const run: ScaleRun = {
    run_id: "scale-test-1m",
    mode: "live",
    status: "completed",
    created_at: "2026-08-11T09:42:00Z",
    started_at: "2026-08-11T09:42:01Z",
    updated_at: "2026-08-11T09:43:15Z",
    completed_at: "2026-08-11T09:43:15Z",
    cancelled_at: null,
    plan: {
      plan_id: "plan-test-1m",
      profile_id: "1m",
      seed: 20_260_811,
      generated_at: "2026-08-11T09:41:59Z",
      capacity_state: "ready",
      total_records: 1_000_000,
      estimated_raw_bytes: 1_400_000_000,
      target_duration_seconds: 120,
      concurrency_limit: 6,
      partition_count: 41,
      dataset_mix: [],
      stages: [],
      cost: {
        currency: "USD",
        estimated_run_usd: 0.13937136,
        upper_bound_usd: 10,
        incremental_idle_monthly_usd: 0,
        pricing_as_of: "2026-08-11",
        estimate_source: "aws_price_model",
        disclaimer: "Estimate only",
        line_items: [],
      },
    },
    progress: {
      stage: "evidence",
      percent: 100,
      records_generated: 1_000_000,
      records_ingested: 1_000_000,
      records_curated: 989_852,
      records_quarantined: 10_148,
      bytes_written: 88_000_000,
      partitions_completed: 41,
      partitions_total: 41,
      current_throughput_rps: 0,
      peak_throughput_rps: 31_250.5,
      elapsed_seconds: 73,
      eta_seconds: 0,
    },
    quality: {
      overall_score: 98.98,
      passed_records: 989_852,
      failed_records: 10_148,
      quarantined_records: 10_148,
      rules: [],
    },
    costs: {
      currency: "USD",
      estimated_run_usd: 0.13937136,
      upper_bound_usd: 10,
      incremental_idle_monthly_usd: 0,
      pricing_as_of: "2026-08-11",
      estimate_source: "aws_price_model",
      disclaimer: "Estimate only",
      line_items: [],
      accrued_usd: 0.05309299,
    },
    intelligence: {
      status: "completed",
      model_run_id: "intelligence-test",
      grants_analyzed: 200_000,
      topic_count: 6,
      anomalies_detected: 137_852,
      processing_seconds: 14,
      top_topics: [],
    },
    export_receipt: {
      export_id: "export-test",
      status: "ready",
      format: "parquet",
      row_count: 989_852,
      bytes: 44_000_000,
      object_uri: "lake://scale-runs/scale-test-1m/exports/export-test/manifest",
      download_url: null,
      expires_at: "2026-08-18T09:43:15Z",
      sha256: "a".repeat(64),
    },
    evidence: {
      correlation_id: "corr-test",
      audit_receipt: "audit-test",
      manifest_uri: "lake://scale-runs/scale-test-1m/manifest",
      manifest_sha256: "b".repeat(64),
      metrics_recorded_at: "2026-08-11T09:43:15Z",
      recovery_queue_depth: 0,
      duplicate_records_suppressed: 0,
      stages: [],
    },
    error: null,
  };
  return { ...run, ...overrides };
}

test("completed receipt becomes an honest Scale decision projection", () => {
  const projection = buildScaleDecisionProjection(scaleRun());

  assert.equal(projection.state, "completed");
  assert.equal(projection.recordContext, "1,000,000 synthetic records");
  assert.equal(projection.grantsAnalyzed, 200_000);
  assert.equal(projection.qualityScore, 98.98);
  assert.equal(projection.quarantinedRecords, 10_148);
  assert.equal(projection.anomalyLinkedRecords, 137_852);
  assert.equal(projection.partitions, "41 of 41");
  assert.equal(projection.peakThroughput, "31,251 records/sec");
  assert.equal(projection.accruedCost, "$0.0531");
  assert.match(projection.proof.title, /1,000,000/);
  assert.match(projection.exceptions.detail, /aggregate findings/i);
  assert.match(projection.recommendation.detail, /Scale Lab/i);
  assert.doesNotMatch(JSON.stringify(projection), /funding|citation|row-level/i);
});

test("active receipt remains a progress decision context", () => {
  const base = scaleRun();
  const projection = buildScaleDecisionProjection(scaleRun({
    status: "quality",
    completed_at: null,
    progress: {
      ...base.progress,
      stage: "quality",
      percent: 72,
      partitions_completed: 29,
      records_generated: 720_000,
      records_ingested: 720_000,
      records_curated: 0,
      records_quarantined: 0,
      eta_seconds: 35,
    },
    quality: {
      ...base.quality,
      overall_score: 0,
      passed_records: 0,
      failed_records: 0,
      quarantined_records: 0,
    },
    intelligence: {
      ...base.intelligence,
      status: "pending",
      grants_analyzed: 0,
      anomalies_detected: 0,
    },
  }));

  assert.equal(projection.state, "running");
  assert.equal(projection.statusLabel, "Applying quality gates");
  assert.match(projection.proof.title, /72%/);
  assert.equal(projection.recommendation.title, "Wait for terminal evidence");
  assert.match(projection.recommendation.detail, /follow live progress/i);
});

test("failed receipt directs the operator to failure evidence", () => {
  const projection = buildScaleDecisionProjection(scaleRun({
    status: "failed",
    error: {
      code: "partition_processing_exhausted",
      message: "One bounded partition exhausted its retries.",
      retryable: true,
    },
  }));

  assert.equal(projection.state, "failed");
  assert.equal(projection.proof.tone, "danger");
  assert.equal(projection.recordContext, "1,000,000 generated records recorded before failure");
  assert.equal(projection.proof.title, "Scale Run stopped in a failed state");
  assert.equal(projection.recommendation.title, "Inspect failure evidence");
  assert.match(projection.recommendation.detail, /failure evidence only/i);
  assert.doesNotMatch(
    JSON.stringify({
      recordContext: projection.recordContext,
      proof: projection.proof,
      recommendation: projection.recommendation,
    }),
    /\bcomplete(?:d)?\b|\bsealed\b/i,
  );
});

test("queued receipt labels every unavailable measure as pending", () => {
  const base = scaleRun();
  const projection = buildScaleDecisionProjection(scaleRun({
    status: "queued",
    started_at: null,
    completed_at: null,
    progress: {
      ...base.progress,
      stage: "plan",
      percent: 0,
      records_generated: 0,
      records_ingested: 0,
      records_curated: 0,
      records_quarantined: 0,
      bytes_written: 0,
      partitions_completed: 0,
      current_throughput_rps: 0,
      peak_throughput_rps: 0,
      elapsed_seconds: 0,
      eta_seconds: 120,
    },
    quality: {
      ...base.quality,
      overall_score: 0,
      passed_records: 0,
      failed_records: 0,
      quarantined_records: 0,
    },
    costs: { ...base.costs, accrued_usd: 0 },
    intelligence: {
      ...base.intelligence,
      status: "pending",
      grants_analyzed: 0,
      topic_count: 0,
      anomalies_detected: 0,
      processing_seconds: null,
    },
  }));

  assert.equal(projection.recordContext, "Synthetic records pending");
  assert.equal(projection.grantsAnalyzed, "Pending");
  assert.equal(projection.qualityScore, "Pending");
  assert.equal(projection.quarantinedRecords, "Pending");
  assert.equal(projection.anomalyLinkedRecords, "Pending");
  assert.equal(projection.partitions, "Pending");
  assert.equal(projection.peakThroughput, "Pending");
  assert.equal(projection.accruedCost, "Pending");
  assert.doesNotMatch(projection.proof.title, /0|1,000,000/);
});

test("cancelled receipt never presents 100 percent progress as success", () => {
  const projection = buildScaleDecisionProjection(scaleRun({
    status: "cancelled",
    cancelled_at: "2026-08-11T09:43:15Z",
  }));

  assert.equal(projection.state, "cancelled");
  assert.equal(projection.recordContext, "1,000,000 generated records recorded before cancellation");
  assert.equal(projection.proof.title, "Scale Run was cancelled");
  assert.equal(projection.proof.tone, "warn");
  assert.equal(projection.recommendation.title, "Inspect cancellation evidence");
  assert.doesNotMatch(
    JSON.stringify({
      recordContext: projection.recordContext,
      proof: projection.proof,
      recommendation: projection.recommendation,
    }),
    /\bcomplete(?:d)?\b|\bsealed\b/i,
  );
});

test("terminal failure without measured stages uses unavailable, not zero", () => {
  const base = scaleRun();
  const projection = buildScaleDecisionProjection(scaleRun({
    status: "failed",
    progress: {
      ...base.progress,
      percent: 100,
      records_generated: 0,
      records_ingested: 0,
      records_curated: 0,
      records_quarantined: 0,
      bytes_written: 0,
      partitions_completed: 0,
      peak_throughput_rps: 0,
    },
    quality: {
      ...base.quality,
      overall_score: 0,
      passed_records: 0,
      failed_records: 0,
      quarantined_records: 0,
    },
    costs: { ...base.costs, accrued_usd: 0 },
    intelligence: {
      ...base.intelligence,
      status: "pending",
      grants_analyzed: 0,
      topic_count: 0,
      anomalies_detected: 0,
      processing_seconds: null,
    },
  }));

  assert.equal(projection.recordContext, "Synthetic record count unavailable");
  assert.equal(projection.grantsAnalyzed, "Unavailable");
  assert.equal(projection.qualityScore, "Unavailable");
  assert.equal(projection.quarantinedRecords, "Unavailable");
  assert.equal(projection.anomalyLinkedRecords, "Unavailable");
  assert.equal(projection.partitions, "Unavailable");
  assert.equal(projection.peakThroughput, "Unavailable");
  assert.equal(projection.accruedCost, "Unavailable");
  assert.equal(projection.exceptions.title, "Exception metrics unavailable");
  assert.doesNotMatch(JSON.stringify(projection.exceptions), /\b0\b|no anomaly-linked/i);
});
