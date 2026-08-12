import assert from "node:assert/strict";
import test from "node:test";

import { PUBLIC_INTELLIGENCE_SNAPSHOT as snapshot } from "./demo-snapshot";
import {
  COLLECTED_PUBLIC_RECORD_COUNT,
  COLLECTED_PUBLIC_SOURCE_COUNT,
  SOURCE_ACQUISITION_GROUPS,
} from "./source-acquisition";

const EXPECTED_PERSISTED_SOURCE_COUNTS = new Map([
  ["usaspending", 20_776],
  ["sbir", 27_887],
  ["grants-gov", 286],
  ["sam_gov", 5],
  ["datacite", 498],
  ["crossref", 48_747],
  ["openalex", 68_912],
  ["pubmed", 1_595],
  ["osti", 3_010],
  ["uspto-patents", 5_388],
  ["federal-register", 91],
  ["onr-website", 308],
]);

test("bundled public source ledger matches the accepted 2026-08-12 corpus", () => {
  const persisted = snapshot.sources.filter((source) => source.status === "persisted");
  const actual = new Map(persisted.map((source) => [source.id, source.recordCount]));

  assert.equal(snapshot.asOfDate, "2026-08-12");
  assert.deepEqual(actual, EXPECTED_PERSISTED_SOURCE_COUNTS);
  assert.equal(persisted.length, 12);
  assert.equal(
    persisted.reduce((total, source) => total + (source.recordCount ?? 0), 0),
    177_503,
  );
  assert.equal(snapshot.sources.find((source) => source.id === "dtic")?.status, "gated");
});

test("public intelligence headline values match the persisted USAspending summary", () => {
  assert.equal(snapshot.corpus.awards, 13_300);
  assert.equal(snapshot.corpus.contracts, 7_476);
  assert.equal(snapshot.corpus.candidateAwardValueUsd, 19_260_405_492.79);

  const usaspending = snapshot.sources.find((source) => source.id === "usaspending");
  assert.equal(usaspending?.recordCount, 20_776);
  assert.match(usaspending?.use ?? "", /candidate scope/i);
  assert.match(usaspending?.use ?? "", /not an authoritative inventory/i);
});

test("public intelligence shows only persisted annual obligations", () => {
  assert.equal(snapshot.fundingFlow.length, 19);
  assert.equal(snapshot.fundingFlow[0]?.observedUsd, 1_007_249_559.99);
  assert.equal(snapshot.fundingFlow.at(-1)?.observedUsd, 912_973_221.97);
  assert.equal(snapshot.fundingFlow.at(-1)?.isPartial, true);
  assert.ok(snapshot.fundingFlow.every((period) => period.forecastUsd === null));
  assert.ok(snapshot.fundingFlow.every((period) => period.lowerUsd === null));
  assert.ok(snapshot.fundingFlow.every((period) => period.upperUsd === null));
});

test("measured funding and transition candidates are shown while other predictions remain unavailable", () => {
  assert.equal(snapshot.technologyAreas.length, 0);
  assert.ok(snapshot.programs.every((program) => program.transitionProbability === null));
  assert.ok(snapshot.programs.every((program) => program.impactPercentile === null));
  assert.ok(snapshot.programs.every((program) => program.confidence === null));
  assert.equal(snapshot.sources.find((source) => source.id === "sbir")?.recordCount, 27_887);
  assert.equal(snapshot.sources.find((source) => source.id === "grants-gov")?.recordCount, 286);
  assert.equal(snapshot.sources.find((source) => source.id === "datacite")?.recordCount, 498);
  const pubmed = snapshot.sources.find((source) => source.id === "pubmed");
  assert.equal(pubmed?.recordCount, 1_595);
  assert.equal(pubmed?.status, "persisted");
  assert.match(pubmed?.use ?? "", /researcher identities.*abstract text.*omitted/i);
  const patents = snapshot.sources.find((source) => source.id === "uspto-patents");
  assert.equal(patents?.recordCount, 5_388);
  assert.equal(patents?.status, "persisted");
  assert.match(patents?.use ?? "", /exact Office of Naval Research.*N00014/i);
  assert.match(patents?.use ?? "", /People, addresses, abstracts.*omitted/i);
  const funding = snapshot.models.find((model) => model.id === "funding-forecast");
  assert.equal(funding?.status, "candidate");
  assert.equal(funding?.trainingRecords, 71);
  assert.equal(funding?.metricValue, 125_392_976.37);
  const transition = snapshot.models.find((model) => model.id === "transition");
  assert.equal(transition?.status, "candidate");
  assert.equal(transition?.trainingRecords, 11_287);
  assert.equal(transition?.metricValue, 0.62642675);
  assert.match(transition?.caveat ?? "", /network-isolated SageMaker job/i);
  assert.match(transition?.caveat ?? "", /PendingManualApproval/i);
  assert.match(transition?.caveat ?? "", /not ONR mission success/i);
  assert.ok(snapshot.models.filter((model) => !["funding-forecast", "transition"].includes(model.id)).every((model) => model.status === "not-trained"));
});

test("source acquisition inventory separates collected, gated, and excluded evidence", () => {
  const persisted = snapshot.sources.filter((source) => source.status === "persisted");
  assert.equal(persisted.length, COLLECTED_PUBLIC_SOURCE_COUNT);
  assert.equal(
    persisted.reduce((total, source) => total + (source.recordCount ?? 0), 0),
    COLLECTED_PUBLIC_RECORD_COUNT,
  );

  assert.deepEqual(
    SOURCE_ACQUISITION_GROUPS.map((group) => group.state),
    ["collected_public", "gated_commercial", "gated_government", "excluded"],
  );
  assert.match(SOURCE_ACQUISITION_GROUPS[1]?.boundary ?? "", /no licensed commercial records/i);
  assert.match(SOURCE_ACQUISITION_GROUPS[2]?.boundary ?? "", /no live Advana, Pulse/i);
  assert.match(SOURCE_ACQUISITION_GROUPS[3]?.boundary ?? "", /protected attachments.*not fetched/i);
});
