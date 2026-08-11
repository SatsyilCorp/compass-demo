variable "aws_region" {
  description = "AWS region for the Compass deployment."
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Stable lowercase deployment name."
  type        = string
  default     = "compass"

  validation {
    condition     = can(regex("^[a-z][a-z0-9-]{2,30}$", var.project_name))
    error_message = "project_name must be a lowercase AWS-safe name."
  }
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "demo"

  validation {
    condition     = contains(["demo", "test", "production"], var.environment)
    error_message = "environment must be demo, test, or production."
  }
}

variable "document_lake_bucket_name" {
  description = "Existing private S3 data lake bucket with EventBridge notifications enabled."
  type        = string
}

variable "document_lake_bucket_arn" {
  description = "ARN of document_lake_bucket_name."
  type        = string
}

variable "kms_key_arn" {
  description = "Customer-managed KMS key protecting the data lake and DynamoDB table."
  type        = string
}

variable "http_api_id" {
  description = "Existing protected API Gateway HTTP API identifier."
  type        = string
}

variable "http_api_execution_arn" {
  description = "Execution ARN of the existing protected HTTP API."
  type        = string
}

variable "http_api_authorizer_id" {
  description = "Existing Cognito JWT authorizer identifier."
  type        = string
}

variable "common_layer_arn" {
  description = "Versioned Compass common Lambda layer ARN."
  type        = string
}

variable "lambda_artifact_bucket" {
  description = "S3 bucket containing the reviewed document_ml Lambda ZIP."
  type        = string
}

variable "lambda_artifact_key" {
  description = "Immutable S3 key containing the reviewed document_ml Lambda ZIP."
  type        = string
}

variable "lambda_artifact_version" {
  description = "Optional immutable S3 object version for the Lambda artifact."
  type        = string
  default     = null
}

variable "mlops_mode" {
  description = "demo runs the deterministic adapter; sagemaker submits an approved job."
  type        = string
  default     = "demo"

  validation {
    condition     = contains(["demo", "sagemaker"], var.mlops_mode)
    error_message = "mlops_mode must be demo or sagemaker."
  }
}

variable "sagemaker_training_image" {
  description = "Approved ECR training image URI required only for sagemaker mode."
  type        = string
  default     = ""
}
