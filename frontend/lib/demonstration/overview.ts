import type { EvidenceMode } from "../evidence-mode";

export type DemoOverviewElement = {
  title: string;
  label: string;
  source: string;
  changes: string;
  action: string;
  href: string;
  evidence: "identity" | "control" | "public" | "rehearsal";
};

export type DemoOverviewModel = {
  heroTitle: string;
  heroBody: string;
  pathKicker: string;
  pathTitle: string;
  pathLead: string;
  pathBadge: string;
  sourceCountValue: string;
  sourceCountLabel: string;
  boundaryKicker: string;
  boundaryTitle: string;
  boundaryBody: string;
  elements: Record<number, DemoOverviewElement>;
};

const LIVE_ELEMENTS: Record<number, DemoOverviewElement> = {
  1: {
    title: "Secure access",
    label: "Identity evidence",
    source: "The signed-in Cognito identity and role mapping",
    changes: "Only when a user signs in or their approved role changes",
    action: "Authenticate a named user and show protected scope and policy behavior.",
    href: "/login/",
    evidence: "identity",
  },
  2: {
    title: "IaC and CI/CD",
    label: "Control evidence",
    source: "GitHub, Terraform, SAM, policy checks, and retained CI/CD artifacts",
    changes: "Only when a reviewed commit moves through the delivery path",
    action: "Walk through source revision, infrastructure definitions, delivery gates, and any retained runtime proof.",
    href: "/admin/delivery/",
    evidence: "control",
  },
  3: {
    title: "Live public acquisition",
    label: "Live public acquisition",
    source: "The current deployed public-source registry through protected AWS connectors",
    changes: "At each source-safe backend poll, or after an operator requests a bounded pull",
    action: "Inspect continuous source control and follow one accepted authority receipt through quality and classification.",
    href: "/ingest/",
    evidence: "public",
  },
  4: {
    title: "Governance and lineage",
    label: "Governed public evidence",
    source: "Exact accepted records, source pages, hashes, quality results, and lineage receipts",
    changes: "After a source run passes policy, quality, and identity checks",
    action: "Open an accepted source product and trace its hashes, quality, model, and lineage evidence.",
    href: "/catalog/",
    evidence: "public",
  },
  5: {
    title: "Model and decide",
    label: "Real model receipts",
    source: "Public Navy SBIR training data, verified classifier receipts, and conditional SageMaker execution receipts when available",
    changes: "After a governed public batch is classified, scored, or evaluated for drift",
    action: "Inspect champion classifier evidence, bounded model execution, registry state, and drift controls.",
    href: "/admin/mlops/",
    evidence: "public",
  },
  6: {
    title: "Executive workspace",
    label: "Live public intelligence",
    source: "Accepted cross-source records, exact evidence identities, model outputs, and cited explanations",
    changes: "When the retained public snapshot changes or the user changes the decision view",
    action: "Review changed records, citations, model flags, and the linked operational lineage.",
    href: "/dashboard/",
    evidence: "public",
  },
  7: {
    title: "Portable browser preview",
    label: "Browser-generated preview",
    source: "The accepted bounded public record previews already loaded in the signed-in browser",
    changes: "Only after the user explicitly downloads a local JSON or CSV preview",
    action: "Create the portable preview, inspect its source fields and local checksum, and confirm that no server release, approval, delivery, or audit receipt was created.",
    href: "/export/",
    evidence: "public",
  },
};

const REHEARSAL_ELEMENTS: Record<number, DemoOverviewElement> = {
  1: {
    title: "Secure rehearsal access",
    label: "Identity and scope",
    source: "The signed-in identity and its approved synthetic-data scope",
    changes: "Only when the user or approved role changes",
    action: "Show the named persona, scoped fixture rows, funding masking, and deny-by-default policy.",
    href: "/login/",
    evidence: "identity",
  },
  2: {
    title: "IaC and CI/CD controls",
    label: "Control artifacts",
    source: "Source-controlled IaC, CI policy, and retained delivery artifacts",
    changes: "Only when a reviewed commit changes the delivery definition or retained proof",
    action: "Inspect IaC and CI controls while distinguishing retained artifacts from runtime fixture evidence.",
    href: "/admin/delivery/",
    evidence: "control",
  },
  3: {
    title: "Synthetic intake",
    label: "Synthetic intake rehearsal",
    source: "A user-selected sanitized fixture processed by deterministic rehearsal adapters",
    changes: "Only after the presenter submits a fixture or starts the isolated rehearsal stream",
    action: "Submit a prepared synthetic file and follow deterministic quality, quarantine, and publication stages.",
    href: "/rehearsal/ingest/",
    evidence: "rehearsal",
  },
  4: {
    title: "Fixture governance and lineage",
    label: "Synthetic governance proof",
    source: "The selected fixture batch, source hash, quality score, schema, and rehearsal lineage receipts",
    changes: "After an explicit rehearsal intake completes or is quarantined",
    action: "Open the synthetic catalog batch and trace its quality inputs and run-bound lineage.",
    href: "/rehearsal/catalog/",
    evidence: "rehearsal",
  },
  5: {
    title: "Rehearsal model lifecycle",
    label: "Deterministic model rehearsal",
    source: "Synthetic training fixtures, portable classifier logic, model version, metrics, and drift scenarios",
    changes: "Only after an explicit rehearsal train, score, promotion, or drift action",
    action: "Exercise deterministic classification, metrics, registry, promotion, and drift without claiming cloud execution.",
    href: "/admin/mlops/",
    evidence: "rehearsal",
  },
  6: {
    title: "Synthetic decision workspace",
    label: "Synthetic decision workspace",
    source: "The active curated fixture portfolio with linked catalog, model, anomaly, and approval receipts",
    changes: "After explicit rehearsal ingestion, analysis, filtering, or scale selection",
    action: "Filter the synthetic portfolio, inspect cited fixture records, and rehearse one approval exception.",
    href: "/rehearsal/dashboard/",
    evidence: "rehearsal",
  },
  7: {
    title: "Rehearsal release",
    label: "Rehearsal release receipt",
    source: "The scoped synthetic portfolio and deterministic export fingerprint",
    changes: "Only after an explicit rehearsal release and any required approval",
    action: "Trigger release controls and inspect the fingerprint, approval, and audit receipt without claiming delivery.",
    href: "/rehearsal/export/",
    evidence: "rehearsal",
  },
};

export function demoOverviewForMode(mode: EvidenceMode): DemoOverviewModel {
  if (mode === "rehearsal") {
    return {
      heroTitle: "One explicit rehearsal story from fixture to decision",
      heroBody: "Present Elements 1 through 7 using isolated deterministic fixtures. Every quality, lineage, model, decision, and release result remains labeled as rehearsal evidence and changes only after an explicit user action.",
      pathKicker: "Explicit rehearsal path",
      pathTitle: "Scored seven-element synthetic workflow rehearsal",
      pathLead: "Each step names its fixture source, trigger, and evidence boundary before you open it.",
      pathBadge: "Synthetic rehearsal is active",
      sourceCountValue: "0",
      sourceCountLabel: "External source calls",
      boundaryKicker: "Rehearsal boundary active",
      boundaryTitle: "Deterministic fixtures and repeatable scenario data",
      boundaryBody: "This workspace exercises the product workflow without representing authority responses, cloud model execution, operational decisions, or delivered release objects. Return to the primary evidence layer when current protected receipts are required.",
      elements: REHEARSAL_ELEMENTS,
    };
  }

  return {
    heroTitle: "One live public story from source to decision",
    heroBody: "Present Elements 1 through 7 in order using accepted records from named public authorities. Compass pulls them in AWS at source-safe cadences, projects retained events to the browser in near real time, and keeps every quality, lineage, model, and decision receipt connected.",
    pathKicker: "Primary live product path",
    pathTitle: "Scored seven-element public evidence demonstration",
    pathLead: "Each step names the exact source and retained proof before you open it.",
    pathBadge: "Live public evidence is primary",
    sourceCountValue: "API",
    sourceCountLabel: "Registry verified at runtime",
    boundaryKicker: "Optional rehearsal fallback",
    boundaryTitle: "Synthetic files and deterministic scenario data",
    boundaryBody: "Enter the separate rehearsal workspace only when public sources are unavailable or the evaluator asks to exercise a controlled failure. Rehearsal is never selected automatically, never appears as live, and cannot silently replace an unavailable public request.",
    elements: LIVE_ELEMENTS,
  };
}
