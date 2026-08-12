#!/usr/bin/env bash
# Build and deploy a fresh production-scale Compass stack through the named
# Satsyil AWS profile. The script never reads the repository's default SAM
# config, so callback URLs from another account cannot cross into this stack.
set -euo pipefail

readonly REQUIRED_AWS_PROFILE="satsyil"
if [ -n "${AWS_PROFILE:-}" ] && [ "$AWS_PROFILE" != "$REQUIRED_AWS_PROFILE" ]; then
  echo "ERROR: this deployment entrypoint requires AWS_PROFILE=satsyil" >&2
  exit 1
fi
export AWS_PROFILE="$REQUIRED_AWS_PROFILE"
export AWS_DEFAULT_PROFILE="$REQUIRED_AWS_PROFILE"
export AWS_REGION="${AWS_REGION:-us-east-1}"
export AWS_DEFAULT_REGION="$AWS_REGION"

# A named profile does not override ambient credential providers by itself.
# Scrub them, then pass the profile explicitly to every AWS and SAM command.
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_SECURITY_TOKEN
unset AWS_ROLE_ARN AWS_ROLE_SESSION_NAME AWS_WEB_IDENTITY_TOKEN_FILE
unset AWS_CONTAINER_CREDENTIALS_FULL_URI AWS_CONTAINER_CREDENTIALS_RELATIVE_URI

SATSYIL_EXPECTED_ACCOUNT_ID="${SATSYIL_EXPECTED_ACCOUNT_ID:-}"

STACK_NAME="${STACK_NAME:-compass-demo}"
DATABASE_MODE="${DATABASE_MODE:-ha}"
SCALE_MAX_RECORDS="${SCALE_MAX_RECORDS:-1000000}"
SCALE_MAX_CONCURRENCY="${SCALE_MAX_CONCURRENCY:-4}"
SCALE_EXPORT_CONCURRENCY="${SCALE_EXPORT_CONCURRENCY:-2}"
SCALE_MAX_COST_USD="${SCALE_MAX_COST_USD:-10}"
SCALE_DATA_RETENTION_DAYS="${SCALE_DATA_RETENTION_DAYS:-7}"
SCALE_EVIDENCE_RETENTION_DAYS="${SCALE_EVIDENCE_RETENTION_DAYS:-30}"
SCALE_ATHENA_SCAN_CUTOFF_BYTES="${SCALE_ATHENA_SCAN_CUTOFF_BYTES:-10737418240}"
COGNITO_DOMAIN_PREFIX="${COGNITO_DOMAIN_PREFIX:-satsyil-compass-demo}"
PUBLIC_SBIR_EXECUTION_ENABLED="${PUBLIC_SBIR_EXECUTION_ENABLED:-false}"
WEB_CUSTOM_DOMAIN_NAME="${WEB_CUSTOM_DOMAIN_NAME:-}"
WEB_CERTIFICATE_ARN="${WEB_CERTIFICATE_ARN:-}"
WEB_HOSTED_ZONE_ID="${WEB_HOSTED_ZONE_ID:-}"
EXISTING_PUBLIC_FUNDING_MODEL_PACKAGE_GROUP_ARN="${EXISTING_PUBLIC_FUNDING_MODEL_PACKAGE_GROUP_ARN:-}"

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/.." && pwd)"
config="$repo/samconfig-satsyil.toml"
cd "$repo"

require_clean_source_tree() {
  local dirty_paths
  dirty_paths="$(git status --porcelain=v1 --untracked-files=all)"
  if [ -n "$dirty_paths" ]; then
    echo "ERROR: deployment requires a clean Git source tree; commit or remove every listed change" >&2
    printf '%s\n' "$dirty_paths" >&2
    exit 1
  fi
}

source_revision="$(git rev-parse --verify HEAD)"
if ! [[ "$source_revision" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: unable to resolve the exact 40-character Git commit SHA" >&2
  exit 1
fi
if [ -n "${DEPLOY_REVISION:-}" ] && [ "$DEPLOY_REVISION" != "$source_revision" ]; then
  echo "ERROR: DEPLOY_REVISION must exactly equal the full Git commit SHA at HEAD" >&2
  exit 1
fi
DEPLOY_REVISION="$source_revision"
unset source_revision
require_clean_source_tree

if ! [[ "$SATSYIL_EXPECTED_ACCOUNT_ID" =~ ^[0-9]{12}$ ]]; then
  echo "ERROR: SATSYIL_EXPECTED_ACCOUNT_ID must be supplied as a 12-digit protected environment value" >&2
  exit 1
fi
if [ "$AWS_REGION" != "us-east-1" ]; then
  echo "ERROR: Compass CloudFront WAF resources require us-east-1" >&2
  exit 1
fi
if [ "$DATABASE_MODE" != "demo" ] && [ "$DATABASE_MODE" != "ha" ]; then
  echo "ERROR: DATABASE_MODE must be demo or ha" >&2
  exit 1
fi
if [ "$PUBLIC_SBIR_EXECUTION_ENABLED" != "true" ] \
    && [ "$PUBLIC_SBIR_EXECUTION_ENABLED" != "false" ]; then
  echo "ERROR: PUBLIC_SBIR_EXECUTION_ENABLED must be true or false" >&2
  exit 1
fi
if ! [[ "$COGNITO_DOMAIN_PREFIX" =~ ^[a-z0-9][a-z0-9-]{0,61}[a-z0-9]$ ]]; then
  echo "ERROR: COGNITO_DOMAIN_PREFIX must be a 2 to 63 character lowercase prefix" >&2
  exit 1
fi
custom_domain_values=0
[ -n "$WEB_CUSTOM_DOMAIN_NAME" ] && custom_domain_values=$((custom_domain_values + 1))
[ -n "$WEB_CERTIFICATE_ARN" ] && custom_domain_values=$((custom_domain_values + 1))
[ -n "$WEB_HOSTED_ZONE_ID" ] && custom_domain_values=$((custom_domain_values + 1))
if [ "$custom_domain_values" -ne 0 ] && [ "$custom_domain_values" -ne 3 ]; then
  echo "ERROR: custom domain name, certificate ARN, and hosted zone ID must be supplied together" >&2
  exit 1
fi
if [ -n "$WEB_CUSTOM_DOMAIN_NAME" ] \
    && ! [[ "$WEB_CUSTOM_DOMAIN_NAME" =~ ^[a-z0-9][a-z0-9.-]*[a-z0-9]$ ]]; then
  echo "ERROR: WEB_CUSTOM_DOMAIN_NAME has an invalid format" >&2
  exit 1
fi
unset custom_domain_values
if [ ! -f "$config" ]; then
  echo "ERROR: missing $config" >&2
  exit 1
fi

aws_satsyil() {
  aws --profile "$REQUIRED_AWS_PROFILE" --region "$AWS_REGION" "$@"
}

echo "==> Verifying the named Satsyil AWS session and expected account"
caller_account="$(aws_satsyil sts get-caller-identity --query 'Account' --output text)"
if [ "$caller_account" != "$SATSYIL_EXPECTED_ACCOUNT_ID" ]; then
  echo "ERROR: the satsyil profile resolved to an unexpected AWS account; refusing deployment" >&2
  exit 1
fi
SATSYIL_ACCOUNT_ID="$caller_account"
unset caller_account SATSYIL_EXPECTED_ACCOUNT_ID

stack_exists=false
stack_probe=""
if stack_probe="$(aws_satsyil cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].StackStatus' \
    --output text 2>&1)"; then
  stack_exists=true
  case "$stack_probe" in
    CREATE_COMPLETE|UPDATE_COMPLETE|UPDATE_ROLLBACK_COMPLETE)
      ;;
    ROLLBACK_COMPLETE)
      echo "ERROR: stack creation previously rolled back; inspect events and remove the failed stack before retrying" >&2
      exit 1
      ;;
    *)
      echo "ERROR: existing stack is not in an updateable state: $stack_probe" >&2
      exit 1
      ;;
  esac
elif [[ "$stack_probe" == *"(ValidationError)"* && "$stack_probe" == *"does not exist"* ]]; then
  stack_exists=false
else
  echo "ERROR: unable to determine whether the target stack exists; refusing deployment" >&2
  exit 1
fi
unset stack_probe

if [ "$stack_exists" = true ] \
    && [ -z "$EXISTING_PUBLIC_FUNDING_MODEL_PACKAGE_GROUP_ARN" ]; then
  existing_public_group_parameter="$(aws_satsyil cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Parameters[?ParameterKey==`ExistingPublicFundingModelPackageGroupArn`].ParameterValue | [0]' \
    --output text)"
  if [ "$existing_public_group_parameter" != "None" ]; then
    EXISTING_PUBLIC_FUNDING_MODEL_PACKAGE_GROUP_ARN="$existing_public_group_parameter"
  fi
  unset existing_public_group_parameter
fi

if [ -n "$EXISTING_PUBLIC_FUNDING_MODEL_PACKAGE_GROUP_ARN" ]; then
  expected_public_group_prefix="arn:aws:sagemaker:$AWS_REGION:$SATSYIL_ACCOUNT_ID:model-package-group/"
  case "$EXISTING_PUBLIC_FUNDING_MODEL_PACKAGE_GROUP_ARN" in
    "$expected_public_group_prefix"*)
      ;;
    *)
      echo "ERROR: external public-funding Model Package Group must be in the target Satsyil account and region" >&2
      exit 1
      ;;
  esac
  public_group_name="${EXISTING_PUBLIC_FUNDING_MODEL_PACKAGE_GROUP_ARN##*/}"
  resolved_public_group_arn="$(aws_satsyil sagemaker describe-model-package-group \
    --model-package-group-name "$public_group_name" \
    --query ModelPackageGroupArn \
    --output text)"
  if [ "$resolved_public_group_arn" != "$EXISTING_PUBLIC_FUNDING_MODEL_PACKAGE_GROUP_ARN" ]; then
    echo "ERROR: external public-funding Model Package Group ARN did not resolve exactly" >&2
    exit 1
  fi
  unset expected_public_group_prefix public_group_name resolved_public_group_arn
fi
unset SATSYIL_ACCOUNT_ID

if [ "$PUBLIC_SBIR_EXECUTION_ENABLED" = "true" ]; then
  if [ "$stack_exists" != "true" ]; then
    echo "ERROR: public SBIR execution can be enabled only after its pinned evidence is provisioned" >&2
    exit 1
  fi
  public_sbir_bucket="$(aws_satsyil cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`RawBucketName`].OutputValue | [0]' \
    --output text)"
  public_sbir_package="$(aws_satsyil sagemaker describe-model-package \
    --model-package-name "${STACK_NAME}-public-sbir-transition/2" \
    --query '[ModelPackageStatus,ModelApprovalStatus] | join(`:`, @)' \
    --output text)"
  if [ "$public_sbir_package" != "Completed:PendingManualApproval" ]; then
    echo "ERROR: pinned public SBIR Model Registry package is not ready" >&2
    exit 1
  fi
  public_sbir_training="$(aws_satsyil sagemaker describe-training-job \
    --training-job-name compass-doc-sbir-transition-20260812-0134 \
    --query TrainingJobStatus \
    --output text)"
  if [ "$public_sbir_training" != "Completed" ]; then
    echo "ERROR: pinned public SBIR training job is not complete" >&2
    exit 1
  fi
  public_sbir_version="$(aws_satsyil s3api head-object \
    --bucket "$public_sbir_bucket" \
    --key mlops/public-sbir-transition/registry/sbir_transition-0dda670313a1e9d3/model-v2.tar.gz \
    --version-id 6ki61OUXqpqujj5uHes3k0Sz2AoryxlB \
    --query VersionId \
    --output text)"
  if [ "$public_sbir_version" != "6ki61OUXqpqujj5uHes3k0Sz2AoryxlB" ]; then
    echo "ERROR: pinned public SBIR model object version did not resolve exactly" >&2
    exit 1
  fi
  aws_satsyil s3api head-object \
    --bucket "$public_sbir_bucket" \
    --key mlops/public-sbir-transition/validation/candidates-20260812.json \
    >/dev/null
  unset public_sbir_bucket public_sbir_package public_sbir_training public_sbir_version
fi

if [ "$stack_exists" = false ]; then
  vpc_count="$(aws_satsyil ec2 describe-vpcs --query 'length(Vpcs)' --output text)"
  vpc_quota="$(aws_satsyil service-quotas get-service-quota \
    --service-code vpc \
    --quota-code L-F678F1CE \
    --query 'Quota.Value' \
    --output text)"
  eip_count="$(aws_satsyil ec2 describe-addresses --query 'length(Addresses)' --output text)"
  eip_quota="$(aws_satsyil service-quotas get-service-quota \
    --service-code ec2 \
    --quota-code L-0263D0A3 \
    --query 'Quota.Value' \
    --output text)"
  if ! awk "BEGIN { exit !($vpc_count < $vpc_quota) }"; then
    echo "ERROR: regional VPC quota has no free slot; wait for the submitted quota request" >&2
    exit 1
  fi
  if ! awk "BEGIN { exit !($eip_count < $eip_quota) }"; then
    echo "ERROR: regional Elastic IP quota has no free slot; wait for the submitted quota request" >&2
    exit 1
  fi
fi

echo "==> Verifying the Linux container build runtime"
docker info >/dev/null

echo "==> Staging database migrations"
"$repo/src/functions/migrator/prepare_migrations.sh"

echo "==> Staging the current SAM template into the RMF artifact package"
"$repo/src/functions/rmf_artifact/prepare_template.sh"

echo "==> Confirming staged deployment artifacts match the committed source"
require_clean_source_tree

echo "==> Validating the SAM template"
sam validate \
  --lint \
  --region "$AWS_REGION" \
  --profile "$REQUIRED_AWS_PROFILE" \
  --config-file "$config" \
  --config-env satsyil

echo "==> Building Linux ARM Lambda packages"
sam build \
  --use-container \
  --region "$AWS_REGION" \
  --profile "$REQUIRED_AWS_PROFILE" \
  --config-file "$config" \
  --config-env satsyil

deploy_pass() {
  local identity_domain="${1:-}"
  local database_mode="${2:-$DATABASE_MODE}"
  local cors_origin_domain="${3:-$identity_domain}"
  local web_parameters=(
    "DeployRevision=$DEPLOY_REVISION"
  )
  if [ -n "$EXISTING_PUBLIC_FUNDING_MODEL_PACKAGE_GROUP_ARN" ]; then
    web_parameters+=(
      "ExistingPublicFundingModelPackageGroupArn=$EXISTING_PUBLIC_FUNDING_MODEL_PACKAGE_GROUP_ARN"
    )
  fi
  if [ -n "$WEB_CUSTOM_DOMAIN_NAME" ]; then
    web_parameters+=(
      "WebCustomDomainName=$WEB_CUSTOM_DOMAIN_NAME"
      "WebCertificateArn=$WEB_CERTIFICATE_ARN"
      "WebHostedZoneId=$WEB_HOSTED_ZONE_ID"
    )
  fi
  if [ -n "$identity_domain" ]; then
    web_parameters+=(
      "WebCallbackUrl=https://$identity_domain/login/"
      "WebLogoutUrl=https://$identity_domain/login/"
      "WebOrigin=https://$cors_origin_domain"
    )
  fi

  sam deploy \
    --config-file "$config" \
    --config-env satsyil \
    --template-file "$repo/.aws-sam/build/template.yaml" \
    --stack-name "$STACK_NAME" \
    --region "$AWS_REGION" \
    --profile "$REQUIRED_AWS_PROFILE" \
    --resolve-s3 \
    --capabilities CAPABILITY_IAM CAPABILITY_NAMED_IAM \
    --no-confirm-changeset \
    --no-fail-on-empty-changeset \
    --parameter-overrides \
      "DatabaseResilienceMode=$database_mode" \
      "ExportMaxRows=5000" \
      "WafRateLimit=2000" \
      "StreamTickerState=ENABLED" \
      "DeploySecurityBaseline=false" \
      "ScaleFeatureEnabled=true" \
      "ScaleMaxRecords=$SCALE_MAX_RECORDS" \
      "ScaleMaxConcurrency=$SCALE_MAX_CONCURRENCY" \
      "ScaleExportConcurrency=$SCALE_EXPORT_CONCURRENCY" \
      "ScaleMaxEstimatedCostUsd=$SCALE_MAX_COST_USD" \
      "ScaleDataRetentionDays=$SCALE_DATA_RETENTION_DAYS" \
      "ScaleEvidenceRetentionDays=$SCALE_EVIDENCE_RETENTION_DAYS" \
      "ScaleAthenaBytesScannedCutoff=$SCALE_ATHENA_SCAN_CUTOFF_BYTES" \
      "PublicSbirExecutionEnabled=$PUBLIC_SBIR_EXECUTION_ENABLED" \
      "CognitoDomainPrefix=$COGNITO_DOMAIN_PREFIX" \
      "${web_parameters[@]}"
}

if [ "$stack_exists" = true ]; then
  cloudfront_domain="$(aws_satsyil cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDomain`].OutputValue | [0]' \
    --output text)"
  if [ -z "$cloudfront_domain" ] || [ "$cloudfront_domain" = "None" ]; then
    echo "ERROR: existing stack did not return CloudFrontDomain" >&2
    exit 1
  fi
  echo "==> Updating the existing stack with its exact web identity bindings"
  identity_domain="$cloudfront_domain"
  if [ -n "$WEB_CUSTOM_DOMAIN_NAME" ]; then
    identity_domain="$WEB_CUSTOM_DOMAIN_NAME"
  fi
  deploy_pass "$identity_domain" "$DATABASE_MODE" "$cloudfront_domain"
  unset identity_domain
else
  echo "==> First deployment pass with recoverable database bootstrap"
  deploy_pass "" demo

  cloudfront_domain="$(aws_satsyil cloudformation describe-stacks \
    --stack-name "$STACK_NAME" \
    --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDomain`].OutputValue | [0]' \
    --output text)"
  if [ -z "$cloudfront_domain" ] || [ "$cloudfront_domain" = "None" ]; then
    echo "ERROR: first deployment did not return CloudFrontDomain" >&2
    exit 1
  fi

  echo "==> Second deployment pass with exact web identity bindings"
  identity_domain="$cloudfront_domain"
  if [ -n "$WEB_CUSTOM_DOMAIN_NAME" ]; then
    identity_domain="$WEB_CUSTOM_DOMAIN_NAME"
  fi
  deploy_pass "$identity_domain" "$DATABASE_MODE" "$cloudfront_domain"
  unset identity_domain
fi

echo "==> Applying database migrations"
"$repo/scripts/migrate.sh" "$STACK_NAME" "$REQUIRED_AWS_PROFILE"

echo "==> Building the authenticated live frontend"
"$repo/scripts/build-frontend.sh" "$STACK_NAME" "$REQUIRED_AWS_PROFILE"

echo "==> Publishing the frontend and waiting for edge invalidation"
WAIT_FOR_INVALIDATION=true "$repo/scripts/upload-to-cloudfront.sh" "$STACK_NAME" "$REQUIRED_AWS_PROFILE"

echo
echo "Compass URL: https://$cloudfront_domain/"
if [ -n "$WEB_CUSTOM_DOMAIN_NAME" ]; then
  echo "Custom URL: https://$WEB_CUSTOM_DOMAIN_NAME/"
fi
echo "Scale Lab: https://$cloudfront_domain/admin/scale/"
