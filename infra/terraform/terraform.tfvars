# Plan-only values for the golden pipeline's "Validate & Plan OpenTofu IaC"
# stage. They point at the existing compass-demo stack so `tofu plan` runs
# non-interactively (without them, plan waits forever for variable input in
# CI). Do NOT `tofu apply` this module into the CloudFormation-managed
# environment - see this directory's README.
document_lake_bucket_name = "compass-demo-raw-551185375163"
document_lake_bucket_arn  = "arn:aws:s3:::compass-demo-raw-551185375163"
kms_key_arn               = "arn:aws:kms:us-east-1:551185375163:key/7ac8d96a-2d3b-40fb-861f-2df30a678675"
http_api_id               = "v98qsota1c"
http_api_execution_arn    = "arn:aws:execute-api:us-east-1:551185375163:v98qsota1c"
# Plan-only placeholder: the live authorizer id is not readable with the
# pipeline credential, and plan does not resolve it against the API.
http_api_authorizer_id    = "planonly"
common_layer_arn          = "arn:aws:lambda:us-east-1:551185375163:layer:compass-demo-common:27"
lambda_artifact_bucket    = "compass-demo-raw-551185375163"
# Plan-only placeholder key; the artifact object is produced by CI at deploy
# time and is never fetched during plan.
lambda_artifact_key       = "mlops/document-ml/plan-only.zip"
