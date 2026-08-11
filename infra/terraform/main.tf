locals {
  name = "${var.project_name}-${var.environment}-document-ml"
  routes = toset([
    "GET /documents/runs",
    "GET /documents/runs/{run_id}",
    "GET /ml/models",
    "GET /ml/ops/evidence",
    "POST /documents/uploads",
    "POST /ml/drift/evaluate",
    "POST /ml/models/{version}/deploy",
    "POST /ml/train",
  ])
}

resource "aws_dynamodb_table" "document_ml" {
  name         = local.name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "pk"
  range_key    = "sk"

  attribute {
    name = "pk"
    type = "S"
  }

  attribute {
    name = "sk"
    type = "S"
  }

  attribute {
    name = "gsi1pk"
    type = "S"
  }

  attribute {
    name = "gsi1sk"
    type = "S"
  }

  global_secondary_index {
    name            = "by-type"
    hash_key        = "gsi1pk"
    range_key       = "gsi1sk"
    projection_type = "ALL"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled     = true
    kms_key_arn = var.kms_key_arn
  }
}

resource "aws_sagemaker_model_package_group" "document_classifier" {
  model_package_group_name        = "${local.name}-classifier"
  model_package_group_description = "Governed Compass document classifier versions"
}

data "aws_iam_policy_document" "sagemaker_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["sagemaker.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "sagemaker" {
  name               = "${local.name}-sagemaker"
  assume_role_policy = data.aws_iam_policy_document.sagemaker_assume.json
}

data "aws_iam_policy_document" "sagemaker" {
  statement {
    sid       = "ListTrainingPrefix"
    effect    = "Allow"
    actions   = ["s3:GetBucketLocation", "s3:ListBucket"]
    resources = [var.document_lake_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["mlops/*"]
    }
  }

  statement {
    sid       = "TrainingArtifacts"
    effect    = "Allow"
    actions   = ["s3:AbortMultipartUpload", "s3:GetObject", "s3:PutObject"]
    resources = ["${var.document_lake_bucket_arn}/mlops/*"]
  }

  statement {
    sid       = "TrainingArtifactEncryption"
    effect    = "Allow"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
    resources = [var.kms_key_arn]
  }
}

resource "aws_iam_role_policy" "sagemaker" {
  name   = "training-artifacts"
  role   = aws_iam_role.sagemaker.id
  policy = data.aws_iam_policy_document.sagemaker.json
}

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "lambda" {
  name               = "${local.name}-lambda"
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "lambda" {
  statement {
    sid     = "WriteFunctionLogs"
    effect  = "Allow"
    actions = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = [
      "${aws_cloudwatch_log_group.lambda.arn}:*",
    ]
  }

  statement {
    sid       = "ListDocumentPrefixes"
    effect    = "Allow"
    actions   = ["s3:GetBucketLocation", "s3:ListBucket"]
    resources = [var.document_lake_bucket_arn]

    condition {
      test     = "StringLike"
      variable = "s3:prefix"
      values   = ["documents/*", "mlops/*"]
    }
  }

  statement {
    sid     = "DocumentObjects"
    effect  = "Allow"
    actions = ["s3:AbortMultipartUpload", "s3:GetObject", "s3:PutObject"]
    resources = [
      "${var.document_lake_bucket_arn}/documents/*",
      "${var.document_lake_bucket_arn}/mlops/*",
    ]
  }

  statement {
    sid       = "DocumentEncryption"
    effect    = "Allow"
    actions   = ["kms:Decrypt", "kms:Encrypt", "kms:GenerateDataKey"]
    resources = [var.kms_key_arn]
  }

  statement {
    sid       = "DocumentLedger"
    effect    = "Allow"
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:Query", "dynamodb:UpdateItem"]
    resources = [aws_dynamodb_table.document_ml.arn, "${aws_dynamodb_table.document_ml.arn}/index/by-type"]
  }

  statement {
    sid     = "BoundedSageMakerTraining"
    effect  = "Allow"
    actions = ["sagemaker:CreateTrainingJob", "sagemaker:DescribeTrainingJob", "sagemaker:StopTrainingJob"]
    resources = [
      "arn:${data.aws_partition.current.partition}:sagemaker:${var.aws_region}:${data.aws_caller_identity.current.account_id}:training-job/compass-doc-*",
    ]
  }

  statement {
    sid       = "PassTrainingRole"
    effect    = "Allow"
    actions   = ["iam:PassRole"]
    resources = [aws_iam_role.sagemaker.arn]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["sagemaker.amazonaws.com"]
    }
  }
}

data "aws_partition" "current" {}
data "aws_caller_identity" "current" {}

resource "aws_iam_role_policy" "lambda" {
  name   = "document-ml"
  role   = aws_iam_role.lambda.id
  policy = data.aws_iam_policy_document.lambda.json
}

resource "aws_cloudwatch_log_group" "lambda" {
  name              = "/aws/lambda/${local.name}"
  retention_in_days = 14
  kms_key_id        = var.kms_key_arn
}

resource "aws_lambda_function" "document_ml" {
  function_name     = local.name
  role              = aws_iam_role.lambda.arn
  handler           = "app.handler"
  runtime           = "python3.12"
  architectures     = ["arm64"]
  memory_size       = 1024
  timeout           = 120
  s3_bucket         = var.lambda_artifact_bucket
  s3_key            = var.lambda_artifact_key
  s3_object_version = var.lambda_artifact_version
  layers            = [var.common_layer_arn]

  tracing_config {
    mode = "Active"
  }

  environment {
    variables = {
      DOCUMENT_LAKE_BUCKET          = var.document_lake_bucket_name
      DOCUMENT_ML_TABLE             = aws_dynamodb_table.document_ml.name
      MLOPS_MODE                    = var.mlops_mode
      SAGEMAKER_EXECUTION_ROLE_ARN  = aws_iam_role.sagemaker.arn
      SAGEMAKER_MODEL_PACKAGE_GROUP = aws_sagemaker_model_package_group.document_classifier.model_package_group_name
      SAGEMAKER_TRAINING_IMAGE      = var.sagemaker_training_image
    }
  }

  depends_on = [aws_cloudwatch_log_group.lambda]
}

resource "aws_apigatewayv2_integration" "document_ml" {
  api_id                 = var.http_api_id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.document_ml.invoke_arn
  payload_format_version = "2.0"
  timeout_milliseconds   = 29000
}

resource "aws_apigatewayv2_route" "document_ml" {
  for_each = local.routes

  api_id             = var.http_api_id
  route_key          = each.value
  target             = "integrations/${aws_apigatewayv2_integration.document_ml.id}"
  authorization_type = "JWT"
  authorizer_id      = var.http_api_authorizer_id
}

resource "aws_lambda_permission" "http_api" {
  statement_id  = "AllowProtectedHttpApi"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.document_ml.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${var.http_api_execution_arn}/*/*"
}

resource "aws_cloudwatch_log_group" "state_machine" {
  name              = "/aws/vendedlogs/states/${local.name}"
  retention_in_days = 14
  kms_key_id        = var.kms_key_arn
}

data "aws_iam_policy_document" "states_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["states.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "states" {
  name               = "${local.name}-states"
  assume_role_policy = data.aws_iam_policy_document.states_assume.json
}

data "aws_iam_policy_document" "states" {
  statement {
    sid       = "InvokeDocumentWorker"
    effect    = "Allow"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.document_ml.arn]
  }

  statement {
    sid    = "WriteWorkflowLogs"
    effect = "Allow"
    actions = [
      "logs:CreateLogDelivery",
      "logs:DeleteLogDelivery",
      "logs:DescribeLogGroups",
      "logs:DescribeResourcePolicies",
      "logs:GetLogDelivery",
      "logs:ListLogDeliveries",
      "logs:PutResourcePolicy",
      "logs:UpdateLogDelivery",
    ]
    resources = ["*"]
  }
}

resource "aws_iam_role_policy" "states" {
  name   = "document-pipeline"
  role   = aws_iam_role.states.id
  policy = data.aws_iam_policy_document.states.json
}

resource "aws_sfn_state_machine" "document_ml" {
  name     = local.name
  role_arn = aws_iam_role.states.arn
  type     = "EXPRESS"
  definition = templatefile("${path.module}/state_machine.json.tftpl", {
    lambda_arn = aws_lambda_function.document_ml.arn
  })

  logging_configuration {
    include_execution_data = false
    level                  = "ALL"
    log_destination        = "${aws_cloudwatch_log_group.state_machine.arn}:*"
  }

  tracing_configuration {
    enabled = true
  }
}

data "aws_iam_policy_document" "events_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["events.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "events" {
  name               = "${local.name}-events"
  assume_role_policy = data.aws_iam_policy_document.events_assume.json
}

data "aws_iam_policy_document" "events" {
  statement {
    effect    = "Allow"
    actions   = ["states:StartExecution"]
    resources = [aws_sfn_state_machine.document_ml.arn]
  }
}

resource "aws_iam_role_policy" "events" {
  name   = "start-document-pipeline"
  role   = aws_iam_role.events.id
  policy = data.aws_iam_policy_document.events.json
}

resource "aws_cloudwatch_event_rule" "document_drop" {
  name        = "${local.name}-object-created"
  description = "Start the Compass document pipeline for browser drops"
  event_pattern = jsonencode({
    source        = ["aws.s3"]
    "detail-type" = ["Object Created"]
    detail = {
      bucket = { name = [var.document_lake_bucket_name] }
      object = { key = [{ prefix = "documents/incoming/" }] }
    }
  })
}

resource "aws_cloudwatch_event_target" "document_drop" {
  rule     = aws_cloudwatch_event_rule.document_drop.name
  arn      = aws_sfn_state_machine.document_ml.arn
  role_arn = aws_iam_role.events.arn
}
