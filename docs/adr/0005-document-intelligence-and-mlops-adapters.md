# ADR 0005: Separate document intelligence contracts from MLOps adapters

Status: Accepted

## Context

The demonstration must show browser document drops, schema inference,
bronze-silver-gold processing, quality and quarantine, classical model
training, registry state, deployment, and drift. The AWS account may not yet
have a Government-approved SageMaker training image or an approved endpoint
cost posture. Treating a local classifier result as a SageMaker execution would
make the evidence misleading.

## Decision

Compass owns one deep document intelligence module with pure extraction,
quality, six-class taxonomy, training, evaluation, inference, and drift
interfaces. S3, DynamoDB, Step Functions, and EventBridge provide the durable
AWS-native data plane.

The MLOps Adapter is an explicit seam:

- `demo` runs the inspectable deterministic multinomial Naive Bayes model and
  labels the deployment target as an offline Lambda adapter.
- `sagemaker` submits a bounded job only when an execution role and approved
  training image are configured. Missing configuration produces a
  `not-submitted` receipt rather than a synthetic job identifier.

Every artifact is content-addressed or digest-bound. Champion promotion is a
metric-gated, separate write with a Deployment Receipt, and low-confidence
classifications are marked for human review. Drift is measured through
population stability and out-of-vocabulary rate.

## Consequences

The full business flow is runnable offline and on AWS without a long-lived ML
endpoint. A production SageMaker container, Model Package approval workflow,
and endpoint monitoring schedule remain deployment inputs, not hidden demo
assumptions. Both AWS and Databricks variants can share the exact taxonomy,
split seed, and evaluation contract.
