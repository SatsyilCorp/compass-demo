import assert from "node:assert/strict";
import test from "node:test";

import { PUBLIC_INTELLIGENCE_SNAPSHOT } from "./demo-snapshot";
import {
  mergePublicIntelligenceSnapshot,
  parsePublicIntelligenceExplanationResponse,
  parsePublicIntelligenceSnapshotResponse,
  safeHttpsUrl,
} from "./live";

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

test("verified live summary fields replace matching bundled values", () => {
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
});
