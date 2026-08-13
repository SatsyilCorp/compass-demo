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
    source: "USAspending.gov, Grants.gov, FederalRegister.gov, and Crossref",
    updateBehavior: "A source is called only on operator request or its responsible schedule. The browser only refreshes retained receipts.",
    tone: "public",
    nextHref: "/intelligence/",
    nextLabel: "Open public intelligence",
  },
  {
    route: "/admin/mlops/",
    element: "Element 5 of 7",
    screen: "Model operations",
    evidenceLabel: "Sanitized model evidence",
    source: "Sanitized training corpus, registered model artifacts, and AWS execution receipts",
    updateBehavior: "Model state changes only after an explicit train, evaluate, promote, deploy, or score action.",
    tone: "mixed",
    nextHref: "/dashboard/",
    nextLabel: "Continue to Element 6",
  },
  {
    route: "/admin/lineage/",
    element: "Supporting evidence",
    screen: "Operational lineage",
    evidenceLabel: "Selected run receipt",
    source: "The exact run identifier in the URL and its retained processing receipts",
    updateBehavior: "Choose a run to see its source, stages, hashes, outputs, and notifications.",
    tone: "mixed",
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
    evidenceLabel: "User-selected input",
    source: "Your submitted sanitized file, or a prepared sample whose public or synthetic status is shown before submission",
    updateBehavior: "Nothing uploads until you submit a file. Synthetic portfolio updates run only when you start them below.",
    tone: "input",
    nextHref: "/catalog/",
    nextLabel: "Continue to Element 4",
    showSyntheticStream: true,
  },
  {
    route: "/catalog/",
    element: "Element 4 of 7",
    screen: "Governed catalog",
    evidenceLabel: "Synthetic mission data",
    source: "Curated demo batches created by Element 3 ingestion",
    updateBehavior: "Rows change only after a completed demo ingestion or synthetic stream event.",
    tone: "synthetic",
    nextHref: "/admin/mlops/",
    nextLabel: "Continue to Element 5",
  },
  {
    route: "/intelligence/",
    element: "Live public evidence",
    screen: "Public portfolio intelligence",
    evidenceLabel: "Live public data",
    source: "Latest accepted snapshots from 12 named public authorities, with source URLs and capture times",
    updateBehavior: "The corpus changes after an accepted public source run, not on every browser refresh.",
    tone: "public",
    nextHref: "/dashboard/",
    nextLabel: "Return to scored demo",
  },
  {
    route: "/analytics/",
    element: "Element 5 support",
    screen: "Topic intelligence",
    evidenceLabel: "Synthetic mission data",
    source: "The active curated demo portfolio and its retained analysis run",
    updateBehavior: "Results change only when you run the analysis or change the active evidence set.",
    tone: "synthetic",
    nextHref: "/dashboard/",
    nextLabel: "Continue to Element 6",
  },
  {
    route: "/dashboard/",
    element: "Element 6 of 7",
    screen: "Decision workspace",
    evidenceLabel: "Synthetic mission data",
    source: "The active curated demo portfolio, with linked catalog, model, anomaly, and approval receipts",
    updateBehavior: "Metrics change after accepted demo ingestion, analysis, or an explicitly selected scale run.",
    tone: "synthetic",
    nextHref: "/export/",
    nextLabel: "Continue to Element 7",
  },
  {
    route: "/licenses/",
    element: "Element 4 support",
    screen: "Data vendor lifecycle",
    evidenceLabel: "Representative policy data",
    source: "Synthetic license, entitlement, renewal, and dataset relationships",
    updateBehavior: "This is a governed workflow example, not an authoritative Government license inventory.",
    tone: "synthetic",
  },
  {
    route: "/export/",
    element: "Element 7 of 7",
    screen: "Governed release",
    evidenceLabel: "Synthetic mission data",
    source: "The active curated demo portfolio and the signed-in user's approved scope",
    updateBehavior: "An export is created only after you request it and any required approval is satisfied.",
    tone: "synthetic",
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

export function screenContextForPath(pathname: string): ScreenContext {
  const normalized = normalizePath(pathname);
  return CONTEXTS.find((item) => routeMatches(normalized, item.route)) ?? FALLBACK;
}

function normalizePath(pathname: string): string {
  const withoutQuery = pathname.split("?")[0]?.split("#")[0] || "/";
  return withoutQuery.endsWith("/") ? withoutQuery : `${withoutQuery}/`;
}

function routeMatches(pathname: string, route: string): boolean {
  return pathname === route || pathname.startsWith(route);
}
