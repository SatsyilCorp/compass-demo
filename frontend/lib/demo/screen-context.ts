import { DEFAULT_EVIDENCE_MODE, type EvidenceMode } from "../evidence-mode";

export type ScreenEvidenceTone = "guide" | "control" | "input" | "synthetic" | "public" | "mixed";

export type ScreenContext = {
  route: string;
  element: string;
  screen: string;
  evidenceLabel: string;
  source: string;
  updateBehavior: string;
  tone: ScreenEvidenceTone;
  nextHref?: string;
  nextLabel?: string;
  showSyntheticStream?: boolean;
};

const CONTEXTS: ScreenContext[] = [
  {
    route: "/rehearsal/",
    element: "Evidence mode boundary",
    screen: "Rehearsal landing",
    evidenceLabel: "Explicit mode selection",
    source: "A user-selected deterministic synthetic evidence boundary",
    updateBehavior: "Rehearsal does not start until the user explicitly activates it on this page or in the application shell.",
    tone: "guide",
    nextHref: "/admin/demo/",
    nextLabel: "Open rehearsal guide",
  },
  {
    route: "/admin/demo/",
    element: "Start here",
    screen: "Guided demonstration",
    evidenceLabel: "Demo guide",
    source: "Seven scored elements and two clearly separated evidence lanes",
    updateBehavior: "This page explains the path. It does not create or change data.",
    tone: "guide",
    nextHref: "/admin/delivery/",
    nextLabel: "Begin Element 2",
  },
  {
    route: "/admin/delivery/",
    element: "Element 2 of 7",
    screen: "IaC and DevSecOps",
    evidenceLabel: "Control evidence",
    source: "GitHub source, Terraform, SAM, security policy, and retained CI/CD artifacts",
    updateBehavior: "The screen describes commit-bound controls. It is not mission data.",
    tone: "control",
    nextHref: "/ingest/",
    nextLabel: "Continue to Element 3",
  },
  {
    route: "/admin/acquisition/",
    element: "Live public evidence",
    screen: "Public source operations",
    evidenceLabel: "Live public data",
    source: "The deployed, protected public-source registry and its current authority receipts",
    updateBehavior: "A source is called only on operator request or its responsible schedule. The browser only refreshes retained receipts.",
    tone: "public",
    nextHref: "/intelligence/",
    nextLabel: "Open public intelligence",
  },
  {
    route: "/admin/mlops/",
    element: "Element 5 of 7",
    screen: "Model operations",
    evidenceLabel: "Live model receipts",
    source: "Accepted public narratives, champion-classifier receipts, model registry evidence, and protected SageMaker execution receipts",
    updateBehavior: "Public classifier evidence changes after accepted source runs. Training, promotion, drift, and Batch Transform state change only after an explicit protected action.",
    tone: "public",
    nextHref: "/dashboard/",
    nextLabel: "Continue to Element 6",
  },
  {
    route: "/admin/lineage/",
    element: "Supporting evidence",
    screen: "Operational lineage",
    evidenceLabel: "Protected live run receipt",
    source: "The exact public acquisition, file intake, model, or release run identifier and its retained AWS processing receipts",
    updateBehavior: "Choose a run to see its source, stages, hashes, outputs, and notifications.",
    tone: "public",
  },
  {
    route: "/admin/requirements/",
    element: "Demo package",
    screen: "Requirements trace",
    evidenceLabel: "Traceability map",
    source: "Demo requirements mapped to user actions, screens, code, proof, and caveats",
    updateBehavior: "This page is explanatory and does not create mission records.",
    tone: "guide",
  },
  {
    route: "/admin/architecture/",
    element: "Supporting evidence",
    screen: "Architecture",
    evidenceLabel: "Proposed design and deployed proof",
    source: "Repository infrastructure definitions plus retained AWS deployment evidence",
    updateBehavior: "Select a component to separate deployed, configured, and proposed capabilities.",
    tone: "control",
  },
  {
    route: "/admin/scale/",
    element: "Supporting evidence",
    screen: "Workload evidence lab",
    evidenceLabel: "Synthetic scale data",
    source: "Generated non-sensitive records from a selected, retained scale run",
    updateBehavior: "The active mission dataset changes only when you explicitly select a completed run.",
    tone: "synthetic",
  },
  {
    route: "/admin/pipeline/",
    element: "Supporting evidence",
    screen: "Mission control",
    evidenceLabel: "Operational receipts",
    source: "Retained workflow, service, cost, and deployment status from the prototype environment",
    updateBehavior: "Status refreshes from protected prototype service endpoints.",
    tone: "control",
  },
  {
    route: "/catalog/lineage/",
    element: "Element 4 of 7",
    screen: "Dataset lineage",
    evidenceLabel: "Synthetic mission workflow",
    source: "The selected curated demo dataset and its originating ingestion run",
    updateBehavior: "The graph changes when the selected dataset or originating run changes.",
    tone: "synthetic",
    nextHref: "/admin/mlops/",
    nextLabel: "Continue to Element 5",
  },
  {
    route: "/ingest/",
    element: "Element 3 of 7",
    screen: "File and stream intake",
    evidenceLabel: "Live public sources and operator input",
    source: "The deployed public-source registry or a user-submitted public and PII-minimized file",
    updateBehavior: "AWS schedules continue until an operator stops them. The screen refreshes retained receipts, while a file changes the system only after an explicit upload.",
    tone: "public",
    nextHref: "/catalog/",
    nextLabel: "Continue to Element 4",
  },
  {
    route: "/catalog/",
    element: "Element 4 of 7",
    screen: "Governed catalog",
    evidenceLabel: "Accepted public source products",
    source: "Latest accepted public acquisition receipts with source hashes, identity keys, governance, model versions, and source links",
    updateBehavior: "Rows change after a public source page or public file completes quality, classification, and governed publication.",
    tone: "public",
    nextHref: "/admin/mlops/",
    nextLabel: "Continue to Element 5",
  },
  {
    route: "/intelligence/",
    element: "Live public evidence",
    screen: "Public portfolio intelligence",
    evidenceLabel: "Live public data",
    source: "Latest accepted snapshots from the deployed public-source registry, with source URLs and capture times",
    updateBehavior: "The corpus changes after an accepted public source run, not on every browser refresh.",
    tone: "public",
    nextHref: "/dashboard/",
    nextLabel: "Return to scored demo",
  },
  {
    route: "/analytics/",
    element: "Element 5 support",
    screen: "Topic intelligence",
    evidenceLabel: "Live public model analytics",
    source: "Latest accepted public-source deltas, record previews, transparent review rules, and champion classifier receipts",
    updateBehavior: "Charts update from new accepted source receipts. They never estimate the complete ONR portfolio.",
    tone: "public",
    nextHref: "/dashboard/",
    nextLabel: "Continue to Element 6",
  },
  {
    route: "/dashboard/",
    element: "Element 6 of 7",
    screen: "Decision workspace",
    evidenceLabel: "Live public decision evidence",
    source: "Accepted public-source receipts, observed preview values, model results, change counts, source health, and analyst review flags",
    updateBehavior: "Metrics change when AWS accepts a new source snapshot. Failed pulls leave the prior accepted snapshot visible with an operator alert.",
    tone: "public",
    nextHref: "/export/",
    nextLabel: "Continue to Element 7",
  },
  {
    route: "/licenses/",
    element: "Element 4 support",
    screen: "Data vendor lifecycle",
    evidenceLabel: "Live public source contracts",
    source: "The deployed public connector registry plus retained health, cadence, owner, steward, and downstream model use",
    updateBehavior: "Operational health changes with source runs. Access-basis and governance fields change through reviewed configuration.",
    tone: "public",
  },
  {
    route: "/export/",
    element: "Element 7 of 7",
    screen: "Portable browser preview",
    evidenceLabel: "Browser-generated public preview",
    source: "The latest accepted bounded public records already loaded in the browser, with acquisition, source, model, review, and lineage fields",
    updateBehavior: "A local JSON or CSV file and checksum are created only after the user requests them. No protected approval, delivery, audit record, or server receipt is created.",
    tone: "public",
    nextHref: "/admin/demo/",
    nextLabel: "Return to demo guide",
  },
];

const FALLBACK: ScreenContext = {
  route: "/",
  element: "Compass prototype",
  screen: "Supporting workspace",
  evidenceLabel: "Screen-specific evidence",
  source: "See the page description and retained receipt before relying on any value",
  updateBehavior: "Every operational result must identify its source and evidence class.",
  tone: "mixed",
  nextHref: "/admin/demo/",
  nextLabel: "Open demo guide",
};

export function screenContextForPath(
  pathname: string,
  evidenceMode: EvidenceMode = DEFAULT_EVIDENCE_MODE,
): ScreenContext {
  const normalized = normalizePath(pathname);
  const routedPath = normalized !== "/rehearsal/" && normalized.startsWith("/rehearsal/")
    ? normalizePath(normalized.slice("/rehearsal".length))
    : normalized;
  const context = CONTEXTS.find((item) => routeMatches(routedPath, item.route)) ?? FALLBACK;
  return applyEvidenceModeBoundary(context, evidenceMode);
}

function applyEvidenceModeBoundary(context: ScreenContext, evidenceMode: EvidenceMode): ScreenContext {
  if (evidenceMode === "live" && context.tone === "synthetic") {
    return {
      ...context,
      evidenceLabel: "Live mode, no synthetic fallback",
      source: "Protected live service responses only. Rehearsal fixtures are disabled in the current evidence mode.",
      updateBehavior: "If live evidence is unavailable, this screen must show unavailable or an error. It must never load synthetic records automatically.",
      tone: "public",
      showSyntheticStream: false,
    };
  }
  if (evidenceMode === "rehearsal" && context.tone === "public") {
    const fixedPublicSnapshot = context.route === "/intelligence/";
    const releaseRehearsal = context.route === "/export/";
    return {
      ...context,
      screen: releaseRehearsal ? "Governed release rehearsal" : context.screen,
      evidenceLabel: fixedPublicSnapshot ? "Fixed non-live public snapshot" : releaseRehearsal ? "Explicit synthetic release rehearsal" : "Explicit synthetic rehearsal",
      source: fixedPublicSnapshot ? "A fixed public evidence package retained for deterministic presentation rehearsal" : "Deterministic fixtures isolated from public-source, production, and operational evidence",
      updateBehavior: fixedPublicSnapshot ? "This snapshot does not refresh or call public APIs. Return to live mode for current protected receipts." : releaseRehearsal ? "Approval, audit, and receipt behavior is a deterministic rehearsal. It does not claim a live cloud file was delivered." : "Rehearsal changes only after an explicit user action and every result remains labeled synthetic.",
      tone: "synthetic",
      showSyntheticStream: context.route === "/ingest/",
    };
  }
  return context;
}

function normalizePath(pathname: string): string {
  const withoutQuery = pathname.split("?")[0]?.split("#")[0] || "/";
  return withoutQuery.endsWith("/") ? withoutQuery : `${withoutQuery}/`;
}

function routeMatches(pathname: string, route: string): boolean {
  return pathname === route || pathname.startsWith(route);
}
