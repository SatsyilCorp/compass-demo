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
  "/admin/requirements/",
  "/admin/architecture/",
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

  await page.getByRole("link", { name: /Unified decision workspace/ }).click();
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
  await expect(page.getByRole("heading", { name: "Architecture Explorer" })).toBeVisible();
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
  await expect(page.getByRole("heading", { name: "Technical Demonstration Command Center" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Seven demonstration elements" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Five mandatory strategic prompts" })).toBeVisible();

  await page.getByRole("tab", { name: /Element 5 Model and decide/ }).click();
  await expect(page.getByRole("heading", { name: "Decision-Support Analytics and Modeling" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Open Model operations" })).toBeVisible();
  await expect(page.getByText("The classifier uses sanitized synthetic documents", { exact: false })).toBeVisible();

  await page.getByRole("button", { name: "Zero Trust and Cybersecurity Compliance" }).click();
  await expect(page.getByText("Continuously evaluate source, dependencies, IaC, STIG policy", { exact: false })).toBeVisible();
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
  await expect(page.getByRole("heading", { name: "Decision workspace" })).toBeVisible();
});

test("keyboard users can bypass navigation and reach page content", async ({ page }) => {
  await page.goto("/dashboard/");
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: /skip/i });
  await expect(skip).toBeFocused();
  await skip.press("Enter");
  await expect(page.locator("main")).toBeFocused();
});
