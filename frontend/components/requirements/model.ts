import type { OperationsRunSummary, OperationsSummaryResponse } from "@/lib/types";

export const TRACE_STATUSES = [
  "verified-live",
  "configured",
  "target-architecture",
  "external-dependency",
  "not-yet-implemented",
] as const;

export type TraceStatus = (typeof TRACE_STATUSES)[number];

export type EvidenceTarget = {
  kind: "screen" | "api";
  label: string;
  locator: string;
  href?: string;
};

export type RequirementLocators = {
  source: string[];
  tests: string[];
  iac: string[];
};

export type RequirementTrace = {
  id: string;
  title: string;
  intent: string;
  status: TraceStatus;
  userAction: string;
  liveEvidence: EvidenceTarget[];
  locators: RequirementLocators;
  differentiator: string;
  caveat: string;
  tags: string[];
};

export type PresenterStep = {
  order: number;
  title: string;
  duration: string;
  instruction: string;
  href: string;
  requirementIds: string[];
};

export const STATUS_META: Record<TraceStatus, {
  label: string;
  shortLabel: string;
  description: string;
}> = {
  "verified-live": {
    label: "Verified live",
    shortLabel: "Live",
    description: "A protected screen or API can return current deployment evidence. The attached caveat still applies.",
  },
  configured: {
    label: "Configured",
    shortLabel: "Configured",
    description: "Source and infrastructure are configured, but this screen has not received a current live acceptance receipt.",
  },
  "target-architecture": {
    label: "Target architecture",
    shortLabel: "Target",
    description: "The design is documented for a future authorization boundary. It is not the state of this commercial demo deployment.",
  },
  "external-dependency": {
    label: "External dependency",
    shortLabel: "Dependency",
    description: "Compass has an integration seam, but an outside subscription, platform, or Government service is required to complete the proof.",
  },
  "not-yet-implemented": {
    label: "Not yet implemented",
    shortLabel: "Not built",
    description: "The requested behavior has no accepted live receipt yet. Do not present it as working.",
  },
};

export const REQUIREMENTS: RequirementTrace[] = [
  {
    id: "governed-intake-quality",
    title: "Governed intake and quality",
    intent: "Acquire real public records through named connectors, bind the exact source response to a run, apply quality policy, and publish or quarantine each bounded collection with a retained receipt.",
    status: "configured",
    userAction: "Open Live source operations, inspect a completed public pull, and follow its source receipt, hash, quality result, model classification, change set, and accepted watermark. Use file upload only from the explicit rehearsal workspace.",
    liveEvidence: [
      { kind: "screen", label: "Live source operations", locator: "/admin/acquisition/", href: "/admin/acquisition/" },
      { kind: "api", label: "Public acquisition receipt", locator: "GET /public-intelligence/acquisitions | POST /public-intelligence/sources/{source_id}/run" },
    ],
    locators: {
      source: ["frontend/components/documents/document-drop-zone.tsx", "src/functions/document_ml/app.py"],
      tests: ["src/functions/document_ml/tests/test_app.py", "frontend/lib/documents/document-intake.test.ts"],
      iac: ["template.yaml: DocumentObjectCreatedRule and DocumentMlStateMachine"],
    },
    differentiator: "The source authority, retrieval time, run ID, source SHA-256, quality outcome, model result, and consumer projection remain bound to the same evidence chain.",
    caveat: "The live plane accepts bounded public, PII-minimized evidence only. The separate rehearsal workspace accepts sanitized files. Neither path may receive CUI, controlled technical data, or direct PII.",
    tags: ["public connector", "structured", "unstructured", "quality", "quarantine", "rehearsal"],
  },
  {
    id: "catalog-metadata",
    title: "Catalog and metadata",
    intent: "Expose governed datasets, field definitions, quality, freshness, ownership, and source context through one searchable catalog.",
    status: "configured",
    userAction: "Open Governed catalog, expand one accepted public dataset, and point to its authority, field definitions, freshness, quality score, source run, model receipt, and owner.",
    liveEvidence: [
      { kind: "screen", label: "Governed catalog", locator: "/catalog/", href: "/catalog/" },
      { kind: "api", label: "Public catalog contract", locator: "GET /public-intelligence/acquisitions | GET /public-intelligence/snapshot" },
    ],
    locators: {
      source: ["src/functions/catalog/app.py", "frontend/components/catalog/catalog-table.tsx"],
      tests: ["frontend/tests/e2e/demo-ready.spec.ts", "src/functions/export/tests/test_openapi_routes.py"],
      iac: ["template.yaml: CatalogFunction and Glue catalog resources"],
    },
    differentiator: "Metadata is tied to operational quality and lineage evidence instead of being a detached inventory page.",
    caveat: "The live catalog covers the bounded public records accepted by Compass. External enterprise catalogs need metadata connectors and Government-approved access. Rehearsal assets remain visibly separate.",
    tags: ["catalog", "dictionary", "freshness", "ownership"],
  },
  {
    id: "lineage",
    title: "Lineage",
    intent: "Trace a specific public acquisition from the external authority through immutable retention, normalization, quality, identity linkage, model version, accepted snapshot, and consuming screen.",
    status: "configured",
    userAction: "From an accepted public source run, open end-to-end lineage and inspect the authority URI, retrieval time, source and output hashes, quality stages, model version, identity keys, watermark, and receipt locator.",
    liveEvidence: [
      { kind: "screen", label: "Public run lineage", locator: "/admin/lineage/?run={run_id}", href: "/admin/lineage/" },
      { kind: "api", label: "Cross-workflow lineage", locator: "GET /operations/lineage/{runId}" },
    ],
    locators: {
      source: ["src/functions/operations/app.py", "frontend/components/catalog/lineage-view.tsx"],
      tests: ["src/functions/operations/tests/test_app.py", "frontend/tests/e2e/demo-ready.spec.ts"],
      iac: ["template.yaml: OperationsTable, document workflow, and intake workflow"],
    },
    differentiator: "Lineage is built from stage receipts and hashes produced by execution, not from a diagram-only claim.",
    caveat: "Public authority lineage begins at the retrieved public response. Enterprise lineage stops at the Compass boundary until Databricks, Advana, or another external catalog supplies its own metadata events.",
    tags: ["provenance", "hash", "receipt", "run"],
  },
  {
    id: "decision-analytics",
    title: "Decision analytics",
    intent: "Turn governed portfolio and document evidence into filterable decisions, anomalies, projections, and cited explanations.",
    status: "configured",
    userAction: "Open Decision workspace, confirm Live public evidence, apply a source, program, or fiscal-year filter, inspect a cross-source signal, and follow its citations back to accepted authority records.",
    liveEvidence: [
      { kind: "screen", label: "Decision workspace", locator: "/dashboard/", href: "/dashboard/" },
      { kind: "api", label: "Decision projection", locator: "GET /dashboard | GET /public-intelligence/snapshot" },
    ],
    locators: {
      source: ["src/functions/dashboard/app.py", "frontend/components/dashboard/dashboard-view.tsx"],
      tests: ["src/functions/dashboard/tests/test_dashboard_filters.py", "frontend/lib/public-intelligence/live.test.ts"],
      iac: ["template.yaml: DashboardFunction and PublicIntelligenceFunction"],
    },
    differentiator: "The consumer view keeps citations, access scope, data mode, and originating run visible beside the decision signal.",
    caveat: "The default results use bounded public evidence. Rehearsal results appear only after explicit selection. All results are decision-support signals, not authoritative ONR conclusions or autonomous decisions.",
    tags: ["dashboard", "anomaly", "forecast", "citations"],
  },
  {
    id: "real-model-lifecycle",
    title: "Real model lifecycle",
    intent: "Train, evaluate, register, approve, deploy, and execute a governed model with immutable dataset, source, artifact, and metric receipts.",
    status: "configured",
    userAction: "Open Model operations, show the public Navy SBIR training manifest and SageMaker candidate, then score a bounded current public cohort and inspect each returned prediction and lineage receipt.",
    liveEvidence: [
      { kind: "screen", label: "Model operations", locator: "/admin/mlops/", href: "/admin/mlops/" },
      { kind: "api", label: "Model registry and execution", locator: "GET /ml/models | POST /public-intelligence/model-executions" },
    ],
    locators: {
      source: ["mlops/sagemaker/public_sbir_transition/train.py", "src/functions/public_intelligence/model_execution.py"],
      tests: ["mlops/sagemaker/public_sbir_transition/test_submit_training.py", "frontend/lib/mlops/model-execution.test.ts"],
      iac: ["template.yaml: PublicSbirTransitionModelPackageGroup and DocumentSageMakerExecutionRole"],
    },
    differentiator: "The product ties public training rows, immutable artifacts, temporal evaluation, current public scoring inputs, prediction outputs, and human promotion to inspectable receipts.",
    caveat: "The public SBIR candidate is evidence for a bounded research use case. It is not an accredited production endpoint and must not be described as predicting program success.",
    tags: ["SageMaker", "registry", "training", "prediction", "human gate"],
  },
  {
    id: "drift-monitoring",
    title: "Drift and monitoring",
    intent: "Compare bounded inference windows to an approved baseline, raise review signals, and prevent silent model promotion when policy thresholds fail.",
    status: "configured",
    userAction: "Open Model operations, select the shifted-data scenario, run drift evaluation, and show that the Champion remains unchanged while review is required.",
    liveEvidence: [
      { kind: "screen", label: "Drift and retraining", locator: "/admin/mlops/", href: "/admin/mlops/" },
      { kind: "api", label: "Drift evaluation", locator: "POST /ml/drift/evaluate | GET /ml/ops/evidence" },
    ],
    locators: {
      source: ["src/functions/document_ml/engine.py", "frontend/components/mlops/model-operations.tsx"],
      tests: ["src/functions/document_ml/tests/test_engine.py", "frontend/lib/mlops/demo-model.test.ts"],
      iac: ["template.yaml: DocumentMlFunctionErrorAlarm and model registry resources"],
    },
    differentiator: "Drift creates a governed review decision and cannot replace the Champion by itself.",
    caveat: "A continuous production inference baseline and a long-running Model Monitor schedule need representative Government traffic and an approved operating policy.",
    tags: ["drift", "baseline", "monitor", "retraining"],
  },
  {
    id: "alerts-notifications",
    title: "Alerts and notifications",
    intent: "Surface ingestion, model, acquisition, and release signals in the product and route approved events to operational channels.",
    status: "external-dependency",
    userAction: "Open the notification bell, inspect a signal, follow it to the affected run, and acknowledge it as the current power user.",
    liveEvidence: [
      { kind: "screen", label: "Operations signals", locator: "Notification bell in the application header", href: "/admin/pipeline/" },
      { kind: "api", label: "Signal feed", locator: "GET /operations/signals | POST /operations/signals/{eventId}/acknowledge" },
    ],
    locators: {
      source: ["frontend/components/notifications/notification-center.tsx", "src/functions/operations/app.py"],
      tests: ["src/functions/operations/tests/test_app.py", "scripts/tests/test_ci_security_regressions.py"],
      iac: ["template.yaml: CloudWatch alarms and operational notification resources"],
    },
    differentiator: "One signal contract links the event, affected run, severity, acknowledgement, and channel delivery state.",
    caveat: "In-app evidence can be shown now. Verified email, SNS, webhook, or CSSP delivery needs a confirmed recipient or Government operations integration.",
    tags: ["alerts", "email", "SNS", "acknowledgement"],
  },
  {
    id: "continuous-public-acquisition",
    title: "Continuous multi-source public acquisition",
    intent: "Pull bounded updates from official public sources on responsible schedules, retain source pages, compute record changes, classify narratives, create exact evidence links, and publish only accepted snapshots.",
    status: "configured",
    userAction: "Open Live source operations, confirm continuous acquisition is running, and show the latest accepted run for each authority, source-safe cadence, change counts, narrative classification, exact identity keys, and end-to-end lineage.",
    liveEvidence: [
      { kind: "screen", label: "Multi-source operations", locator: "/admin/acquisition/", href: "/admin/acquisition/" },
      { kind: "api", label: "Source health and receipts", locator: "GET /public-intelligence/acquisitions | GET /public-intelligence/acquisitions/continuous" },
    ],
    locators: {
      source: ["src/functions/public_acquisition/app.py", "src/functions/public_acquisition/feed_sources.py", "src/functions/document_ml/app.py"],
      tests: ["src/functions/public_acquisition/tests/test_app.py", "src/functions/operations/tests/test_app.py"],
      iac: ["template.yaml: ScheduledPublicAcquisition, dead-letter queue, and public acquisition resources"],
    },
    differentiator: "Backend schedules continue without an open browser while the interface projects retained change events in near real time. Every accepted fact keeps its source-specific receipt, immutable hashes, model version, exact identity keys, and change set.",
    caveat: "Continuous means recurring backend acquisition at each authority's responsible cadence, not a request to an external API every second. Only sources with a protected live receipt and accepted watermark are verified, and ambiguous cross-source links require analyst review.",
    tags: ["USAspending", "Grants.gov", "Crossref", "Federal Register", "lineage", "model"],
  },
  {
    id: "devsecops-iac",
    title: "DevSecOps and IaC",
    intent: "Build and deploy application and infrastructure changes through reviewed, repeatable, security-scanned automation with rollback evidence.",
    status: "configured",
    userAction: "Open Delivery control and walk from source review through tests, SAST and dependency checks, Terraform and SAM validation, OIDC deployment, verification, and rollback.",
    liveEvidence: [
      { kind: "screen", label: "IaC and DevSecOps Delivery Control", locator: "/admin/delivery/", href: "/admin/delivery/" },
      { kind: "api", label: "Deployment evidence", locator: "GET /system/evidence" },
    ],
    locators: {
      source: [".github/workflows/devsecops.yml", ".github/workflows/deploy.yml"],
      tests: ["scripts/tests/test_ci_runner_contract.py", "scripts/tests/test_ci_security_regressions.py"],
      iac: ["template.yaml", "infra/terraform/main.tf"],
    },
    differentiator: "The delivery path treats test, security, identity, deployment, and rollback outputs as demonstrable evidence, not presentation text.",
    caveat: "A current successful workflow for the exact deployed commit and the customer's approved scanners and gates are required before calling delivery verified.",
    tags: ["CI/CD", "Terraform", "SAM", "OIDC", "security"],
  },
  {
    id: "identity-access",
    title: "Identity and access",
    intent: "Authenticate users, derive role and organization from trusted identity claims, and enforce the same scope in the API and data layer.",
    status: "verified-live",
    userAction: "Sign in as a power user, show the active persona, then explain that the API derives role and organization from the protected token rather than a browser switch.",
    liveEvidence: [
      { kind: "screen", label: "Authenticated mission workspace", locator: "/dashboard/", href: "/dashboard/" },
      { kind: "api", label: "Identity projection", locator: "GET /me" },
    ],
    locators: {
      source: ["src/functions/authorizer/app.py", "frontend/lib/auth/identity-contract.ts"],
      tests: ["src/functions/authorizer/tests/test_identity_display.py", "frontend/lib/auth/identity-contract.test.ts"],
      iac: ["template.yaml: UserPool, HttpApi JWT authorizer, and database RLS"],
    },
    differentiator: "The visible persona, JWT claims, API authorization, and row scope follow one identity contract.",
    caveat: "The commercial demo uses Cognito. CAC or PIV federation, DoD ICAM, and privileged-access controls belong to the Government IL4 or IL5 target environment.",
    tags: ["Cognito", "JWT", "RBAC", "RLS", "CAC/PIV"],
  },
  {
    id: "controlled-release-api",
    title: "Controlled release and API",
    intent: "Expose portable open-format interfaces while keeping a future protected release workflow, role checks, approvals, destinations, and audit evidence separate from browser-only preview behavior.",
    status: "configured",
    userAction: "Open Portable preview from the live public workspace, download the bounded JSON or CSV generated in this browser, inspect its source fields and local checksum, and state that no protected release, approval, delivery, or audit receipt was created.",
    liveEvidence: [
      { kind: "screen", label: "Browser-generated portable preview", locator: "/export/", href: "/export/" },
      { kind: "api", label: "Configured protected API contract", locator: "GET /openapi.json | POST /export" },
    ],
    locators: {
      source: ["src/functions/export/app.py", "src/functions/export/openapi.py"],
      tests: ["src/functions/export/tests/test_security.py", "src/functions/export/tests/test_openapi_routes.py"],
      iac: ["template.yaml: HttpApi JWT authorizer, export function, and encrypted buckets"],
    },
    differentiator: "The live screen proves data portability without misrepresenting a browser download as an approved server-side release. The protected release API remains a separately testable integration seam.",
    caveat: "The live public screen creates a local browser preview only. It does not call POST /export, apply approval policy, deliver an object, write an audit record, or return a server receipt. Those controls require a verified protected API execution in the intended environment.",
    tags: ["API", "export", "approval", "checksum", "audit"],
  },
  {
    id: "il4-il5-target",
    title: "IL4/IL5 target",
    intent: "Define a GovCloud authorization boundary with SCCA services, CAC or PIV federation, Zero Trust controls, protected logging, and RMF evidence.",
    status: "target-architecture",
    userAction: "Open Architecture evidence, select the IL4 and IL5 target view, and distinguish the current commercial demo boundary from the proposed GovCloud and SCCA boundary.",
    liveEvidence: [
      { kind: "screen", label: "Architecture evidence", locator: "/admin/architecture/", href: "/admin/architecture/" },
      { kind: "screen", label: "Target architecture record", locator: "docs/IL4_IL5_TARGET_ARCHITECTURE.md" },
    ],
    locators: {
      source: ["docs/IL4_IL5_TARGET_ARCHITECTURE.md", "docs/SECURITY.md"],
      tests: ["scripts/tests/test_stig_evidence.py", "scripts/validate_stig_controls.py"],
      iac: ["template.yaml: current commercial baseline only", "infra/terraform/main.tf: portable baseline only"],
    },
    differentiator: "The proof screen labels deployed controls and target controls separately, which avoids turning an architecture proposal into an accreditation claim.",
    caveat: "This deployment is not IL4 or IL5 authorized. GovCloud tenancy, CAP or BCAP onboarding, VDSS and VDMS services, DoD ICAM, CSSP operations, control inheritance, assessment, and AO authorization are external prerequisites.",
    tags: ["GovCloud", "SCCA", "Zero Trust", "RMF", "ATO"],
  },
];

export const PRESENTER_SEQUENCE: PresenterStep[] = [
  {
    order: 1,
    title: "Start with live public acquisition",
    duration: "4 min",
    instruction: "Confirm continuous acquisition is running, open one accepted public run, and show its authority, watermark, source hash, quality result, model receipt, catalog metadata, and lineage.",
    href: "/admin/acquisition/",
    requirementIds: ["governed-intake-quality", "catalog-metadata", "lineage"],
  },
  {
    order: 2,
    title: "Move from evidence to decision",
    duration: "4 min",
    instruction: "Filter live public intelligence, inspect a cited cross-source signal, then show the real public-data model candidate, bounded execution receipt, and shifted-data drift decision.",
    href: "/dashboard/",
    requirementIds: ["decision-analytics", "real-model-lifecycle", "drift-monitoring"],
  },
  {
    order: 3,
    title: "Show continuous operations",
    duration: "3 min",
    instruction: "Use the live proof panel and notification bell. Explain that AWS schedules call each authority responsibly while the browser refreshes retained events in near real time. A source counts as live only when its protected receipt has a watermark and change counts.",
    href: "/admin/pipeline/",
    requirementIds: ["alerts-notifications", "continuous-public-acquisition"],
  },
  {
    order: 4,
    title: "Prove secure delivery and the release boundary",
    duration: "4 min",
    instruction: "Walk the reviewed delivery pipeline and trusted identity path, then create the browser-only portable preview and distinguish it from the configured protected approval, delivery, audit, and receipt workflow.",
    href: "/admin/delivery/",
    requirementIds: ["devsecops-iac", "identity-access", "controlled-release-api"],
  },
  {
    order: 5,
    title: "Close with the authorization boundary",
    duration: "3 min",
    instruction: "Show the IL4 and IL5 target architecture and name the Government dependencies without claiming that this commercial deployment is accredited.",
    href: "/admin/architecture/",
    requirementIds: ["il4-il5-target"],
  },
];

export function countByStatus(requirements: readonly RequirementTrace[] = REQUIREMENTS): Record<TraceStatus, number> {
  return TRACE_STATUSES.reduce<Record<TraceStatus, number>>((counts, status) => {
    counts[status] = requirements.filter((item) => item.status === status).length;
    return counts;
  }, {
    "verified-live": 0,
    configured: 0,
    "target-architecture": 0,
    "external-dependency": 0,
    "not-yet-implemented": 0,
  });
}

const VERIFIED_PUBLIC_REQUIREMENTS = new Set([
  "governed-intake-quality",
  "lineage",
  "continuous-public-acquisition",
]);

export function resolveOperationalRequirementStates(
  requirements: readonly RequirementTrace[],
  operations: OperationsSummaryResponse | null,
): RequirementTrace[] {
  if (!isVerifiedOperationsSummary(operations)) return requirements.map((item) => ({ ...item }));

  const acceptedPublicRun = verifiedAcceptedPublicRun(operations);
  const verifiedModelRun = operations.runs.find((run) => isVerifiedRun(run, [
    "sagemaker-batch-inference",
    "public-narrative-classification",
  ]));
  const verifiedDriftRun = operations.runs.find((run) => (
    isVerifiedRun(run) && run.run_kind.toLowerCase().includes("drift")
  ));

  return requirements.map((item) => {
    if (acceptedPublicRun && VERIFIED_PUBLIC_REQUIREMENTS.has(item.id)) {
      return {
        ...item,
        status: "verified-live",
        caveat: `Protected operations evidence verifies completed public run ${acceptedPublicRun.run_id} with an accepted watermark and source digest. This proves a bounded public workflow, not access to protected ONR systems or production authorization.`,
      };
    }
    if (item.id === "real-model-lifecycle" && verifiedModelRun) {
      return {
        ...item,
        status: "verified-live",
        caveat: `Protected operations evidence verifies completed model run ${verifiedModelRun.run_id}. The bounded public model remains decision support and is not an accredited production endpoint or a prediction of ONR program success.`,
      };
    }
    if (item.id === "drift-monitoring" && verifiedDriftRun) {
      return {
        ...item,
        status: "verified-live",
        caveat: `Protected operations evidence verifies completed drift run ${verifiedDriftRun.run_id}. Representative Government traffic, an approved baseline, and approved operating thresholds are still required for production monitoring.`,
      };
    }
    return { ...item };
  });
}

function isVerifiedOperationsSummary(
  operations: OperationsSummaryResponse | null,
): operations is OperationsSummaryResponse {
  return Boolean(
    operations
    && operations.contract === "compass.operations.summary.v1"
    && operations.mode === "live"
    && validTimestamp(operations.generated_at)
    && Array.isArray(operations.runs)
    && Array.isArray(operations.source_watermarks),
  );
}

function verifiedAcceptedPublicRun(operations: OperationsSummaryResponse): OperationsRunSummary | undefined {
  return operations.runs.find((run) => {
    if (!isVerifiedRun(run, ["public-acquisition"])) return false;
    return operations.source_watermarks.some((watermark) => (
      watermark.run_id === run.run_id
      && watermark.status === "current"
      && validTimestamp(watermark.last_accepted_at)
      && Boolean(watermark.watermark?.trim())
    ));
  });
}

function isVerifiedRun(run: OperationsRunSummary, allowedKinds?: readonly string[]): boolean {
  const normalizedKind = run.run_kind.trim().toLowerCase().replaceAll("_", "-");
  const evidenceClass = run.evidence_class.trim().toLowerCase().replaceAll("_", "-");
  return Boolean(
    run.run_id.trim()
    && (!allowedKinds || allowedKinds.includes(normalizedKind))
    && evidenceClass.startsWith("public")
    && run.status === "completed"
    && run.stage_count > 0
    && run.completed_stages >= run.stage_count
    && validTimestamp(run.updated_at)
    && validSha256(run.source.sha256),
  );
}

function validTimestamp(value: string | null): boolean {
  return Boolean(value && Number.isFinite(Date.parse(value)));
}

function validSha256(value: string | null | undefined): boolean {
  return Boolean(value && /^[a-f0-9]{64}$/i.test(value));
}
