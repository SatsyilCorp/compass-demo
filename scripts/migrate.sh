#!/usr/bin/env bash
# Apply db/migrations against the private Aurora cluster via the in-VPC
# migrator Lambda (invoke-only — the cluster has no public endpoint).
# Idempotent: applied migrations are recorded in compass._schema_migrations
# and skipped on re-run. See docs/RUNBOOK.md §4.
#
# Usage: ./scripts/migrate.sh [stack-name]
set -euo pipefail

STACK_NAME="${1:-compass-demo}"
REGION="us-east-1"

echo "==> Resolving MigratorFunction name from stack outputs ($STACK_NAME)"
FUNCTION_NAME="$(aws cloudformation describe-stacks \
  --region "$REGION" \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs[?OutputKey==`MigratorFunctionName`].OutputValue' \
  --output text)"

if [ -z "$FUNCTION_NAME" ] || [ "$FUNCTION_NAME" = "None" ]; then
  echo "MigratorFunctionName not in stack outputs — falling back to describe-stack-resources" >&2
  FUNCTION_NAME="$(aws cloudformation describe-stack-resources \
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
trap 'rm -f "$RESPONSE_FILE"' EXIT

aws lambda invoke \
  --region "$REGION" \
  --function-name "$FUNCTION_NAME" \
  --payload '{"migrate":"all"}' \
  --cli-binary-format raw-in-base64-out \
  "$RESPONSE_FILE" \
  --query '{StatusCode:StatusCode,FunctionError:FunctionError}' \
  --output table

echo
echo "==> Response body:"
python3 -m json.tool "$RESPONSE_FILE" 2>/dev/null || cat "$RESPONSE_FILE"
echo
echo "Expect 001_schema and 002_rls listed as applied. If it reports no"
echo "migrations found, re-run ./src/functions/migrator/prepare_migrations.sh"
echo "then redeploy (docs/RUNBOOK.md §11)."
