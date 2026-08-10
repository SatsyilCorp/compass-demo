#!/usr/bin/env bash
# Regenerate seed/ (stdlib-only generator) and drop seed/drops/*.json into the
# raw S3 bucket to trigger the real intake pipeline (S3 -> EventBridge ->
# Express state machine -> quality gate -> curated table). See
# docs/RUNBOOK.md §5.
#
# WARNING (recording-day tripwire, per docs/RUNBOOK.md §5 and §8): do NOT run
# this against the stack you intend to record on before recording — the
# drops are ingested live on camera during Element 3 of docs/DEMO_SCRIPT.md.
# Fine to run any time against a dev/rehearsal stack (--config-env dev).
#
# Usage: ./scripts/seed.sh [stack-name]
set -euo pipefail

STACK="${1:-compass-demo}"
REGION="${REGION:-us-east-1}"

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/.." && pwd)"

if [ -f "$here/seed_data.py" ]; then
  echo "==> Regenerating seed/ via scripts/seed_data.py"
  python3 "$here/seed_data.py"
else
  echo "==> scripts/seed_data.py not present — using seed/ as committed"
fi

echo "==> Resolving raw bucket name from stack outputs ($STACK)"
RAW_BUCKET="$(aws cloudformation describe-stacks \
  --region "$REGION" \
  --stack-name "$STACK" \
  --query 'Stacks[0].Outputs[?OutputKey==`RawBucketName`].OutputValue' \
  --output text)"

if [ -z "$RAW_BUCKET" ] || [ "$RAW_BUCKET" = "None" ]; then
  echo "RawBucketName not in stack outputs — falling back to describe-stack-resources (logical id: RawBucket)" >&2
  RAW_BUCKET="$(aws cloudformation describe-stack-resources \
    --region "$REGION" \
    --stack-name "$STACK" \
    --logical-resource-id RawBucket \
    --query 'StackResources[0].PhysicalResourceId' \
    --output text)"
fi

if [ -z "$RAW_BUCKET" ] || [ "$RAW_BUCKET" = "None" ]; then
  echo "ERROR: could not resolve the raw bucket for stack $STACK" >&2
  exit 1
fi

DROPS_DIR="$repo/seed/drops"
if [ ! -d "$DROPS_DIR" ] || [ -z "$(ls -A "$DROPS_DIR"/*.json 2>/dev/null)" ]; then
  echo "ERROR: no *.json files under $DROPS_DIR" >&2
  exit 1
fi

echo "==> Dropping seed/drops/*.json into s3://$RAW_BUCKET/drops/"
for f in "$DROPS_DIR"/*.json; do
  name="$(basename "$f")"
  echo "  -> drops/$name"
  aws s3 cp "$f" "s3://$RAW_BUCKET/drops/$name" --region "$REGION" >/dev/null
done

echo
echo "Dropped:"
for f in "$DROPS_DIR"/*.json; do
  echo "  $(basename "$f")"
done
echo
echo "EventBridge -> the intake state machine should fire automatically for each object."
echo "Check progress: GET /ingest/status, or"
echo "  aws stepfunctions list-executions --region $REGION --state-machine-arn <IntakeStateMachineArn>"
