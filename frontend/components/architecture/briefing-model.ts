export type BriefingViewId = "executive" | "il45" | "lineage" | "devsecops" | "mlops";

export type ArchitectureStatus = "Running now" | "Configured" | "Target control" | "External dependency";

export type BriefingNode = {
  id: string;
  label: string;
  service: string;
  detail: string;
  status: ArchitectureStatus;
};

export type BriefingConnector = {
  protocol: string;
  receipt: string;
};

export type BriefingLane = {
  id: string;
  label: string;
  boundary: string;
  tone: "commercial" | "protected" | "external" | "evidence";
  outsideProtectedBoundary?: boolean;
  nodes: BriefingNode[];
  connectors: BriefingConnector[];
};

export type BriefingView = {
  id: BriefingViewId;
  label: string;
  eyebrow: string;
  title: string;
  summary: string;
  truth: string;
  lanes: BriefingLane[];
  callouts: string[];
};

const node = (
  id: string,
  label: string,
  service: string,
  detail: string,
  status: ArchitectureStatus,
): BriefingNode => ({ id, label, service, detail, status });

const connector = (protocol: string, receipt: string): BriefingConnector => ({ protocol, receipt });

export const ARCHITECTURE_STATUSES: ArchitectureStatus[] = [
  "Running now",
  "Configured",
  "Target control",
  "External dependency",
];

export const BRIEFING_VIEWS: BriefingView[] = [
  {
    id: "executive",
    label: "Executive flow",
    eyebrow: "One mission path",
    title: "Evidence enters, controls execute, people decide",
    summary: "The commercial AWS prototype keeps identity, workflow, governed data, model evidence, and human decisions on one traceable path.",
    truth: "Running in the Satsyil commercial AWS account. This view is operational evidence, not an IL4/IL5 authorization claim.",
    lanes: [
      {
        id: "executive-current",
        label: "Interactive mission path",
        boundary: "Current Satsyil commercial AWS deployment",
        tone: "commercial",
        nodes: [
          node("mission-user", "Mission user", "Compass browser", "Power user, reviewer, viewer, or operator enters a role-scoped workspace.", "Running now"),
          node("commercial-edge", "Protected web edge", "AWS WAF and CloudFront", "The current public commercial edge serves the static application and screens requests.", "Running now"),
          node("identity-api", "Identity and API", "Cognito, authorizer, API Gateway", "Short-lived claims are verified before a narrow application operation is selected.", "Running now"),
          node("workflow-data", "Governed processing", "Lambda, Step Functions, SQS, S3, Aurora", "Bounded work validates, transforms, quarantines, persists, and receipts each state change.", "Running now"),
          node("decisions", "Decision and evidence", "Catalog, intelligence, approval, export", "People inspect cited evidence, approve a decision, and release a checksummed product.", "Running now"),
        ],
        connectors: [
          connector("HTTPS", "WAF access log"),
          connector("OIDC and JWT", "authentication receipt"),
          connector("AWS API and events", "workflow and quality receipts"),
          connector("HTTPS and SQL", "decision and release receipts"),
        ],
      },
      {
        id: "executive-public",
        label: "Public evidence ingress",
        boundary: "External public evidence boundary",
        tone: "external",
        outsideProtectedBoundary: true,
        nodes: [
          node("public-sources", "Public source families", "USAspending, SBIR, Grants.gov, SAM.gov", "Government public endpoints remain authoritative and independently operated.", "External dependency"),
          node("public-quarantine", "Public-source quarantine", "Isolated S3 source and quarantine prefixes", "Unaccepted collections remain separate from the governed serving projection.", "Configured"),
          node("public-snapshot", "Accepted public snapshot", "Manifest and SHA-256 verified index", "Minimized records enter the evidence plane only after source and digest checks pass.", "Running now"),
        ],
        connectors: [
          connector("HTTPS pull", "source manifest and retrieval time"),
          connector("S3 object event", "acceptance or quarantine receipt"),
        ],
      },
    ],
    callouts: [
      "Human approval remains the decision boundary.",
      "Public evidence never silently merges into the synthetic portfolio.",
      "Every mutating operation retains actor, correlation, state, and digest evidence.",
    ],
  },
  {
    id: "il45",
    label: "IL4/IL5 target boundary",
    eyebrow: "Target deployment view",
    title: "Government boundary services surround a private mission enclave",
    summary: "The target pattern places application and data services inside an authorized Government landing zone and connects them through Government-furnished SCCA and identity services.",
    truth: "Target architecture only. The current commercial deployment is not IL4/IL5, does not have an ATO, and does not prove Government boundary integration.",
    lanes: [
      {
        id: "il45-current-edge",
        label: "Current demonstration edge",
        boundary: "Outside the target GovCloud protected boundary",
        tone: "external",
        outsideProtectedBoundary: true,
        nodes: [
          node("cloudfront-outside", "WAF and CloudFront", "Current commercial web edge", "CloudFront is intentionally shown outside the future protected enclave and is not represented as an IL4/IL5 boundary service.", "Running now"),
          node("approved-transfer", "Approved transfer seam", "Target ingress and content promotion", "A Government-approved publication and transfer process replaces direct commercial-to-enclave trust.", "Target control"),
        ],
        connectors: [connector("Approved content transfer", "release manifest and approval receipt")],
      },
      {
        id: "il45-access",
        label: "Government access path",
        boundary: "Government-furnished SCCA and identity services",
        tone: "external",
        outsideProtectedBoundary: true,
        nodes: [
          node("dod-icam", "DoD ICAM and CAC/PIV", "Federated mission identity", "The target accepts Government identity and device assurance instead of local demonstration credentials.", "External dependency"),
          node("cap-bcap", "CAP or BCAP", "DoD cloud access boundary", "Provides approved cloud connectivity and boundary defense for the mission partner path.", "External dependency"),
          node("vdss", "VDSS", "Virtual Data Center Security Stack", "Provides the target virtual enclave security inspection boundary around applications and data.", "External dependency"),
          node("private-ingress", "Private application ingress", "Approved load balancer or API ingress", "Terminates only approved traffic before it reaches application services in private subnets.", "Target control"),
        ],
        connectors: [
          connector("SAML or OIDC plus mTLS", "identity assurance receipt"),
          connector("DoD network path", "boundary connection log"),
          connector("Inspected TLS", "VDSS security event"),
        ],
      },
      {
        id: "il45-enclave",
        label: "Protected mission enclave",
        boundary: "Target IL4/IL5 Government cloud VPC",
        tone: "protected",
        nodes: [
          node("private-app", "Private application tier", "API, workflow, queue, compute", "No direct internet route. Workloads use least privilege roles and approved private service paths.", "Target control"),
          node("private-data", "Private data and ML tier", "Encrypted lake, database, model services", "Data stores, keys, model artifacts, and evidence remain inside approved account and network boundaries.", "Target control"),
          node("private-observe", "Security and audit plane", "Central logs, findings, traces, alerts", "Control evidence is exported to Government monitoring and incident-response services.", "Target control"),
        ],
        connectors: [
          connector("Private TLS and service endpoints", "application trace and policy receipt"),
          connector("Encrypted log subscription", "audit and finding receipt"),
        ],
      },
      {
        id: "il45-admin",
        label: "Privileged operations path",
        boundary: "Government-furnished managed services",
        tone: "external",
        outsideProtectedBoundary: true,
        nodes: [
          node("vdms", "VDMS", "Virtual Data Center Managed Services", "Provides target host security and privileged administration services.", "External dependency"),
          node("tccm", "TCCM", "Trusted Cloud Credential Manager", "Enforces target role-based and least-privilege cloud administration.", "External dependency"),
          node("privileged-session", "Controlled admin session", "Target enclave operations", "Administration enters through approved privileged paths with session evidence.", "Target control"),
        ],
        connectors: [
          connector("Managed admin channel", "host security event"),
          connector("Federated privileged access", "role and session receipt"),
        ],
      },
    ],
    callouts: [
      "CAP or BCAP, VDSS, VDMS, TCCM, and DoD ICAM are Government or enterprise dependencies, not deployed Compass components.",
      "Service authorization, control inheritance, eMASS evidence, CSSP integration, and an ATO require the selected Government environment.",
      "The application interfaces remain portable, but endpoint availability and approved service choices must be validated in the target enclave.",
    ],
  },
  {
    id: "lineage",
    label: "Data lineage",
    eyebrow: "Source to decision",
    title: "Every accepted record keeps its origin and every rejected record keeps its reason",
    summary: "File uploads and public-source snapshots enter through distinct gates, then converge only after validation into versioned Bronze, Silver, and Gold evidence.",
    truth: "The current design retains object, quality, workflow, model, and release evidence. Scheduled external acquisition is shown as configured until a recurring pull is observed live.",
    lanes: [
      {
        id: "lineage-file",
        label: "Authorized file drop",
        boundary: "Interactive governed intake",
        tone: "commercial",
        nodes: [
          node("file-source", "Authorized file", "JSON, CSV, or bounded document", "The uploader receives a server-selected destination and immutable correlation identifier.", "Running now"),
          node("immutable-landing", "Immutable landing", "KMS-encrypted S3 object", "The original bytes, object version, media type, size, and SHA-256 are retained.", "Running now"),
          node("inspect-quality", "Inspect and quality gate", "Step Functions and deterministic rules", "Schema, safety, extraction, required fields, relationships, and classification rules decide the path.", "Running now"),
          node("medallion-zones", "Bronze, Silver, Gold", "Versioned lake and curated store", "Raw, normalized, and decision-ready representations remain linked to the same source identity.", "Running now"),
          node("catalog-consumer", "Catalog to decision", "Lineage, intelligence, dashboard, export", "Consumers see the source, rule outcomes, model evidence, owner, steward, and release status.", "Running now"),
        ],
        connectors: [
          connector("HTTPS upload plan", "source and actor receipt"),
          connector("S3 object-created event", "object version and ingest receipt"),
          connector("Workflow task token", "rule-level quality receipt"),
          connector("SQL and governed API", "lineage and release receipts"),
        ],
      },
      {
        id: "lineage-public",
        label: "Public-source acquisition",
        boundary: "Isolated external-source quarantine",
        tone: "external",
        outsideProtectedBoundary: true,
        nodes: [
          node("external-feed", "Government public endpoint", "Source-owned API or file", "The source remains authoritative and may change independently of Compass.", "External dependency"),
          node("scheduled-collector", "Bounded collector", "Watermark, allowlist, rate limit", "A scheduled adapter records request time, source URI, terms, watermark, and response digest.", "Configured"),
          node("source-quarantine", "Public-source quarantine", "Isolated collection prefix", "Malformed, disallowed, duplicate, or unprofiled collections cannot enter the serving projection.", "Configured"),
          node("accepted-source", "Accepted source snapshot", "Immutable manifest and minimized records", "Only verified, policy-allowed fields move into the governed public evidence plane.", "Running now"),
        ],
        connectors: [
          connector("HTTPS with source policy", "retrieval and watermark receipt"),
          connector("Hash and schema gate", "quarantine reason receipt"),
          connector("Manifest promotion", "acceptance digest and snapshot ID"),
        ],
      },
      {
        id: "lineage-evidence",
        label: "Evidence spine",
        boundary: "Append-only lineage and audit evidence",
        tone: "evidence",
        nodes: [
          node("source-proof", "Source proof", "URI, object version, SHA-256", "Identifies the exact input bytes or public-source snapshot.", "Running now"),
          node("quality-proof", "Quality proof", "Rules, scores, accepted and rejected counts", "Explains why each batch or document advanced or stopped.", "Running now"),
          node("transform-proof", "Transformation proof", "Adapter, schema, stage, output digest", "Links Bronze, Silver, and Gold representations without exposing physical keys.", "Running now"),
          node("decision-proof", "Decision proof", "Model version, citations, reviewer, export digest", "Connects data and model evidence to a human decision and governed release.", "Running now"),
        ],
        connectors: [
          connector("Correlation ID", "ingestion receipt"),
          connector("Lineage edge", "transformation receipt"),
          connector("Evidence reference", "decision and release receipt"),
        ],
      },
    ],
    callouts: [
      "Quarantine is a terminal governed state, not a hidden deletion path.",
      "Physical S3 keys and sensitive fields stay out of browser projections.",
      "Replay starts from the immutable source and creates a new correlated execution receipt.",
    ],
  },
  {
    id: "devsecops",
    label: "DevSecOps",
    eyebrow: "Commit to verified release",
    title: "One revision carries code, policy, infrastructure, deployment, and rollback proof",
    summary: "The delivery path fails closed before promotion and uses short-lived AWS identity instead of committed cloud credentials.",
    truth: "Repository workflows and AWS deployment are active in the commercial prototype. Government runner, registry, signing, and promotion services remain target-environment decisions.",
    lanes: [
      {
        id: "devsecops-pipeline",
        label: "Golden delivery path",
        boundary: "Source and commercial deployment pipeline",
        tone: "commercial",
        nodes: [
          node("reviewed-change", "Reviewed change", "Pull request and protected branch", "A commit enters only through reviewable source control history.", "Running now"),
          node("security-gates", "Security gates", "Secrets, SAST, dependencies, SBOM", "Parallel scans stop promotion when a required policy fails.", "Running now"),
          node("quality-iac", "Quality and IaC gates", "Contracts, tests, SAM, Terraform, STIG policy", "Application behavior and infrastructure intent are validated together.", "Running now"),
          node("approval-oidc", "Approval and OIDC", "Protected environment and short-lived AWS role", "An explicit approval binds the reviewed revision to temporary deployment authority.", "Configured"),
          node("deploy-verify", "Deploy and verify", "CloudFormation, publication, DAST, smoke", "Deployment is followed by runtime checks against the promoted revision.", "Running now"),
          node("release-rollback", "Release or rollback", "Immutable receipt and previous known-good revision", "A failed gate stops release and retained revisions support recovery.", "Running now"),
        ],
        connectors: [
          connector("Git commit", "review and provenance receipt"),
          connector("CI artifacts", "scan and SBOM receipts"),
          connector("Plan digest", "test and policy receipts"),
          connector("OIDC role session", "approval and identity receipt"),
          connector("CloudFormation events", "smoke or rollback receipt"),
        ],
      },
      {
        id: "devsecops-target",
        label: "Target enclave promotion",
        boundary: "Government software factory and authorized artifact boundary",
        tone: "protected",
        nodes: [
          node("government-runner", "Government CI runner", "Approved software factory", "Executes the same source-controlled gates inside the authorized delivery boundary.", "Target control"),
          node("signed-artifact", "Signed artifact registry", "Approved images, packages, SBOM, attestations", "Only verified immutable artifacts are eligible for environment promotion.", "Target control"),
          node("environment-promotion", "Environment promotion", "Development, test, production approval", "Separate roles and evidence gates prevent unreviewed cross-environment changes.", "Target control"),
          node("government-monitoring", "CSSP and operations", "Findings, alerts, incident and rollback evidence", "Government monitoring receives the evidence required for response and authorization maintenance.", "External dependency"),
        ],
        connectors: [
          connector("Signed build output", "provenance attestation"),
          connector("Artifact digest", "promotion approval receipt"),
          connector("Encrypted telemetry", "finding and incident receipt"),
        ],
      },
    ],
    callouts: [
      "No long-lived AWS access key is required by the current GitHub deployment path.",
      "The same revision identifies frontend assets, infrastructure change set, runtime checks, and rollback target.",
      "A green pipeline is delivery evidence, not an ATO or an IL4/IL5 authorization.",
    ],
  },
  {
    id: "mlops",
    label: "MLOps",
    eyebrow: "Data to reviewed prediction",
    title: "A registered candidate scores governed records without making the decision",
    summary: "The current use case estimates a public Navy SBIR Phase I transition proxy from label-excluded records and retains training, evaluation, scoring, cost, and review evidence.",
    truth: "SageMaker training, Model Registry, and Batch Transform have executed in commercial AWS. The package remains PendingManualApproval, no persistent endpoint exists, and the result is not ONR mission success.",
    lanes: [
      {
        id: "mlops-run",
        label: "Governed model lifecycle",
        boundary: "Current commercial SageMaker evidence path",
        tone: "commercial",
        nodes: [
          node("training-snapshot", "Training snapshot", "11,287 public Navy SBIR rows", "A reproducible source manifest, chronological split, feature contract, and hashes bind the training input.", "Running now"),
          node("training-job", "Network-isolated training", "SageMaker training job", "A calibrated classical classifier trains with fixed images, parameters, time limits, and encrypted artifacts.", "Running now"),
          node("evaluation-gate", "Independent evaluation", "Chronological holdout and metric gates", "ROC AUC, Brier score, F1, calibration, and caveats are retained before registration.", "Running now"),
          node("model-registry", "Registered candidate", "SageMaker Model Registry", "The immutable package remains PendingManualApproval until a person approves promotion.", "Running now"),
          node("batch-scoring", "Ephemeral batch scoring", "SageMaker Batch Transform", "Newer label-excluded public records are scored without an always-on endpoint.", "Running now"),
          node("reviewed-output", "Prediction evidence", "Compass intelligence and review", "Per-record probabilities, input and output hashes, runtime, estimate-only cost, and review status are visible.", "Running now"),
        ],
        connectors: [
          connector("S3 manifest", "dataset and split receipt"),
          connector("Model artifact", "training and metric receipt"),
          connector("Registry API", "package version and approval state"),
          connector("Batch Transform API", "job, input, output, and cleanup receipt"),
          connector("Protected JSON API", "prediction and reviewer receipt"),
        ],
      },
      {
        id: "mlops-monitor",
        label: "Monitoring and controlled change",
        boundary: "Model evidence and human promotion controls",
        tone: "evidence",
        nodes: [
          node("accepted-baseline", "Accepted baseline", "Features, labels, confidence, vocabulary", "The approved candidate establishes versioned comparison distributions and thresholds.", "Configured"),
          node("drift-monitor", "Drift evaluation", "PSI, vocabulary coverage, confidence", "A bounded comparison recommends continue, investigate, or retrain without silently changing production state.", "Configured"),
          node("model-alert", "Model alert", "CloudWatch and notification adapter", "Threshold and execution failures create visible evidence for an assigned reviewer.", "Configured"),
          node("retrain-review", "Retrain and promote", "New candidate and four-eyes review", "A failed candidate leaves the current approved model unchanged and fully traceable.", "Configured"),
        ],
        connectors: [
          connector("Metric batch", "drift comparison receipt"),
          connector("Threshold event", "alert and owner receipt"),
          connector("Approval workflow", "candidate decision receipt"),
        ],
      },
    ],
    callouts: [
      "The model ranks evidence for review and never allocates funding or approves an award.",
      "Training evaluation is separate from the newer current cohort used for demonstration scoring.",
      "A persistent endpoint is intentionally absent to reduce idle cost and avoid implying an approved real-time production service.",
    ],
  },
];

export function briefingView(id: BriefingViewId): BriefingView {
  return BRIEFING_VIEWS.find((view) => view.id === id) ?? BRIEFING_VIEWS[0];
}
