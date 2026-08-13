export type OverallArchitectureGroupId =
  | "actors"
  | "edge"
  | "network"
  | "endpoints"
  | "application"
  | "regional-compute"
  | "relational"
  | "ingestion"
  | "scale"
  | "ml"
  | "security"
  | "operations"
  | "delivery";

export type OverallArchitectureGroup = {
  id: OverallArchitectureGroupId;
  label: string;
  boundary: string;
  step: number | null;
  componentIds: readonly string[];
};

export const OVERALL_FLOW_STEPS = [
  { number: 1, label: "Access", detail: "WAF, web edge, identity" },
  { number: 2, label: "Acquire", detail: "Independent real source connectors" },
  { number: 3, label: "Orchestrate", detail: "Events, workflows, queues" },
  { number: 4, label: "Validate", detail: "Normalize, quality, quarantine" },
  { number: 5, label: "Govern", detail: "Lake, catalog, owners, lineage" },
  { number: 6, label: "Link and analyze", detail: "Identity graph, models, RAG" },
  { number: 7, label: "Decide", detail: "Brief, approval, export" },
  { number: 8, label: "Prove", detail: "Audit, alarms, release evidence" },
] as const;

export const VPC_LAMBDA_COMPONENT_IDS = [
  "intake",
  "quality",
  "catalog",
  "analytics",
  "dashboard",
  "summarize",
  "rag",
  "approvals",
  "license",
  "export",
  "evidence",
  "rmf",
  "migrator",
] as const;

export const REGIONAL_LAMBDA_COMPONENT_IDS = [
  "authorizer",
  "document-ml",
  "public-acquisition",
  "operations-api",
  "public-intelligence",
  "scale-control",
  "scale-worker",
  "scale-export",
] as const;

export const GATEWAY_ENDPOINT_COMPONENT_IDS = [
  "s3-gateway-endpoint",
  "dynamodb-gateway-endpoint",
] as const;

export const OVERALL_ARCHITECTURE_GROUPS: OverallArchitectureGroup[] = [
  {
    id: "actors",
    label: "Mission actors",
    boundary: "Outside the AWS account",
    step: 1,
    componentIds: ["personas"],
  },
  {
    id: "edge",
    label: "Edge, web, identity, and API",
    boundary: "AWS global and regional managed services outside the VPC",
    step: 1,
    componentIds: ["waf", "cloudfront", "web-bucket", "cognito", "http-api"],
  },
  {
    id: "network",
    label: "VPC routing and workload controls",
    boundary: "10.42.0.0/16 across two availability zones",
    step: 3,
    componentIds: ["vpc", "internet-gateway", "public-subnets", "nat-gateway", "private-subnets", "lambda-sg", "db-sg"],
  },
  {
    id: "endpoints",
    label: "Private AWS service routes",
    boundary: "Gateway endpoints attached to the private route table",
    step: 3,
    componentIds: GATEWAY_ENDPOINT_COMPONENT_IDS,
  },
  {
    id: "application",
    label: "Private application services",
    boundary: "Lambda network interfaces in private subnets A and B",
    step: 4,
    componentIds: VPC_LAMBDA_COMPONENT_IDS,
  },
  {
    id: "regional-compute",
    label: "Regional Lambda adapters",
    boundary: "AWS regional Lambda service plane without customer VPC attachment",
    step: 4,
    componentIds: REGIONAL_LAMBDA_COMPONENT_IDS,
  },
  {
    id: "relational",
    label: "Private relational data tier",
    boundary: "Aurora subnet group in private subnets A and B",
    step: 5,
    componentIds: ["aurora-writer", "aurora-reader"],
  },
  {
    id: "ingestion",
    label: "Ingestion, events, and operational stream",
    boundary: "AWS regional managed service plane outside the VPC",
    step: 2,
    componentIds: ["raw-bucket", "demo-stream", "eventbridge", "intake-workflow", "ticker"],
  },
  {
    id: "scale",
    label: "Scale, lake, catalog, and asynchronous export",
    boundary: "AWS regional managed service plane outside the VPC",
    step: 5,
    componentIds: [
      "scale-workflow",
      "scale-ledger",
      "worker-queue",
      "worker-dlq",
      "scale-lake",
      "glue",
      "lake-formation",
      "athena",
      "export-queue",
      "export-dlq",
    ],
  },
  {
    id: "ml",
    label: "AI, document processing, and model governance",
    boundary: "AWS regional AI services and governed model evidence",
    step: 6,
    componentIds: ["bedrock", "document-workflow", "document-ledger", "sagemaker", "model-monitor"],
  },
  {
    id: "security",
    label: "Identity, encryption, and threat protection",
    boundary: "Cross-cutting security control plane",
    step: 8,
    componentIds: ["kms", "secrets", "iam", "guardduty", "securityhub", "macie"],
  },
  {
    id: "operations",
    label: "Telemetry, alarms, dashboards, and tracing",
    boundary: "Cross-cutting operations and evidence plane",
    step: 8,
    componentIds: ["cloudwatch-logs", "cloudwatch-alarms", "cloudwatch-dashboards", "xray"],
  },
  {
    id: "delivery",
    label: "DevSecOps and infrastructure delivery",
    boundary: "Source control to immutable AWS deployment",
    step: null,
    componentIds: ["github-actions", "terraform", "cloudformation"],
  },
];

export function overallGroup(id: OverallArchitectureGroupId): OverallArchitectureGroup {
  const group = OVERALL_ARCHITECTURE_GROUPS.find((candidate) => candidate.id === id);
  if (!group) throw new Error(`Unknown overall architecture group: ${id}`);
  return group;
}

export function allOverallComponentIds(): string[] {
  return OVERALL_ARCHITECTURE_GROUPS.flatMap((group) => [...group.componentIds]);
}
