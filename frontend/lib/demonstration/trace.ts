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
    shortTitle: "Live public acquisition",
    action: "Open continuous source operations, inspect one accepted authority run, and follow the resulting change events.",
    focus: "Show operator-controlled continuous state, source-safe schedules, exact authority receipts, automated quality, schema variation handling, quarantine, classification, identity linkage, and Kinesis change projection.",
    durationMinutes: 7,
    presenter: "Data Engineer",
    href: "/admin/acquisition/",
    screen: "Live source operations",
    value: "Compass collects real public changes without an open browser while rejected content is isolated instead of silently entering decisions.",
    proof: ["Authority URI, retrieval time, watermark, and SHA-256", "Quality, identity, and narrative-classifier receipts", "Accepted, changed, quarantined, and Kinesis projection evidence"],
    source: ["src/functions/public_acquisition/", "src/functions/document_ml/", "frontend/components/acquisition/"],
    state: "live",
    boundary: "Continuous means backend polling at each authority's responsible cadence. The browser projects retained AWS events in near real time and does not call external APIs every second. Synthetic files require explicit rehearsal mode.",
  },
  {
    number: 4,
    title: "Data Governance, Quality, and Cataloging",
    shortTitle: "Governance and lineage",
    action: "Open the catalog entry created from an accepted public source run and inspect its dictionary, authority, model receipt, and lineage.",
    focus: "Show captured authority metadata, ownership, policy, quality score, model version, health status, and visual lineage from source response through the visualization tier.",
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
    action: "Inspect the champion narrative classifier on accepted public records, then run the governed SageMaker candidate against a bounded current public cohort.",
    focus: "Show public training lineage, structured model outputs, metrics, registry version, Batch Transform receipt, monitoring, drift, and how the result supports a leadership decision.",
    durationMinutes: 7,
    presenter: "Data Scientist",
    href: "/admin/mlops/",
    screen: "Model operations",
    value: "Leadership receives reproducible public evidence labels and a bounded transition proxy with confidence, citations, and lifecycle controls instead of an unexplained prediction.",
    proof: ["11,287-row public Navy SBIR manifest and source digests", "SageMaker evaluation metrics and registered candidate version", "Per-record classifier version, Batch Transform output, confidence, drift, and promotion receipt"],
    source: ["src/functions/model_ops/", "infra/terraform/sagemaker.tf", "frontend/components/mlops/"],
    state: "working",
    boundary: "The public narrative classifier organizes evidence and the SBIR candidate estimates a bounded transition proxy. Neither model predicts ONR program success, allocates funding, or makes an autonomous decision.",
  },
  {
    number: 6,
    title: "Unified Dashboard, Visualizations, and Process Automation",
    shortTitle: "Executive workspace",
    action: "Use the live public decision workspace as a non-technical leader to search, filter, inspect citations, summarize, and route an exception.",
    focus: "Show unified visualization, search and filtering, automated summaries, approval routing, anomaly flags, and evidence drill-through.",
    durationMinutes: 5,
    presenter: "Product Lead",
    href: "/dashboard/",
    screen: "Decision workspace",
    value: "A single workflow shortens the path from incoming evidence to an authorized, explainable portfolio action.",
    proof: ["Role-aware filters and KPIs", "Automated anomaly and summary workflow", "Four-eyes action and evidence drill-through"],
    source: ["frontend/components/dashboard/", "src/functions/dashboard/app.py", "src/functions/approvals/app.py"],
    state: "live",
    boundary: "Public-data signals are decision support. Mission KPIs, operating thresholds, and approval chains remain representative until configured with ONR users and data owners.",
  },
  {
    number: 7,
    title: "Interoperability, Data Portability, and Secure Export",
    shortTitle: "Portable preview",
    action: "Filter accepted public evidence and create a browser-generated JSON or CSV preview with source fields and a local checksum.",
    focus: "Show open-format portability, source identity, a browser-computed checksum, standard interface seams, and the explicit boundary before protected approval, delivery, audit, or Government integration can be claimed.",
    durationMinutes: 4,
    presenter: "Chief Enterprise Architect",
    href: "/export/",
    screen: "Portable browser preview",
    value: "Open formats and stable contracts preserve customer choice while the product clearly separates a local preview from a governed server release.",
    proof: ["Filtered browser preview", "Source and model evidence fields", "Local file checksum and explicit no-server-receipt disclosure"],
    source: ["src/functions/export/app.py", "src/functions/export/openapi.py", "docs/CONTRACTS.md"],
    state: "working",
    boundary: "The live screen does not call POST /export or create approval, delivery, audit, expiration, or server receipt evidence. Advana, Cloud One, and Government transfer endpoints remain configured interfaces until execution and connectivity are verified.",
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
