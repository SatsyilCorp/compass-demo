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
    intent: "Accept a structured or unstructured file, bind its bytes to a run, apply quality policy, and publish or quarantine it with a retained receipt.",
    status: "verified-live",
    userAction: "Open Ingest and quality, select the prepared Technical report, then follow the visible stages from hash through Gold publication.",
    liveEvidence: [
      { kind: "screen", label: "Ingest and quality", locator: "/ingest/", href: "/ingest/" },
      { kind: "api", label: "Upload and run receipt", locator: "POST /documents/uploads | GET /documents/runs/{run_id}" },
    ],
    locators: {
      source: ["frontend/components/documents/document-drop-zone.tsx", "src/functions/document_ml/app.py"],
      tests: ["src/functions/document_ml/tests/test_app.py", "frontend/lib/documents/document-intake.test.ts"],
      iac: ["template.yaml: DocumentObjectCreatedRule and DocumentMlStateMachine"],
    },
    differentiator: "The run ID, source SHA-256, quality outcome, model result, and consumer projection remain bound to the same evidence chain.",
    caveat: "The commercial demo accepts synthetic or public PII-minimized content only. It must not receive CUI, controlled technical data, or direct PII.",
    tags: ["file drop", "structured", "unstructured", "quality", "quarantine"],
  },
  {
    id: "catalog-metadata",
    title: "Catalog and metadata",
    intent: "Expose governed datasets, field definitions, quality, freshness, ownership, and source context through one searchable catalog.",
    status: "verified-live",
    userAction: "Open Governed catalog, expand one dataset, and point to its field definitions, freshness, quality score, source batch, and owner.",
    liveEvidence: [
      { kind: "screen", label: "Governed catalog", locator: "/catalog/", href: "/catalog/" },
      { kind: "api", label: "Catalog contract", locator: "GET /catalog" },
    ],
    locators: {
      source: ["src/functions/catalog/app.py", "frontend/components/catalog/catalog-table.tsx"],
      tests: ["frontend/tests/e2e/demo-ready.spec.ts", "src/functions/export/tests/test_openapi_routes.py"],
      iac: ["template.yaml: CatalogFunction and Glue catalog resources"],
    },
    differentiator: "Metadata is tied to operational quality and lineage evidence instead of being a detached inventory page.",
    caveat: "The catalog covers Compass-managed assets. External enterprise catalogs need metadata connectors and Government-approved access.",
    tags: ["catalog", "dictionary", "freshness", "ownership"],
  },
  {
    id: "lineage",
    title: "Lineage",
    intent: "Trace a specific run from immutable source through every processing stage, model version, output artifact, and consuming screen.",
    status: "verified-live",
    userAction: "After a file run, open its lineage link and inspect stage status, source and output hashes, model version, actor, and receipt locator.",
    liveEvidence: [
      { kind: "screen", label: "Run lineage", locator: "/catalog/lineage/?batch={run_id}", href: "/catalog/lineage/" },
      { kind: "api", label: "Cross-workflow lineage", locator: "GET /operations/lineage/{runId}" },
    ],
    locators: {
      source: ["src/functions/operations/app.py", "frontend/components/catalog/lineage-view.tsx"],
      tests: ["src/functions/operations/tests/test_app.py", "frontend/tests/e2e/demo-ready.spec.ts"],
      iac: ["template.yaml: OperationsTable, document workflow, and intake workflow"],
    },
    differentiator: "Lineage is built from stage receipts and hashes produced by execution, not from a diagram-only claim.",
    caveat: "Enterprise lineage stops at the Compass boundary until Databricks, Advana, or another external catalog supplies its own metadata events.",
    tags: ["provenance", "hash", "receipt", "run"],
  },
  {
    id: "decision-analytics",
    title: "Decision analytics",
    intent: "Turn governed portfolio and document evidence into filterable decisions, anomalies, projections, and cited explanations.",
    status: "verified-live",
    userAction: "Open Decision workspace, apply a program or fiscal-year filter, inspect an anomaly, and follow its evidence back to the governed source.",
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
    caveat: "Current results use synthetic or public evidence. They are decision-support signals, not authoritative ONR conclusions or autonomous decisions.",
    tags: ["dashboard", "anomaly", "forecast", "citations"],
  },
  {
    id: "real-model-lifecycle",
    title: "Real model lifecycle",
    intent: "Train, evaluate, register, approve, deploy, and execute a governed model with immutable dataset, source, artifact, and metric receipts.",
    status: "verified-live",
    userAction: "Open Model operations, show the SageMaker candidate and its temporal evaluation, then run bounded scoring and inspect the returned prediction receipt.",
    liveEvidence: [
      { kind: "screen", label: "Model operations", locator: "/admin/mlops/", href: "/admin/mlops/" },
      { kind: "api", label: "Model registry and execution", locator: "GET /ml/models | POST /public-intelligence/model-executions" },
    ],
    locators: {
      source: ["mlops/sagemaker/public_sbir_transition/train.py", "src/functions/public_intelligence/model_execution.py"],
      tests: ["mlops/sagemaker/public_sbir_transition/test_submit_training.py", "frontend/lib/mlops/model-execution.test.ts"],
      iac: ["template.yaml: PublicSbirTransitionModelPackageGroup and DocumentSageMakerExecutionRole"],
    },
    differentiator: "The demo separates a measured candidate from a production Champion and keeps promotion behind a human gate.",
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
    title: "Continuous public acquisition",
    intent: "Pull bounded USAspending updates on a schedule, retain source pages, advance a watermark, compute record changes, and publish only an accepted snapshot.",
    status: "not-yet-implemented",
    userAction: "Use the live operations proof above. A successful run must show a USAspending watermark, accepted timestamp, run ID, and added or changed record counts.",
    liveEvidence: [
      { kind: "screen", label: "Public source ledger", locator: "/intelligence/", href: "/intelligence/" },
      { kind: "api", label: "Acquisition watermark", locator: "GET /operations/summary" },
    ],
    locators: {
      source: ["src/functions/public_acquisition/app.py", "src/functions/operations/app.py"],
      tests: ["src/functions/public_acquisition/tests/test_app.py", "src/functions/operations/tests/test_app.py"],
      iac: ["template.yaml: ScheduledPublicAcquisition, dead-letter queue, and public acquisition resources"],
    },
    differentiator: "A watermark and change set prove an incremental acquisition instead of repeatedly presenting a bundled static snapshot.",
    caveat: "Keep this state as not yet implemented unless the protected live API returns a current accepted USAspending watermark. Replay fixtures do not prove a cloud pull.",
    tags: ["USAspending", "schedule", "watermark", "change set"],
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
    intent: "Expose governed interfaces and exports with role checks, scope policy, approvals, checksums, and auditable release receipts.",
    status: "verified-live",
    userAction: "Open Governed release, request a bounded export, show the approval control, and inspect the checksum and audit receipt after release.",
    liveEvidence: [
      { kind: "screen", label: "Governed release", locator: "/export/", href: "/export/" },
      { kind: "api", label: "Protected API contract", locator: "GET /openapi.json | POST /export" },
    ],
    locators: {
      source: ["src/functions/export/app.py", "src/functions/export/openapi.py"],
      tests: ["src/functions/export/tests/test_security.py", "src/functions/export/tests/test_openapi_routes.py"],
      iac: ["template.yaml: HttpApi JWT authorizer, export function, and encrypted buckets"],
    },
    differentiator: "The release is a policy decision with a single-use receipt, not an unrestricted download button.",
    caveat: "Production transfer destinations, cross-domain controls, records retention, and Government data-loss prevention policy remain environment-specific.",
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
    title: "Drop one file and prove the run",
    duration: "4 min",
    instruction: "Use the prepared Technical report. Show the byte hash, quality gate, model stage, terminal receipt, catalog metadata, and run lineage.",
    href: "/ingest/",
    requirementIds: ["governed-intake-quality", "catalog-metadata", "lineage"],
  },
  {
    order: 2,
    title: "Move from evidence to decision",
    duration: "4 min",
    instruction: "Filter the decision workspace, inspect a cited signal, then show the real model candidate, bounded execution receipt, and shifted-data drift decision.",
    href: "/dashboard/",
    requirementIds: ["decision-analytics", "real-model-lifecycle", "drift-monitoring"],
  },
  {
    order: 3,
    title: "Show continuous operations",
    duration: "3 min",
    instruction: "Use the live proof panel and notification bell. A public pull counts only when a live watermark and change counts are present.",
    href: "/admin/pipeline/",
    requirementIds: ["alerts-notifications", "continuous-public-acquisition"],
  },
  {
    order: 4,
    title: "Prove secure delivery and release",
    duration: "4 min",
    instruction: "Walk the reviewed delivery pipeline, trusted identity path, protected API, approval gate, and checksummed release receipt.",
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
