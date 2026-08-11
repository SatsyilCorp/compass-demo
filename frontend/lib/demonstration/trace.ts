export type DemoEvidenceState = "live" | "working" | "planned";

export type DemoElement = {
  number: number;
  title: string;
  shortTitle: string;
  action: string;
  focus: string;
  durationMinutes: number;
  presenter: string;
  href: string;
  screen: string;
  value: string;
  proof: string[];
  source: string[];
  state: DemoEvidenceState;
  boundary: string;
};

export type StrategicPrompt = {
  id: string;
  title: string;
  requirement: string;
  addressDuring: number[];
  response: string[];
  evidence: string[];
};

export const DEMO_EVIDENCE_META: Record<DemoEvidenceState, { label: string; description: string }> = {
  live: {
    label: "Live evidence",
    description: "Executed in the retained Satsyil AWS environment with inspectable source and receipts.",
  },
  working: {
    label: "Working prototype",
    description: "Implemented and executable with sanitized demo data, with production activation still bounded.",
  },
  planned: {
    label: "Proposed production pattern",
    description: "Architecture and controls are shown honestly, but customer-environment acceptance is still required.",
  },
};

export const DEMO_LOGISTICS = {
  maximumMinutes: 50,
  scenarioMinutes: 39,
  promptMinutes: 8,
  closeMinutes: 3,
  dataConstraint: "Use sanitized, open-source, or mock data only. Never upload CUI, PII, or classified data.",
  environmentConstraint: "Use a live functioning cloud environment and live source repositories. Static slide decks are not part of the technical demonstration.",
  presenterConstraint: "Proposed Key Personnel lead and narrate the technical elements.",
};

export const DEMO_ELEMENTS: DemoElement[] = [
  {
    number: 1,
    title: "Secure Access, Authentication, and Zero Trust",
    shortTitle: "Secure access",
    action: "Authenticate a named user and enter the Compass portal.",
    focus: "Show MFA, the identity provider, least privilege, role mapping, and continuous authorization across protected requests.",
    durationMinutes: 5,
    presenter: "Chief Enterprise Architect",
    href: "/login/",
    screen: "Identity gateway",
    value: "Named identities and deny-by-default authorization reduce account sharing and restrict each decision to the user's approved scope.",
    proof: ["Cognito authentication flow", "JWT authorizer and fixed role mapping", "Viewer funding redaction and database RLS"],
    source: ["template.yaml", "src/functions/authorizer/app.py", "db/migrations/003_security_hardening.sql"],
    state: "working",
    boundary: "Team-preview users remain password-only for collaboration. The formal recording must use the dedicated MFA identity and approved security posture.",
  },
  {
    number: 2,
    title: "Infrastructure as Code and Automation",
    shortTitle: "IaC and CI/CD",
    action: "Walk through the repository, infrastructure plan, security gates, and controlled deployment evidence.",
    focus: "Show Terraform or equivalent IaC, configuration management, CI/CD, version control, security scanning, approval, and rollback.",
    durationMinutes: 6,
    presenter: "DevSecOps Engineer",
    href: "/admin/delivery/",
    screen: "Delivery control",
    value: "A commit-bound golden path makes environments reproducible, reviewable, and safer to promote.",
    proof: ["Terraform and SAM infrastructure", "GitHub Actions quality and deployment gates", "SAST, dependency, secret, IaC, STIG, and DAST evidence"],
    source: ["infra/terraform/", "template.yaml", ".github/workflows/"],
    state: "working",
    boundary: "The prototype proves the delivery controls in Satsyil. Government runners, registries, approval groups, and production promotion policy require target-environment configuration.",
  },
  {
    number: 3,
    title: "Automated Ingestion, Data Operations, and Streaming",
    shortTitle: "File and stream intake",
    action: "Drop a sanitized unstructured or semi-structured file into Compass and follow the resulting run.",
    focus: "Show file detection, schema inspection, automated quality checks, schema variation handling, quarantine, Bronze, Silver, and Gold processing, plus Kinesis streaming.",
    durationMinutes: 7,
    presenter: "Data Engineer",
    href: "/ingest/",
    screen: "Document intake",
    value: "Users can submit new evidence without waiting for a custom seed release, while failed content is isolated instead of silently entering decisions.",
    proof: ["Real browser-selected file and SHA-256 digest", "Inspection, quality, and classification receipts", "Bronze, Silver, Gold, quarantine, and Kinesis stage evidence"],
    source: ["src/functions/document_intake/", "statemachines/document_intake.asl.yaml", "frontend/components/documents/"],
    state: "working",
    boundary: "The demo accepts bounded sanitized files. Customer connectors, malware tooling, OCR languages, source agreements, and sustained stream rates require acceptance testing.",
  },
  {
    number: 4,
    title: "Data Governance, Quality, and Cataloging",
    shortTitle: "Governance and lineage",
    action: "Open the catalog entry created by the uploaded document and inspect its dictionary and lineage.",
    focus: "Show captured metadata, ownership, policy, quality score, health status, and visual lineage from raw intake through the visualization tier.",
    durationMinutes: 5,
    presenter: "Data Architect",
    href: "/catalog/",
    screen: "Governed catalog",
    value: "Every visible insight can be traced to controlled source evidence, reducing unexplainable analytics and manual audit work.",
    proof: ["Dataset and field metadata", "Quality formula and disposition", "Source-to-decision lineage graph"],
    source: ["src/functions/catalog/app.py", "frontend/components/catalog/lineage-view.tsx", "docs/CONTRACTS.md"],
    state: "live",
    boundary: "Compass lineage covers this prototype workflow. Enterprise lineage across external tools requires their metadata adapters and stewardship policy.",
  },
  {
    number: 5,
    title: "Decision-Support Analytics and Modeling",
    shortTitle: "Model and decide",
    action: "Train or select a classical document classifier, run it against the ingested file, and open the resulting decision evidence.",
    focus: "Show structured model outputs, metrics, registry version, deployment state, monitoring, drift, and how the result supports a leadership decision.",
    durationMinutes: 7,
    presenter: "Data Scientist",
    href: "/admin/mlops/",
    screen: "Model operations",
    value: "Leadership receives a reproducible priority signal with confidence, evidence, and lifecycle controls instead of an unexplained prediction.",
    proof: ["Training dataset and source digests", "Evaluation metrics and registered model version", "Classification, confidence, drift, and promotion receipt"],
    source: ["src/functions/model_ops/", "infra/terraform/sagemaker.tf", "frontend/components/mlops/"],
    state: "working",
    boundary: "The classifier uses sanitized synthetic documents and is a capability proof, not an operational grant-selection model.",
  },
  {
    number: 6,
    title: "Unified Dashboard, Visualizations, and Process Automation",
    shortTitle: "Executive workspace",
    action: "Use the decision workspace as a non-technical leader to search, filter, inspect, summarize, and route an exception.",
    focus: "Show unified visualization, search and filtering, automated summaries, approval routing, anomaly flags, and evidence drill-through.",
    durationMinutes: 5,
    presenter: "Product Lead",
    href: "/dashboard/",
    screen: "Decision workspace",
    value: "A single workflow shortens the path from incoming evidence to an authorized, explainable portfolio action.",
    proof: ["Role-aware filters and KPIs", "Automated anomaly and summary workflow", "Four-eyes action and evidence drill-through"],
    source: ["frontend/components/dashboard/", "src/functions/dashboard/app.py", "src/functions/approvals/app.py"],
    state: "live",
    boundary: "Mission KPIs and approval chains are representative and must be configured with ONR users and data owners.",
  },
  {
    number: 7,
    title: "Interoperability, Data Portability, and Secure Export",
    shortTitle: "Secure export",
    action: "Filter a governed dataset, obtain approval when required, and export it in an open format.",
    focus: "Show CSV, JSON, and Parquet portability, checksums, secure bulk release, standard schemas and interfaces, and integration with Advana or Cloud One.",
    durationMinutes: 4,
    presenter: "Chief Enterprise Architect",
    href: "/export/",
    screen: "Governed release",
    value: "Open formats and stable contracts preserve customer choice while policy is rechecked at the point of release.",
    proof: ["Filtered export request", "Independent approval and one-time capability", "Open-format object, checksum, expiration, and interface contract"],
    source: ["src/functions/export/app.py", "src/functions/export/openapi.py", "docs/CONTRACTS.md"],
    state: "live",
    boundary: "Advana, Cloud One, and Government transfer endpoints are represented by standard interfaces until customer connectivity is authorized.",
  },
];

export const STRATEGIC_PROMPTS: StrategicPrompt[] = [
  {
    id: "legacy-sustainment",
    title: "Sustainment of the Legacy Footprint",
    requirement: "Explain how current portal, reporting, database, and ETL operations continue without service degradation during modernization.",
    addressDuring: [2, 3],
    response: [
      "Establish service baselines, ownership, dependencies, SLIs, incident routes, and frozen interface contracts before changing the implementation.",
      "Use a strangler migration with parallel adapters, shadow reads, reconciliation receipts, and reversible traffic shifts by workload.",
      "Keep production support and modernization backlogs separate, with error budgets and rollback gates protecting the legacy mission.",
    ],
    evidence: ["Adapter seam in architecture", "Additive database migrations", "Deployment and rollback gates"],
  },
  {
    id: "financial-integration",
    title: "Financial and Budgetary Analytical Integration",
    requirement: "Explain predictive and prescriptive support for execution tracking, budget formulation, and cost optimization.",
    addressDuring: [5, 6],
    response: [
      "Join governed obligations, awards, milestones, and portfolio outcomes through stable business keys and visible quality rules.",
      "Use forecasting and scenario ranges with assumptions, confidence, model version, and source coverage shown next to every recommendation.",
      "Route threshold exceptions for human review and compare program benefit, schedule risk, and cloud run cost before action.",
    ],
    evidence: ["Budget execution visualization", "Model and anomaly receipts", "Cost-bounded Scale Plan"],
  },
  {
    id: "zero-trust",
    title: "Zero Trust and Cybersecurity Compliance",
    requirement: "Explain micro-segmentation, continuous compliance, and least-privilege configuration for an IL5 hosting baseline.",
    addressDuring: [1, 2],
    response: [
      "Authenticate named users, issue short-lived identity, and authorize every request using fixed roles and resource scope.",
      "Keep data stores private, encrypt each durable layer, restrict workload identities, and separate control, data, evidence, and presentation planes.",
      "Continuously evaluate source, dependencies, IaC, STIG policy, runtime findings, audit logs, and deployment drift before promotion.",
    ],
    evidence: ["Identity and policy trace", "Network and encryption topology", "DevSecOps security gates"],
  },
  {
    id: "resilience",
    title: "Disaster Recovery, Resilience, and Failover",
    requirement: "Explain RTO, RPO, high availability, and non-disruptive annual disaster recovery exercises.",
    addressDuring: [2, 6],
    response: [
      "Set workload-specific recovery targets, with a proposed portal RTO of 60 minutes and RPO of 15 minutes subject to discovery and approval.",
      "Use multi-AZ managed data services, versioned immutable objects, additive deployment, retained manifests, and independently replayable processing.",
      "Exercise restore, regional rebuild, queue redrive, identity recovery, and evidence reconciliation annually through an approved game day with measured receipts.",
    ],
    evidence: ["Multi-AZ and durable queue design", "Backup and replay paths", "Recovery gate in Delivery control"],
  },
  {
    id: "vendor-lifecycle",
    title: "Data Vendor and Lifecycle Management",
    requirement: "Explain subscription tracking, usage licenses, data quality compliance, and renewal management without dashboard gaps.",
    addressDuring: [4, 7],
    response: [
      "Register vendor, dataset, allowed purpose, users, geography, retention, renewal date, owner, and evidence as governed metadata.",
      "Evaluate license scope at intake, query, and export, then alert owners before renewal or usage limits create a data gap.",
      "Maintain an approved fallback source and visible freshness state so downstream products fail clearly instead of serving stale data silently.",
    ],
    evidence: ["License posture workspace", "Catalog ownership and freshness", "Release-time policy decision"],
  },
];

export function totalScenarioMinutes(): number {
  return DEMO_ELEMENTS.reduce((total, element) => total + element.durationMinutes, 0);
}

