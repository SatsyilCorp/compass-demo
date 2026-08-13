import assert from "node:assert/strict";
import test from "node:test";

import type { Anomaly } from "../../lib/types";
import { explainAnomaly, friendlyAnomalyKind } from "./anomaly-explanation";

const funding: Anomaly = {
  id: 7,
  grant_id: 41,
  grant_no: "ONR-TEST-041",
  title: "Autonomous sensing",
  program_area: "Autonomy",
  org_unit: "Code-31",
  kind: "funding_zscore",
  severity: "high",
  reason: "amount $9,500,000 is +3.4 std devs from the Autonomy mean",
  status: "open",
  created_at: "2026-08-13T12:00:00.000Z",
};

test("funding anomaly is explained as a review prompt rather than a conclusion", () => {
  const explanation = explainAnomaly(funding);
  assert.equal(friendlyAnomalyKind(funding.kind), "Unusual funding amount");
  assert.match(explanation.whatHappened, /ONR-TEST-041/);
  assert.match(explanation.whyItMatters, /may be completely valid/i);
  assert.match(explanation.recommendedAction, /compare/i);
  assert.doesNotMatch(explanation.whyItMatters, /fraud|failure/i);
});

test("quality anomaly explains that publication was safely blocked", () => {
  const explanation = explainAnomaly({
    ...funding,
    kind: "structured_quality",
    grant_no: undefined,
    reason: "Required fields were missing.",
  });
  assert.equal(friendlyAnomalyKind("structured_quality"), "Data quality issue");
  assert.match(explanation.whyItMatters, /not published/i);
  assert.match(explanation.recommendedAction, /correct/i);
});

test("common portfolio checks name the exact issue and a concrete review action", () => {
  const cases = [
    ["duplicate_grant_no", "Possible duplicate record", /compare both records/i],
    ["missing_abstract", "Missing document summary", /open the source document/i],
    ["org_unit_mismatch", "Organization does not match", /confirm the owning organization/i],
    ["fiscal_year_drift", "Fiscal year needs confirmation", /confirm the fiscal year/i],
  ] as const;

  for (const [kind, label, action] of cases) {
    const explanation = explainAnomaly({ ...funding, kind });
    assert.equal(friendlyAnomalyKind(kind), label);
    assert.equal(explanation.title, label);
    assert.match(explanation.recommendedAction, action);
  }
});
