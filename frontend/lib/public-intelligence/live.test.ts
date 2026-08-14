import assert from "node:assert/strict";
import test from "node:test";

import { PUBLIC_INTELLIGENCE_SNAPSHOT } from "./demo-snapshot";
import {
  mergePublicIntelligenceSnapshot,
  parsePublicIntelligenceExplanationResponse,
  parsePublicIntelligenceSnapshotResponse,
  safeHttpsUrl,
} from "./live";
import {
  parseContinuousPublicAcquisitionControl,
  parsePublicAcquisitionList,
  parsePublicAcquisitionRecord,
} from "./acquisition-contract";

function liveSnapshot() {
  return parsePublicIntelligenceSnapshotResponse({
    contract: "compass.public-intelligence.snapshot-response.v1",
    snapshot_id: "onr-public-test",
    snapshot_version: 1,
    generated_at: "2026-08-12T12:00:00Z",
    as_of_at: "2026-08-12T11:59:00Z",
    evidence_class: "public_evidence",
    provenance: {
      manifest_sha256: "a".repeat(64),
      index_sha256: "b".repeat(64),
      manifest_object_version: "v1",
      index_object_version: "v2",
    },
    identity_scope: { role: "poweruser", org_unit: "ONR-Corporate" },
    snapshot: {
      as_of_date: "2026-08-12",
      candidate_scope: {
        grants: 13_301,
        contracts: 7_477,
        summed_award_amount_usd: 20_000_000_000,
      },
      observed_annual_obligations: [
        { fiscal_year: 2025, observed_obligations_usd: 1_500_000_000 },
      ],
    },
    sources: [
      {
        source_id: "grants_gov",
        count: 300,
        state: "persisted",
        scope: "Public ONR opportunities",
        url: "https://www.grants.gov/api",
      },
      {
        source_id: "new_public_source",
        count: 42,
        state: "persisted",
        scope: "New governed public evidence",
        url: "https://example.gov/public-source",
      },
    ],
    models: [],
    record_count: 600,
    records: [],
    disclosure: "Public evidence only.",
  });
}

test("verified live projection never inherits bundled records or model fixtures", () => {
  const live = liveSnapshot();
  assert.ok(live);
  const merged = mergePublicIntelligenceSnapshot(PUBLIC_INTELLIGENCE_SNAPSHOT, live);

  assert.equal(merged.generatedAt, "2026-08-12T12:00:00Z");
  assert.equal(merged.corpus.awards, 13_301);
  assert.equal(merged.corpus.contracts, 7_477);
  assert.equal(merged.corpus.candidateAwardValueUsd, 20_000_000_000);
  assert.deepEqual(merged.fundingFlow.map((period) => period.fiscalYear), [2025]);
  assert.equal(merged.sources.find((source) => source.id === "grants-gov")?.recordCount, 300);
  assert.equal(merged.sources.find((source) => source.id === "new-public-source")?.recordCount, 42);
  assert.equal(merged.sources.find((source) => source.id === "new-public-source")?.status, "persisted");
  assert.equal(merged.sources.length, 2);
  assert.equal(merged.programs.length, 0);
  assert.equal(merged.models.length, 0);
  assert.equal(merged.technologyAreas.length, 0);
});

test("malformed snapshot responses fail closed", () => {
  assert.equal(parsePublicIntelligenceSnapshotResponse({ contract: "wrong" }), null);
  assert.equal(
    parsePublicIntelligenceSnapshotResponse({
      contract: "compass.public-intelligence.snapshot-response.v1",
      snapshot_id: "",
    }),
    null,
  );
});

test("synthetic evidence cannot enter the live snapshot contract", () => {
  const valid = liveSnapshot();
  assert.ok(valid);
  const raw = {
    ...valid,
    evidence_class: "synthetic-demo",
  };
  assert.equal(parsePublicIntelligenceSnapshotResponse(raw), null);
  assert.equal(parsePublicIntelligenceSnapshotResponse({ ...valid, evidence_class: "observed" }), null);
});

test("accepts only live public acquisition contracts", () => {
  const run = {
    contract: "compass.public-acquisition.v1",
    evidence_class: "public-observed",
    run_id: "acq-usaspending-1",
    source_id: "usaspending-onr-grants",
    source_label: "USAspending",
    status: "completed",
    stage: "accepted-snapshot",
    started_at: "2026-08-13T20:00:00Z",
    updated_at: "2026-08-13T20:00:01Z",
    record_count: 1,
    record_preview: [{ source_record_id: "award-1", title: "Public award", source_url: "https://www.usaspending.gov/award/award-1" }],
  };
  assert.ok(parsePublicAcquisitionRecord(run));
  assert.equal(parsePublicAcquisitionRecord({ ...run, evidence_class: "synthetic-demo" }), null);

  const list = {
    contract: "compass.public-acquisition-list.v1",
    mode: "live",
    evidence_class: "public-operational",
    generated_at: "2026-08-13T20:00:02Z",
    schedule: "source-specific schedules",
    source_transport: "bounded HTTPS polling",
    source_health: [{
      source_id: "usaspending-onr-grants",
      label: "USAspending",
      authority: "USAspending.gov",
      endpoint: "https://api.usaspending.gov/api/v2/search/spending_by_award/",
      cadence_seconds: 300,
      data_kind: "Public award records",
      model_use: "Classification",
      status: "healthy",
    }],
    acquisitions: [run],
  };
  assert.ok(parsePublicAcquisitionList(list));
  assert.ok(parsePublicAcquisitionList({
    ...list,
    evidence_threads: [{
      thread_id: "thread-1",
      match_type: "explainable-candidate",
      match_score: 0.82,
      review_status: "analyst-review",
      explanation: "Public records share bounded descriptive terms.",
      shared_terms: ["autonomy"],
      owner: "Portfolio Data Product Owner",
      steward: "Public Evidence Data Steward",
      facts: [{
        source_id: "usaspending-onr-grants",
        source_label: "USAspending",
        run_id: "acq-usaspending-1",
        record_id: "award-1",
        record_type: "award",
        title: "Public award",
        source_url: null,
        document_url: null,
      }],
    }],
  }));
  assert.equal(parsePublicAcquisitionList({ ...list, mode: "replay" }), null);
  assert.equal(parsePublicAcquisitionList({ ...list, evidence_class: "synthetic-demo" }), null);
  assert.equal(parsePublicAcquisitionList({
    ...list,
    source_health: [{ ...list.source_health[0], endpoint: "https://example.com/fake-source" }],
  }), null);
});

test("continuous control requires live operational provenance", () => {
  const control = {
    contract: "compass.public-acquisition-continuous-control.v1",
    mode: "live",
    evidence_class: "public-operational",
    status: "running",
    enabled: true,
    defaulted: false,
    updated_at: "2026-08-13T20:00:00Z",
    updated_by: "poweruser",
    manual_runs_available: true,
    control_scope: "scheduled public-source acquisitions",
  };
  assert.ok(parseContinuousPublicAcquisitionControl(control));
  assert.equal(parseContinuousPublicAcquisitionControl({ ...control, mode: "replay" }), null);
  assert.equal(parseContinuousPublicAcquisitionControl({ ...control, evidence_class: "synthetic-demo" }), null);
});

test("safe source links accept HTTPS without embedded credentials", () => {
  assert.equal(safeHttpsUrl("https://www.usaspending.gov/award/example"), "https://www.usaspending.gov/award/example");
  assert.equal(safeHttpsUrl("javascript:alert(1)"), null);
  assert.equal(safeHttpsUrl("http://example.com"), null);
  assert.equal(safeHttpsUrl("https://user:secret@example.com/record"), null);
});

test("grounded explanations require a record citation and sanitize display text", () => {
  const missingCitation = parsePublicIntelligenceExplanationResponse({
    contract: "compass.public-intelligence.explanation.v1",
    answer: "Unsupported",
    grounded: true,
    refused: false,
    citations: [],
    explanation_run_id: "run-1",
    snapshot_id: "snapshot-1",
  });
  assert.equal(missingCitation, null);

  const parsed = parsePublicIntelligenceExplanationResponse({
    contract: "compass.public-intelligence.explanation.v1",
    answer: "Evidence\u2014bounded answer. [SRC:record-1]",
    grounded: true,
    refused: false,
    citations: [
      {
        record_id: "record-1",
        source_id: "usaspending",
        title: "Public record",
        source_url: "https://example.gov/record-1",
        evidence_class: "observed",
        snapshot_id: "snapshot-1",
        record_sha256: "c".repeat(64),
        citation_token: "[SRC:record-1]",
      },
    ],
    evidence_class: "observed",
    model_run_ids: [],
    explanation_run_id: "run-2",
    uncertainty: { level: "source-bounded", basis: "Public records only.", limitations: [] },
    generation: { provider: "deterministic", model_id: null, usage: null },
    snapshot_id: "snapshot-1",
    identity_scope: { role: "poweruser", org_unit: "ONR-Corporate" },
  });

  assert.ok(parsed);
  assert.equal(parsed.answer.includes("\u2014"), false);
  assert.equal(parsed.citations.length, 1);

  const ungroundedButNotRefused = parsePublicIntelligenceExplanationResponse({
    ...parsed,
    grounded: false,
    refused: false,
  });
  assert.equal(ungroundedButNotRefused, null);

  const validRefusal = parsePublicIntelligenceExplanationResponse({
    ...parsed,
    grounded: false,
    refused: true,
    refusal_code: "INSUFFICIENT_CITABLE_EVIDENCE",
    citations: [],
    evidence_class: "none",
  });
  assert.ok(validRefusal);
});
