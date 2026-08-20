// Flag-on static-build smoke for the single-mode presentation.
// Usage:
//   NEXT_PUBLIC_SINGLE_MODE=true NEXT_PUBLIC_AUTH_DISABLED=true pnpm build
//   node scripts/single-mode-smoke.mjs
// Serves out/ and asserts: key routes render, rehearsal UI is absent,
// /rehearsal/* deep-loads redirect, and seeded rehearsal storage is inert.
import { spawn } from "node:child_process";
import { chromium } from "@playwright/test";

const PORT = 4199;
const BASE = `http://127.0.0.1:${PORT}`;
const ROUTES = [
  "/", "/login/", "/admin/delivery/", "/ingest/", "/catalog/", "/admin/mlops/", "/dashboard/", "/export/",
  "/admin/architecture/", "/admin/demo/", "/admin/scale/",
  "/admin/acquisition/?mode=demo",
];
const FORBIDDEN = [
  "Persistent evidence mode",
  "Rehearsal landing",
  "Explicitly enter rehearsal",
  "Open synthetic rehearsal",
  "Switch the acting persona",
  "Act as",
  "Synthetic rehearsal now has its own boundary",
  "Enter the separate rehearsal workspace",
  "Activate rehearsal",
  "Open rehearsal boundary",
  "until the operator selects rehearsal",
];

const server = spawn("python3", ["-m", "http.server", String(PORT), "--directory", "out"], { stdio: "ignore" });
await new Promise((r) => setTimeout(r, 1200));

let failures = 0;
const fail = (msg) => { failures += 1; console.error("FAIL:", msg); };
const ok = (msg) => console.log("ok  :", msg);

const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  // Seed both persisted keys - the shipped bundle must ignore them.
  await page.addInitScript(() => {
    window.localStorage.setItem("compass.evidence-mode.v1", "rehearsal");
    window.localStorage.setItem("compass:rehearsal-persona:v1", "viewer");
  });

  for (const route of ROUTES) {
    await page.goto(BASE + route, { waitUntil: "networkidle" });
    const body = await page.locator("body").innerText();
    if (body.trim().length < 40) fail(`${route} rendered almost nothing`);
    for (const term of FORBIDDEN) {
      if (body.includes(term)) fail(`${route} still shows "${term}"`);
    }
    ok(`${route} clean`);
  }

  for (const [from, to] of [["/rehearsal/", "/"], ["/rehearsal/dashboard/", "/dashboard/"], ["/rehearsal/export/", "/export/"]]) {
    await page.goto(BASE + from, { waitUntil: "networkidle" });
    await page.waitForTimeout(600);
    const path = new URL(page.url()).pathname;
    if (path === to) ok(`${from} redirected to ${to}`);
    else fail(`${from} landed on ${path}, expected ${to}`);
  }

  // Seeded rehearsal storage must be inert: no rehearsal banner anywhere.
  await page.goto(BASE + "/dashboard/", { waitUntil: "networkidle" });
  const text = await page.locator("body").innerText();
  if (/Explicit synthetic rehearsal/i.test(text)) fail("seeded storage reactivated rehearsal");
  else ok("seeded rehearsal storage is inert");
} finally {
  await browser.close();
  server.kill();
}

if (failures) { console.error(`\n${failures} failure(s)`); process.exit(1); }
console.log("\nSINGLE-MODE SMOKE PASS");
