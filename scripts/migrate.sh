#!/usr/bin/env bash
# Apply db/migrations against the private Aurora cluster via the in-VPC
# migrator Lambda (invoke-only; the cluster has no public endpoint).
# Idempotent: applied migrations are recorded in compass._schema_migrations
# and skipped on re-run. See docs/RUNBOOK.md §4.
#
# Usage: ./scripts/migrate.sh [stack-name] [aws-profile]
set -euo pipefail

STACK_NAME="${1:-compass-demo}"
PROFILE="${2:-${AWS_PROFILE:-}}"
REGION="us-east-1"
AWS_CLI=(aws)
if [ -n "$PROFILE" ]; then
  AWS_CLI+=(--profile "$PROFILE")
fi

echo "==> Resolving MigratorFunction name from stack outputs ($STACK_NAME)"
FUNCTION_NAME="$("${AWS_CLI[@]}" cloudformation describe-stacks \
  --region "$REGION" \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`MigratorFunctionName`].OutputValue' \
  --output text)"

if [ -z "$FUNCTION_NAME" ] || [ "$FUNCTION_NAME" = "None" ]; then
  echo "MigratorFunctionName not in stack outputs; falling back to describe-stack-resources" >&2
  FUNCTION_NAME="$("${AWS_CLI[@]}" cloudformation describe-stack-resources \
    --region "$REGION" \
    --stack-name "$STACK_NAME" \
    --logical-resource-id MigratorFunction \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text)"
fi

if [ -z "$FUNCTION_NAME" ] || [ "$FUNCTION_NAME" = "None" ]; then
  echo "ERROR: could not resolve MigratorFunction for stack $STACK_NAME" >&2
  exit 1
fi

echo "==> Invoking $FUNCTION_NAME with {\"migrate\":\"all\"}"
RESPONSE_FILE="$(mktemp)"
INVOKE_META_FILE="$(mktemp)"
trap 'rm -f "$RESPONSE_FILE" "$INVOKE_META_FILE"' EXIT

"${AWS_CLI[@]}" lambda invoke \
  --region "$REGION" \
  --function-name "$FUNCTION_NAME" \
  --payload '{"migrate":"all"}' \
  --cli-binary-format raw-in-base64-out \
  "$RESPONSE_FILE" \
  --query '{StatusCode:StatusCode,FunctionError:FunctionError}' \
  --output json > "$INVOKE_META_FILE"

python3 -c 'import json,sys; meta=json.load(open(sys.argv[1])); data=json.load(open(sys.argv[2])); assert meta.get("StatusCode")==200 and not meta.get("FunctionError"), meta; assert data.get("status")=="ok", data; assert data.get("role_bootstrap", {}).get("status")=="granted", data' "$INVOKE_META_FILE" "$RESPONSE_FILE"

echo
echo "==> Response body:"
python3 -m json.tool "$RESPONSE_FILE" 2>/dev/null || cat "$RESPONSE_FILE"
echo
echo "Verified status=ok and role_bootstrap=granted."
echo "Expect 001_schema, 002_rls, 003_security_hardening, and 004_opaque_approval_capability"
echo "listed as applied or skipped. If it reports no"
echo "migrations found, re-run ./src/functions/migrator/prepare_migrations.sh"
echo "then redeploy (docs/RUNBOOK.md §11)."
