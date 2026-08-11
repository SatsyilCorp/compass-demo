export type DocumentClass =
  | "grant_abstract"
  | "technical_report"
  | "publication_summary"
  | "patent_summary"
  | "investment_brief"
  | "financial_execution";

export type ClassificationResult = {
  label: DocumentClass;
  displayLabel: string;
  confidence: number;
  reviewRequired: boolean;
  matchedTerms: string[];
  probabilities: Record<DocumentClass, number>;
};

export type ModelVersion = {
  version: string;
  stage: "Archived" | "Candidate" | "Champion";
  accuracy: number;
  macroF1: number;
  trainingRecords: number;
  sourceRevision: string;
  registry: string;
  createdAt: string;
};

type ClassDefinition = {
  id: DocumentClass;
  label: string;
  purpose: string;
  keywords: string[];
};

export const DOCUMENT_CLASSES: readonly ClassDefinition[] = [
  {
    id: "grant_abstract",
    label: "Grant abstract",
    purpose: "Research intent, investigator, award, and planned outcomes",
    keywords: ["grant", "award", "principal", "investigator", "hypothesis", "research", "university", "milestone"],
  },
  {
    id: "technical_report",
    label: "Technical report",
    purpose: "Progress, engineering evidence, test results, and delivery risk",
    keywords: ["technical", "progress", "engineering", "test", "prototype", "performance", "deliverable", "risk"],
  },
  {
    id: "publication_summary",
    label: "Publication summary",
    purpose: "Published methods, results, citations, and scientific findings",
    keywords: ["publication", "paper", "journal", "conference", "citation", "methodology", "peer", "findings"],
  },
  {
    id: "patent_summary",
    label: "Patent summary",
    purpose: "Invention, claims, assignee, filing, and intellectual property",
    keywords: ["patent", "invention", "claims", "assignee", "filing", "inventor", "prior", "intellectual"],
  },
  {
    id: "investment_brief",
    label: "Investment brief",
    purpose: "Company, financing, market, dual-use potential, and readiness",
    keywords: ["investment", "startup", "company", "venture", "valuation", "market", "revenue", "financing"],
  },
  {
    id: "financial_execution",
    label: "Financial execution",
    purpose: "Budget, obligation, expenditure, forecast, and variance",
    keywords: ["budget", "obligation", "expenditure", "forecast", "variance", "fiscal", "funding", "invoice"],
  },
] as const;

export const REVIEW_THRESHOLD = 0.62;

export const MODEL_VERSIONS: readonly ModelVersion[] = [
  {
    version: "1",
    stage: "Archived",
    accuracy: 0.84,
    macroF1: 0.82,
    trainingRecords: 720,
    sourceRevision: "0f38c3a",
    registry: "SageMaker Model Registry",
    createdAt: "2026-08-08T17:20:00Z",
  },
  {
    version: "2",
    stage: "Champion",
    accuracy: 0.91,
    macroF1: 0.9,
    trainingRecords: 1_200,
    sourceRevision: "candidate",
    registry: "SageMaker Model Registry",
    createdAt: "2026-08-11T18:42:00Z",
  },
  {
    version: "3",
    stage: "Candidate",
    accuracy: 0.93,
    macroF1: 0.92,
    trainingRecords: 1_440,
    sourceRevision: "candidate",
    registry: "SageMaker Model Registry",
    createdAt: "2026-08-11T19:06:00Z",
  },
] as const;

const EMPTY_PROBABILITIES: Record<DocumentClass, number> = {
  grant_abstract: 0,
  technical_report: 0,
  publication_summary: 0,
  patent_summary: 0,
  investment_brief: 0,
  financial_execution: 0,
};

function tokens(value: string): string[] {
  return value.toLowerCase().match(/[a-z][a-z0-9_-]{1,39}/g) ?? [];
}

export function displayDocumentClass(value: DocumentClass): string {
  return DOCUMENT_CLASSES.find((item) => item.id === value)?.label ?? value;
}

export function classifyDocument(text: string, filename = "document.txt"): ClassificationResult {
  const input = tokens(`${filename} ${text}`);
  const tokenSet = new Set(input);
  const scores = DOCUMENT_CLASSES.map((definition) => {
    const matchedTerms = definition.keywords.filter((keyword) => tokenSet.has(keyword));
    return { definition, matchedTerms, score: 1 + matchedTerms.length * 2 };
  });
  const total = scores.reduce((sum, item) => sum + item.score, 0);
  const probabilities = { ...EMPTY_PROBABILITIES };
  for (const item of scores) probabilities[item.definition.id] = item.score / total;
  const winner = [...scores].sort((a, b) => b.score - a.score || a.definition.id.localeCompare(b.definition.id))[0];
  const evidenceRatio = winner.matchedTerms.length / Math.max(3, Math.min(8, input.length));
  const confidence = Math.min(0.98, Number((0.46 + evidenceRatio * 0.7).toFixed(2)));
  probabilities[winner.definition.id] = confidence;
  const remaining = 1 - confidence;
  const otherTotal = scores.filter((item) => item.definition.id !== winner.definition.id).reduce((sum, item) => sum + item.score, 0);
  for (const item of scores) {
    if (item.definition.id !== winner.definition.id) probabilities[item.definition.id] = remaining * item.score / otherTotal;
    probabilities[item.definition.id] = Number(probabilities[item.definition.id].toFixed(4));
  }
  return {
    label: winner.definition.id,
    displayLabel: winner.definition.label,
    confidence,
    reviewRequired: confidence < REVIEW_THRESHOLD,
    matchedTerms: winner.matchedTerms,
    probabilities,
  };
}

export function modelPromotionDecision(model: ModelVersion): "approve" | "hold" {
  return model.accuracy >= 0.9 && model.macroF1 >= 0.88 ? "approve" : "hold";
}

export function driftDecision(psi: number, meanConfidence: number): {
  detected: boolean;
  action: "continue-monitoring" | "retrain-and-review";
} {
  const detected = psi > 0.25 || meanConfidence < 0.55;
  return { detected, action: detected ? "retrain-and-review" : "continue-monitoring" };
}
