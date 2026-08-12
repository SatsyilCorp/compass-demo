export const MODEL_EXECUTION_STATUSES = [
  "SUBMITTED",
  "IN_PROGRESS",
  "COMPLETED",
  "FAILED",
  "STOPPED",
] as const;

export type ModelExecutionStatus = (typeof MODEL_EXECUTION_STATUSES)[number];

export type ModelExecutionPrediction = {
  recordId: string;
  observedPublicTransitionProbability: number;
  candidateLabel: string;
  semantics: string;
  humanReviewRequired: boolean;
};

export type PublicModelExecutionReceipt = {
  contract: "compass.public-intelligence.model-execution.v1";
  executionId: string;
  status: ModelExecutionStatus;
  createdAt: string;
  updatedAt: string;
  completedAt: string | null;
  purpose: "bounded_public_validation";
  executionMode: "sagemaker_batch_transform";
  model: {
    name: string;
    packageArn: string;
    packageVersion: string;
    approvalStatus: string;
    candidateOnly: boolean;
    trainingJobArn: string;
    modelArtifactSha256: string;
  };
  input: {
    recordCount: number;
    sha256: string;
  };
  execution: {
    transformJobArn: string | null;
    transformJobName: string | null;
    instanceType: string;
    instanceCount: number;
    networkIsolation: boolean;
  };
  output: {
    predictionCount: number;
    sha256: string;
    predictions: ModelExecutionPrediction[];
  } | null;
  cost: {
    observedDurationSeconds: number | null;
    estimatedComputeUsd: number | null;
    estimateOnly: boolean;
  } | null;
  provenance: {
    receiptSha256: string;
    inputVersionId: string | null;
    outputVersionId: string | null;
  } | null;
  humanReviewRequired: true;
  disclosure: string;
  failure: {
    code: string;
    message: string;
  } | null;
};

export type PublicModelExecutionList = {
  contract: "compass.public-intelligence.model-execution-list.v1";
  executions: PublicModelExecutionReceipt[];
};

const STATUS_SET = new Set<string>(MODEL_EXECUTION_STATUSES);
const SHA256_PATTERN = /^[a-f0-9]{64}$/;

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function stringValue(value: unknown): string | null {
  return typeof value === "string" && value.trim().length > 0 ? value : null;
}

function identifierValue(value: unknown): string | null {
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return stringValue(value);
}

function nullableString(value: unknown): string | null | undefined {
  return value === null ? null : stringValue(value) ?? undefined;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function nonNegativeInteger(value: unknown): number | null {
  return typeof value === "number" && Number.isInteger(value) && value >= 0 ? value : null;
}

function parsePrediction(value: unknown): ModelExecutionPrediction | null {
  if (!isObject(value)) return null;
  const recordId = stringValue(value.recordId);
  const probability = finiteNumber(value.observedPublicTransitionProbability);
  const candidateLabel = identifierValue(value.candidateLabel);
  const semantics = stringValue(value.semantics);
  if (
    !recordId ||
    probability === null ||
    probability < 0 ||
    probability > 1 ||
    !candidateLabel ||
    !semantics ||
    typeof value.humanReviewRequired !== "boolean"
  ) {
    return null;
  }
  return {
    recordId,
    observedPublicTransitionProbability: probability,
    candidateLabel,
    semantics,
    humanReviewRequired: value.humanReviewRequired,
  };
}

export function parsePublicModelExecutionReceipt(
  value: unknown,
): PublicModelExecutionReceipt | null {
  if (!isObject(value)) return null;
  const model = value.model;
  const input = value.input;
  const execution = value.execution;
  if (!isObject(model) || !isObject(input) || !isObject(execution)) return null;

  const executionId = stringValue(value.executionId);
  const status = stringValue(value.status);
  const createdAt = stringValue(value.createdAt);
  const updatedAt = stringValue(value.updatedAt);
  const completedAt = nullableString(value.completedAt);
  const modelName = stringValue(model.name);
  const packageArn = stringValue(model.packageArn);
  const packageVersion = identifierValue(model.packageVersion);
  const approvalStatus = stringValue(model.approvalStatus);
  const trainingJobArn = stringValue(model.trainingJobArn);
  const modelArtifactSha256 = stringValue(model.modelArtifactSha256);
  const recordCount = nonNegativeInteger(input.recordCount);
  const inputSha256 = stringValue(input.sha256);
  const transformJobArn = nullableString(execution.transformJobArn);
  const transformJobName = nullableString(execution.transformJobName);
  const instanceType = stringValue(execution.instanceType);
  const instanceCount = nonNegativeInteger(execution.instanceCount);

  if (
    value.contract !== "compass.public-intelligence.model-execution.v1" ||
    !executionId ||
    !status ||
    !STATUS_SET.has(status) ||
    !createdAt ||
    !updatedAt ||
    completedAt === undefined ||
    value.purpose !== "bounded_public_validation" ||
    value.executionMode !== "sagemaker_batch_transform" ||
    !modelName ||
    !packageArn ||
    !packageVersion ||
    !approvalStatus ||
    typeof model.candidateOnly !== "boolean" ||
    !trainingJobArn ||
    !modelArtifactSha256 ||
    !SHA256_PATTERN.test(modelArtifactSha256) ||
    recordCount === null ||
    recordCount < 1 ||
    recordCount > 25 ||
    !inputSha256 ||
    !SHA256_PATTERN.test(inputSha256) ||
    transformJobArn === undefined ||
    transformJobName === undefined ||
    !instanceType ||
    instanceCount === null ||
    instanceCount < 1 ||
    typeof execution.networkIsolation !== "boolean" ||
    value.humanReviewRequired !== true ||
    !stringValue(value.disclosure)
  ) {
    return null;
  }

  let output: PublicModelExecutionReceipt["output"] = null;
  if (value.output !== null) {
    if (!isObject(value.output)) return null;
    const predictionCount = nonNegativeInteger(value.output.predictionCount);
    const sha256 = stringValue(value.output.sha256);
    if (predictionCount === null || !sha256 || !Array.isArray(value.output.predictions)) return null;
    const predictions = value.output.predictions.map(parsePrediction);
    if (predictions.some((prediction) => prediction === null)) return null;
    if (predictionCount !== predictions.length || predictionCount !== recordCount) return null;
    if (!SHA256_PATTERN.test(sha256)) return null;
    output = {
      predictionCount,
      sha256,
      predictions: predictions as ModelExecutionPrediction[],
    };
  }

  let cost: PublicModelExecutionReceipt["cost"] = null;
  if (value.cost !== null) {
    if (!isObject(value.cost)) return null;
    const observedDurationSeconds = value.cost.observedDurationSeconds === null
      ? null
      : finiteNumber(value.cost.observedDurationSeconds);
    const estimatedComputeUsd = value.cost.estimatedComputeUsd === null
      ? null
      : finiteNumber(value.cost.estimatedComputeUsd);
    if (
      (value.cost.observedDurationSeconds !== null && observedDurationSeconds === null) ||
      (value.cost.estimatedComputeUsd !== null && estimatedComputeUsd === null) ||
      (observedDurationSeconds !== null && observedDurationSeconds < 0) ||
      (estimatedComputeUsd !== null && estimatedComputeUsd < 0) ||
      typeof value.cost.estimateOnly !== "boolean"
    ) {
      return null;
    }
    cost = { observedDurationSeconds, estimatedComputeUsd, estimateOnly: value.cost.estimateOnly };
  }

  let provenance: PublicModelExecutionReceipt["provenance"] = null;
  if (value.provenance !== null) {
    if (!isObject(value.provenance)) return null;
    const receiptSha256 = stringValue(value.provenance.receiptSha256);
    const inputVersionId = nullableString(value.provenance.inputVersionId);
    const outputVersionId = nullableString(value.provenance.outputVersionId);
    if (
      !receiptSha256 ||
      !SHA256_PATTERN.test(receiptSha256) ||
      inputVersionId === undefined ||
      outputVersionId === undefined
    ) return null;
    provenance = { receiptSha256, inputVersionId, outputVersionId };
  }

  if (status === "COMPLETED" && (!output || !cost || !provenance)) return null;
  if (status === "COMPLETED" && completedAt === null) return null;
  if (status !== "COMPLETED" && (output !== null || cost !== null)) return null;
  if (status !== "COMPLETED" && completedAt !== null && status !== "FAILED" && status !== "STOPPED") return null;
  if (status === "COMPLETED" && (transformJobArn === null || transformJobName === null)) return null;

  let failure: PublicModelExecutionReceipt["failure"] = null;
  if (isObject(value.failure)) {
    const code = stringValue(value.failure.code);
    const message = stringValue(value.failure.message);
    if (code && message) failure = { code, message };
  }

  return {
    contract: value.contract,
    executionId,
    status: status as ModelExecutionStatus,
    createdAt,
    updatedAt,
    completedAt,
    purpose: value.purpose,
    executionMode: value.executionMode,
    model: {
      name: modelName,
      packageArn,
      packageVersion,
      approvalStatus,
      candidateOnly: model.candidateOnly,
      trainingJobArn,
      modelArtifactSha256,
    },
    input: { recordCount, sha256: inputSha256 },
    execution: {
      transformJobArn,
      transformJobName,
      instanceType,
      instanceCount,
      networkIsolation: execution.networkIsolation,
    },
    output,
    cost,
    provenance,
    humanReviewRequired: true,
    disclosure: value.disclosure as string,
    failure,
  };
}

export function isTerminalModelExecutionStatus(status: ModelExecutionStatus): boolean {
  return status === "COMPLETED" || status === "FAILED" || status === "STOPPED";
}

export function parsePublicModelExecutionList(value: unknown): PublicModelExecutionList | null {
  if (!isObject(value) || value.contract !== "compass.public-intelligence.model-execution-list.v1" || !Array.isArray(value.executions)) return null;
  const executions = value.executions.map(parsePublicModelExecutionReceipt);
  if (executions.some((execution) => execution === null)) return null;
  return {
    contract: value.contract,
    executions: executions as PublicModelExecutionReceipt[],
  };
}
