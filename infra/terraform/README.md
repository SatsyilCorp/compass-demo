# Terraform deployment slice

This module is the Terraform implementation of the AWS-native document and
MLOps slice. It attaches to the existing protected Compass API, KMS key, common
Lambda layer, and private S3 lake. Do not apply it to the same environment as
the equivalent resources in `template.yaml`.

The CI pipeline runs formatting, validation, policy checks, and a plan before a
protected environment can apply a reviewed artifact. The Lambda ZIP must be an
immutable CI artifact containing `src/functions/document_ml` and its pinned
dependencies. The S3 bucket must already have EventBridge notifications
enabled and browser CORS restricted to approved Compass origins.

`mlops_mode = "demo"` is the cost-bounded default. It runs the source classical
model and clearly labels that no SageMaker endpoint exists. Set
`mlops_mode = "sagemaker"` only with an approved training image. The runtime
then submits the bounded, network-isolated SageMaker job described by the
backend adapter.
