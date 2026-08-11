import assert from "node:assert/strict";
import test from "node:test";

import { exportTestSupport } from "./export";


test("replay fingerprint binds the normalized output limit", () => {
  const request = {
    format: "csv" as const,
    columns: ["grant_no", "title"],
  };
  const columns = exportTestSupport.normalizeColumns(request.columns, "viewer");
  const unlimited = exportTestSupport.normalizeFilters({ program_area: "Hypersonics" });
  const limitFive = exportTestSupport.normalizeFilters({
    program_area: "Hypersonics",
    limit: 5,
  });
  const limitSix = exportTestSupport.normalizeFilters({
    program_area: "Hypersonics",
    limit: 6,
  });

  const baseFingerprint = exportTestSupport.requestFingerprint(
    request,
    columns,
    unlimited,
    "Code-30",
  );
  const fiveFingerprint = exportTestSupport.requestFingerprint(
    request,
    columns,
    limitFive,
    "Code-30",
  );
  const sixFingerprint = exportTestSupport.requestFingerprint(
    request,
    columns,
    limitSix,
    "Code-30",
  );

  assert.notEqual(baseFingerprint, fiveFingerprint);
  assert.notEqual(fiveFingerprint, sixFingerprint);
});


test("replay limit normalization fails closed", () => {
  assert.throws(
    () => exportTestSupport.normalizeFilters({ limit: 0 }),
    /limit_must_be_positive_integer/,
  );
  assert.throws(
    () => exportTestSupport.normalizeFilters({ limit: "5" }),
    /limit_must_be_positive_integer/,
  );
});
