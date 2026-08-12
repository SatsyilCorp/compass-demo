import assert from "node:assert/strict";
import test from "node:test";

import {
  isTerminalModelExecutionStatus,
  parsePublicModelExecutionList,
  parsePublicModelExecutionReceipt,
} from "./model-execution";

function receipt(status: "SUBMITTED" | "IN_PROGRESS" | "COMPLETED") {
  return {
    contract: "compass.public-intelligence.model-execution.v1",
    executionId: "mx-01HZZ",
    status,
    createdAt: "2026-08-12T15:00:00Z",
    updatedAt: "2026-08-12T15:01:00Z",
    completedAt: status === "COMPLETED" ? "2026-08-12T15:01:00Z" : null,
    purpose: "bounded_public_validation",
    executionMode: "sagemaker_batch_transform",
    model: {
      name: "compass-demo-public-sbir-transition",
      packageArn: "arn:aws:sagemaker:us-east-1:111122223333:model-package/example/2",
      packageVersion: "2",
      approvalStatus: "PendingManualApproval",
      candidateOnly: true,
      trainingJobArn: "arn:aws:sagemaker:us-east-1:111122223333:training-job/example",
      modelArtifactSha256: "a".repeat(64),
    },
    input: { recordCount: 8, sha256: "b".repeat(64) },
    execution: {
      transformJobArn: status === "SUBMITTED" ? null : "arn:aws:sagemaker:us-east-1:111122223333:transform-job/example",
      transformJobName: status === "SUBMITTED" ? null : "example",
      instanceType: "ml.m5.large",
      instanceCount: 1,
      networkIsolation: true,
    },
    output: status === "COMPLETED" ? {
      predictionCount: 8,
      sha256: "c".repeat(64),
      predictions: Array.from({ length: 8 }, (_, index) => ({
        recordId: `sbir-${index + 1}`,
        observedPublicTransitionProbability: 0.64,
        candidateLabel: "transition_proxy_positive",
        semantics: "Public transition proxy only",
        humanReviewRequired: true,
      })),
    } : null,
    cost: status === "COMPLETED" ? {
      observedDurationSeconds: 42,
      estimatedComputeUsd: 0.007,
      estimateOnly: true,
    } : null,
    provenance: status === "COMPLETED" ? {
      receiptSha256: "d".repeat(64),
      inputVersionId: "input-v1",
      outputVersionId: "output-v1",
    } : null,
    humanReviewRequired: true,
    disclosure: "Candidate output requires human review and is not a mission-success decision.",
    failure: null,
  };
}

test("parses submitted and completed backend execution receipts without filling missing evidence", () => {
  const submitted = parsePublicModelExecutionReceipt(receipt("SUBMITTED"));
  assert.equal(submitted?.status, "SUBMITTED");
  assert.equal(submitted?.execution.transformJobArn, null);
  assert.equal(submitted?.output, null);

  const completed = parsePublicModelExecutionReceipt(receipt("COMPLETED"));
  assert.equal(completed?.output?.predictionCount, 8);
  assert.equal(completed?.output?.predictions[0]?.recordId, "sbir-1");
  assert.equal(completed?.cost?.estimateOnly, true);
});

test("rejects a registry record or incomplete object as execution evidence", () => {
  assert.equal(parsePublicModelExecutionReceipt({
    modelPackageArn: "arn:aws:sagemaker:example",
    approvalStatus: "PendingManualApproval",
  }), null);
  assert.equal(parsePublicModelExecutionReceipt({ ...receipt("COMPLETED"), output: null }), null);
});

test("terminal status helper polls only active executions", () => {
  assert.equal(isTerminalModelExecutionStatus("SUBMITTED"), false);
  assert.equal(isTerminalModelExecutionStatus("IN_PROGRESS"), false);
  assert.equal(isTerminalModelExecutionStatus("COMPLETED"), true);
  assert.equal(isTerminalModelExecutionStatus("FAILED"), true);
  assert.equal(isTerminalModelExecutionStatus("STOPPED"), true);
});

test("normalizes numeric package versions and labels from the SageMaker receipt", () => {
  const value = receipt("COMPLETED");
  value.model.packageVersion = 2 as unknown as string;
  value.output!.predictions[0]!.candidateLabel = 1 as unknown as string;
  const parsed = parsePublicModelExecutionReceipt(value);
  assert.equal(parsed?.model.packageVersion, "2");
  assert.equal(parsed?.output?.predictions[0]?.candidateLabel, "1");
});

test("parses the durable execution history without accepting partial rows", () => {
  const parsed = parsePublicModelExecutionList({
    contract: "compass.public-intelligence.model-execution-list.v1",
    executions: [receipt("COMPLETED"), receipt("IN_PROGRESS")],
  });
  assert.equal(parsed?.executions.length, 2);
  assert.equal(parsePublicModelExecutionList({ executions: [receipt("COMPLETED")] }), null);
});
