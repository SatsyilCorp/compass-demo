export type EvidenceClass = "observed" | "derived" | "predicted";

export type PublicSource = {
  id: string;
  name: string;
  authority: string;
  recordCount: number | null;
  recordLabel: string;
  status: "persisted" | "scheduled" | "gated";
  lastObserved: string;
  use: string;
  url: string;
};

export type FundingFlow = {
  fiscalYear: number;
  observedUsd: number | null;
  forecastUsd: number | null;
  lowerUsd: number | null;
  upperUsd: number | null;
  isPartial?: boolean;
};

export type TechnologyArea = {
  id: string;
  label: string;
  fundingUsd: number | null;
  awards: number | null;
  publications: number | null;
  velocityPct: number | null;
  transitionProbability: number | null;
  evidence: EvidenceClass;
};

export type PortfolioProgram = {
  id: string;
  title: string;
  recipient: string;
  source: string;
  sourceUrl: string;
  awardAmountUsd: number | null;
  startDate: string;
  endDate: string;
  technologyArea: string | null;
  transitionProbability: number | null;
  impactPercentile: number | null;
  confidence: number | null;
  scopeNote: string;
  observedFacts: string[];
};

export type ModelCard = {
  id: string;
  name: string;
  objective: string;
  algorithm: string;
  target: string;
  status: "not-trained" | "candidate" | "validated" | "champion";
  metric: string;
  metricValue: number | null;
  metricLabel: string;
  trainingRecords: number;
  evidenceClass: EvidenceClass;
  caveat: string;
};

export type IntelligenceSnapshot = {
  generatedAt: string;
  asOfDate: string;
  corpus: {
    awards: number | null;
    contracts: number | null;
    candidateAwardValueUsd: number | null;
  };
  sources: PublicSource[];
  fundingFlow: FundingFlow[];
  technologyAreas: TechnologyArea[];
  programs: PortfolioProgram[];
  models: ModelCard[];
};

export type PublicRecordEvidenceClass =
  | EvidenceClass
  | "public_observed"
  | "public_derived"
  | "public_predicted";

export type PublicSnapshotEvidenceClass = "public_evidence";

export type PublicExplanationEvidenceClass =
  | PublicRecordEvidenceClass
  | "mixed_public_evidence"
  | "none";

export type PublicIntelligenceRecord = {
  record_id: string;
  source_id: string;
  title: string;
  summary: string;
  source_url: string;
  evidence_class: PublicRecordEvidenceClass;
  model_run_id: string | null;
  uncertainty: unknown;
  snapshot_id: string;
  record_sha256: string;
};

export type PublicIntelligenceSourceEvidence = {
  source_id: string;
  count: number | null;
  state: string;
  scope: string;
  url: string;
};

export type PublicIntelligenceModelEvidence = {
  model_id: string;
  model_run_id: string | null;
  state: string;
  approved: boolean;
  deployed: boolean;
};

export type PublicIntelligenceSnapshotSummary = {
  as_of_date?: string;
  candidate_scope?: {
    award_records?: number;
    grants?: number;
    contracts?: number;
    summed_award_amount_usd?: number;
    disclosure?: string;
  };
  observed_annual_obligations?: Array<{
    fiscal_year?: number;
    observed_obligations_usd?: number;
  }>;
  serving_index_records?: number;
  source_counts?: Record<string, number>;
  [key: string]: unknown;
};

export type PublicIntelligenceSnapshotResponse = {
  contract: "compass.public-intelligence.snapshot-response.v1";
  snapshot_id: string;
  snapshot_version: number;
  generated_at: string;
  as_of_at: string;
  evidence_class: PublicSnapshotEvidenceClass;
  provenance: {
    manifest_sha256: string;
    index_sha256: string;
    manifest_object_version: string | null;
    index_object_version: string | null;
  };
  identity_scope: { role: string; org_unit: string };
  snapshot: PublicIntelligenceSnapshotSummary;
  sources: PublicIntelligenceSourceEvidence[];
  models: PublicIntelligenceModelEvidence[];
  record_count: number;
  records: PublicIntelligenceRecord[];
  disclosure: string;
};

export type PublicIntelligenceExplainRequest = {
  question: string;
  record_ids?: string[];
  top_k?: number;
};

export type PublicIntelligenceCitation = {
  record_id: string;
  source_id: string;
  title: string;
  source_url: string;
  evidence_class: PublicRecordEvidenceClass;
  model_run_id: string | null;
  uncertainty: unknown;
  snapshot_id: string;
  record_sha256: string;
  citation_token: string;
};

export type PublicIntelligenceExplanationResponse = {
  contract: "compass.public-intelligence.explanation.v1";
  answer: string;
  grounded: boolean;
  refused: boolean;
  refusal_code: string | null;
  citations: PublicIntelligenceCitation[];
  evidence_class: PublicExplanationEvidenceClass;
  model_run_id: string | null;
  model_run_ids: string[];
  explanation_run_id: string;
  uncertainty: {
    level: string;
    basis: string;
    per_record: Array<{ record_id: string; value: unknown }>;
    limitations: string[];
  };
  generation: {
    provider: string;
    model_id: string | null;
    usage: unknown;
  };
  snapshot_id: string;
  identity_scope: { role: string; org_unit: string };
};
