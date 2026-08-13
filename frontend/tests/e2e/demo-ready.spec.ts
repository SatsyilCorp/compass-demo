import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

const ROUTES = [
  "/",
  "/ingest/",
  "/catalog/",
  "/analytics/",
  "/dashboard/",
  "/export/",
  "/licenses/",
  "/admin/demo/",
  "/admin/requirements/",
  "/admin/acquisition/",
  "/admin/architecture/",
  "/admin/mlops/",
  "/admin/scale/",
  "/admin/pipeline/",
];

test("Scale Lab previews, launches, proves, and exports a bounded workload", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "full Scale Lab workflow runs once on desktop");

  await page.goto("/admin/scale/");
  await expect(page.getByRole("heading", { name: "Scale Lab" })).toBeVisible();
  await expect(page.getByText("Cost-gated execution contract", { exact: true })).toBeVisible();
  await page.getByLabel("Deterministic seed").fill("424242");
  await page.getByRole("button", { name: "Preview" }).click();
  await expect(page.getByText("10,000", { exact: true }).first()).toBeVisible();
  await page.getByRole("button", { name: "Launch exact plan" }).click();

  await expect(page.getByText(/^scale-replay-\d+$/).first()).toBeVisible();
  await expect(page.getByText("Completed", { exact: true }).first()).toBeVisible({ timeout: 12_000 });
  await expect(page.getByText("Final evidence sealed", { exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "Evidence" }).click();
  await expect(page.getByText("Correlation chain", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Cost" }).click();
  await expect(page.getByText("Hard ceiling", { exact: true }).first()).toBeVisible();
  await page.getByRole("tab", { name: "Intelligence" }).click();
  await expect(page.getByText("Autonomous maritime systems", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "Export receipt" }).click();
  await page.getByRole("button", { name: "Build governed export" }).click();
  await expect(page.getByRole("link", { name: "Download release receipt" })).toBeVisible({ timeout: 5_000 });

  await page.getByRole("button", { name: "Data" }).click();
  await page.getByRole("button", { name: /Quality and quarantine/ }).click();
  await expect(page.getByText("Every rejected record is counted and quarantined with rule-level reasons.", { exact: true })).toBeVisible();

  await page.getByRole("link", { name: "Unified decision workspace", exact: true }).click();
  await expect(page).toHaveURL(/\/dashboard\/$/);
  await expect(page.getByText("Scale run decision context", { exact: true })).toBeVisible();
  await expect(page.getByText("10,000 synthetic records", { exact: true })).toBeVisible();
  await expect(page.getByText("2,000", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("400 grants across 8 program areas", { exact: true })).toHaveCount(0);

  await page.getByRole("button", { name: "Use curated baseline" }).first().click();
  await expect(page.getByText("Curated demo", { exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Decision workspace" })).toBeVisible();
  await expect(page.getByText("Scale run decision context", { exact: true })).toHaveCount(0);
});

test.beforeEach(async ({ page }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
});

test("continuous synthetic ingestion advances until the operator stops it", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "continuous stream workflow runs once on desktop");

  await page.goto("/dashboard/");
  await expect(page.getByText("Curated demo", { exact: true })).toBeVisible();
  await page.getByLabel("Synthetic stream cadence").selectOption("1");
  await page.getByRole("button", { name: "Start live updates" }).click();

  await expect(page.getByText("Updating now", { exact: true })).toBeVisible();
  await expect(page.getByText(/1 new record/)).toBeVisible({ timeout: 4_000 });

  await page.getByRole("button", { name: "Stop live updates" }).click();
  await expect(page.getByText("Updates stopped", { exact: true })).toBeVisible();
});

test("the demo sequence stays explicit and alerts use the full viewport", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "desktop navigation and alert drawer run once");

  await page.goto("/dashboard/");
  const navigation = page.getByRole("navigation");
  for (const label of ["IaC and DevSecOps", "Ingestion and DataOps", "Governance and catalog", "Decision analytics and MLOps", "Unified decision workspace", "Interoperability and export"]) {
    await expect(navigation.getByRole("link", { name: label, exact: false })).toBeVisible();
  }
  await expect(navigation.getByRole("link", { name: "Architecture", exact: true })).toBeHidden();
  await expect(page.getByText("Demo package", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("Demo evidence and supporting analysis", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: "Demo requirements", exact: true })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Items needing review" })).toBeVisible();
  await expect(page.getByText("An anomaly is a record that looks different from similar records.", { exact: false })).toBeVisible();

  await page.getByRole("button", { name: /Open alerts/ }).click();
  const dialog = page.getByRole("dialog", { name: "Alerts and activity" });
  await expect(dialog).toBeVisible();
  const coverage = await dialog.evaluate((element) => element.getBoundingClientRect().height / window.innerHeight);
  expect(coverage).toBeGreaterThan(0.9);
  await expect(dialog.getByText("Why it matters", { exact: true }).first()).toBeVisible();
  await expect(dialog.getByText("Recommended action", { exact: true }).first()).toBeVisible();
});

for (const route of ROUTES) {
  test(`${route} has a visible heading, no horizontal overflow, and no serious accessibility defects`, async ({ page }) => {
    await page.goto(route);
    const heading = page.getByRole("heading", { level: 1 }).first();
    await expect(heading).toBeVisible();

    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);

    const result = await new AxeBuilder({ page }).analyze();
    const blocking = result.violations.filter((violation) =>
      violation.impact === "critical" || violation.impact === "serious",
    );
    expect(blocking, JSON.stringify(blocking, null, 2)).toEqual([]);
  });
}

test("mission control distinguishes replay evidence from workflow definition", async ({ page }) => {
  await page.goto("/admin/pipeline/");
  await expect(page.getByText("Replay fixture", { exact: true })).toBeVisible();
  await expect(page.getByText("Backend evidence stream", { exact: true })).toBeVisible();
  await expect(page.getByText("Decision trace", { exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "Control receipts" }).click();
  await expect(page.getByText("Sanitized audit readback", { exact: true })).toBeVisible();

  await page.getByRole("tab", { name: "Workflow definition" }).click();
  await expect(page.getByText("Definition view", { exact: true })).toBeVisible();
  await expect(page.getByText("Runtime policy levers", { exact: true })).toBeVisible();
});

test("architecture explorer maps services and explains production scale flow", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "interactive architecture flow runs once on desktop");

  await page.goto("/admin/architecture/");
  await expect(page.getByRole("heading", { name: "AWS architecture and VPC map" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Six views. One accountable system." })).toBeVisible();
  await expect(page.getByRole("heading", { name: "10.42.0.0/16 across two availability zones" })).toBeVisible();
  await expect(page.getByText("Public subnet A", { exact: true })).toBeVisible();
  await expect(page.getByText("Private subnet B", { exact: true })).toBeVisible();
  await expect(page.getByText("TCP 5432 from application SG only", { exact: true })).toBeVisible();
  await page.getByRole("tab", { name: "IL4/IL5 target boundary" }).click();
  await expect(page.getByRole("heading", { name: "Government boundary services surround a private mission enclave" })).toBeVisible();
  await expect(page.getByText("Target architecture only.", { exact: false }).first()).toBeVisible();
  await page.getByRole("tab", { name: "Data lineage" }).click();
  await expect(page.getByRole("heading", { name: "Every accepted record keeps its origin and every rejected record keeps its reason" })).toBeVisible();

  await page.getByText("Open the full deployed topology, scale playback, and component inventory", { exact: true }).click();
  await expect(page.getByRole("heading", { name: "Deployed AWS-native proving prototype" })).toBeVisible();
  await expect(page.getByText("This is not a FedRAMP High, IL5, ATO, or Government production authorization.", { exact: false })).toBeVisible();
  await expect(page.getByText(/boxes mapped/)).toBeVisible();

  await page.getByRole("tab", { name: "Production scale" }).click();
  await page.getByRole("radio", { name: "1M profile, 41 partitions" }).check();
  await expect(page.getByRole("group", { name: "Records: 1,000,000" })).toBeVisible();
  await expect(page.getByRole("group", { name: "Peak throughput: 16,667 rec/s" })).toBeVisible();

  await page.getByLabel("Scale Plan and Run Gate, AWS Lambda Scale Control").click();
  await expect(page.getByText("The Scale Run Module exposes the narrow plan, launch, status, cancel, and export interface.", { exact: true })).toBeVisible();
  await expect(page.getByText("How it scales", { exact: true })).toBeVisible();
  await expect(page.getByText("Security boundary", { exact: true })).toBeVisible();

  await page.getByRole("button", { name: "Show scale stage 5: Generate and gate" }).click();
  await expect(page.getByText("Generate and gate", { exact: true })).toBeVisible();

  await page.getByPlaceholder("Find a service, role, or control").fill("Macie");
  await expect(page.getByText("1 of", { exact: false })).toBeVisible();
  await expect(page.getByText("Sensitive-data discovery", { exact: true })).toBeVisible();
});

test("demo command center walks the scored sequence and strategic prompts", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "interactive command center flow runs once on desktop");

  await page.goto("/admin/requirements/");
  await expect(page.getByRole("heading", { name: "Requirement proof and presenter path" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Tell one evidence chain in 18 minutes" })).toBeVisible();
  await expect(page.getByText("5 stops | 12 asks", { exact: true })).toBeVisible();

  await page.getByPlaceholder("Search an ask, screen, API, source, or caveat").fill("Real model lifecycle");
  await expect(page.getByRole("heading", { name: "Real model lifecycle" })).toBeVisible();
  await expect(page.getByText("1 of 12 shown", { exact: true })).toBeVisible();
  await expect(page.getByRole("link", { name: /Model operations/ })).toBeVisible();

  await page.getByLabel("Evidence state").selectOption("target-architecture");
  await expect(page.getByText("No matching demo ask", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Clear filters" }).click();
  await expect(page.getByRole("heading", { name: "IL4/IL5 target" })).toBeVisible();
});

test("model operations refuses to present replay or registry evidence as an execution", async ({ page }) => {
  await page.goto("/admin/mlops/");
  await expect(page.getByRole("heading", { name: "Execute the registered candidate" })).toBeVisible();
  await expect(page.getByText("Replay mode cannot claim cloud execution", { exact: true })).toBeVisible();
  await expect(page.getByText("No execution receipt in this session", { exact: true })).toBeVisible();
  await expect(page.getByText("Registry evidence is not execution evidence", { exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Execute candidate now" })).toBeDisabled();
});

test("a completed ingest appears in the shared System Inspector evidence", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "full workflow runs once on desktop");

  await page.goto("/ingest/");
  await page.getByRole("button", { name: "Reset replay" }).click();
  await page.getByRole("button", { name: "Clean batch" }).click();

  const batchId = page.getByText(/^batch-replay-clean-\d+$/).first();
  await expect(batchId).toBeVisible();
  const batchRow = page.locator("li").filter({ has: batchId });
  await expect(batchRow.getByText("Curated", { exact: true })).toBeVisible({ timeout: 5_000 });
  const createdBatchId = (await batchId.textContent())!;

  await page.goto("/admin/pipeline/");
  await expect(page.getByText(createdBatchId, { exact: true })).toBeVisible();
  await expect(page.getByText("48 rows", { exact: false })).toBeVisible();
});

test("dashboard filters and viewer scope change the decision projection", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "full workflow runs once on desktop");

  await page.goto("/dashboard/");
  await page.getByText("Demo evidence and supporting analysis", { exact: true }).click();
  await page.getByLabel("Search portfolio").fill("hypersonic");
  await page.getByRole("button", { name: "Apply view" }).click();
  await expect(page.getByText(/3 grants across 2 program areas/i)).toBeVisible();

  await page.getByLabel("Active demo persona").selectOption("viewer");
  await expect(page.getByLabel("Organization")).toBeDisabled();
  await expect(page.getByLabel("Organization")).toHaveValue("Code-30");
  await expect(page.getByText("Funding values protected", { exact: true })).toBeVisible();
});

test("independent approval clears the exact export once and rejects reuse", async ({ page, context }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "two-session workflow runs once on desktop");

  await page.goto("/ingest/");
  await page.getByRole("button", { name: "Reset replay" }).click();
  await page.getByLabel("Active demo persona").selectOption("viewer");
  await page.goto("/export/");

  await page.getByRole("button", { name: "Run export" }).click();
  await expect(page.getByText("HTTP 428: approval required", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Request approval" }).click();
  await expect(page.getByText("Approval record", { exact: true })).toBeVisible();

  const reviewer = await context.newPage();
  await reviewer.goto("/export/");
  await reviewer.getByLabel("Active demo persona").selectOption("poweruser");
  await reviewer.getByRole("button", { name: "Refresh inbox" }).click();
  await expect(reviewer.getByText("Shared review queue", { exact: true })).toBeVisible();
  await reviewer.getByRole("button", { name: "Approve", exact: true }).click();
  await expect(reviewer.getByText("Decision approved", { exact: true })).toBeVisible();
  const token = await reviewer.locator("#approval-handoff-token").inputValue();
  expect(token).toMatch(/^apr-[1-9]\d*\.[A-Za-z0-9_-]{43}$/);

  await page.bringToFront();
  await page.locator("#requester-approval-token").fill(token);
  await page.getByRole("button", { name: "Retry exact export" }).click();
  await expect(page.getByText("Export released", { exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Verify one-time use" }).click();
  await expect(page.getByText(/Single-use control verified/)).toBeVisible();
});

test("viewer cannot open the shared analytics workspace", async ({ page }, testInfo) => {
  test.skip(testInfo.project.name !== "desktop-chromium", "role redirect runs once on desktop");

  await page.goto("/dashboard/");
  await page.getByLabel("Active demo persona").selectOption("viewer");
  await page.goto("/analytics/");
  await expect(page).toHaveURL(/\/dashboard\/$/);
  await expect(page.getByRole("heading", { name: "What is happening now" })).toBeVisible();
});

test("keyboard users can bypass navigation and reach page content", async ({ page }) => {
  await page.goto("/dashboard/");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: /skip/i });
  await expect(skip).toBeFocused();
  await skip.press("Enter");
  await expect(page.locator("main")).toBeFocused();
});
