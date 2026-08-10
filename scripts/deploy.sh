#!/usr/bin/env bash
# Build + deploy the Compass stack.
#
# Usage: ./scripts/deploy.sh [config-env]
#   config-env defaults to "default" (samconfig.toml [default] section).
#   Pass "dev" to deploy the isolated compass-demo-dev stack instead
#   (see samconfig.toml.template).
#
# NOTE: sam build MUST use --use-container on macOS — the CommonLayer
# pip-installs psycopg2-binary and the demo also needs numpy for analytics;
# a macOS-native build produces darwin wheels inside a linux/arm64 layer,
# which breaks the Lambda import at runtime (see docs/BUILD_REPORT.md /
# docs/RUNBOOK.md §11 troubleshooting).
set -euo pipefail

CONFIG_ENV="${1:-default}"
STACK_NAME="compass-demo"
REGION="us-east-1"

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/.." && pwd)"
cd "$repo"

if [ ! -f samconfig.toml ]; then
  echo "ERROR: samconfig.toml not found. cp samconfig.toml.template samconfig.toml first (docs/RUNBOOK.md §1)." >&2
  exit 1
fi

if [ "$CONFIG_ENV" = "dev" ]; then
  STACK_NAME="compass-demo-dev"
fi

echo "==> Staging db/migrations into the migrator package"
"$repo/src/functions/migrator/prepare_migrations.sh"

echo "==> sam build --use-container (config-env: $CONFIG_ENV)"
sam build --use-container

echo "==> sam deploy --config-env $CONFIG_ENV --no-confirm-changeset --resolve-s3"
sam deploy \
  --config-env "$CONFIG_ENV" \
  --no-confirm-changeset \
  --resolve-s3

echo
echo "==> Stack outputs ($STACK_NAME, $REGION):"
aws cloudformation describe-stacks \
  --region "$REGION" \
  --stack-name "$STACK_NAME" \
  --query 'Stacks[0].Outputs' \
  --output table
