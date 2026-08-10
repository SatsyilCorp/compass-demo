#!/usr/bin/env bash
# Upload frontend/out → the Compass web S3 bucket, then invalidate CloudFront.
# Reads WebBucketName + WebDistributionId from the CFN stack outputs.
# Adapted from exim-eol-poc/scripts/upload-to-cloudfront.sh.
#
# Usage: ./scripts/upload-to-cloudfront.sh [stack-name]
set -euo pipefail

STACK="${1:-compass-demo}"
REGION="${REGION:-us-east-1}"

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/.." && pwd)"

if [ ! -d "$repo/frontend/out" ]; then
  echo "ERROR: $repo/frontend/out not found — run scripts/build-frontend.sh first." >&2
  exit 1
fi

BUCKET="$(aws cloudformation describe-stacks \
  --region "$REGION" \
  --stack-name "$STACK" \
  --query 'Stacks[0].Outputs[?OutputKey==`WebBucketName`].OutputValue' \
  --output text)"
DIST="$(aws cloudformation describe-stacks \
  --region "$REGION" \
  --stack-name "$STACK" \
  --query 'Stacks[0].Outputs[?OutputKey==`WebDistributionId`].OutputValue' \
  --output text)"

if [ -z "$BUCKET" ] || [ "$BUCKET" = "None" ] || [ -z "$DIST" ] || [ "$DIST" = "None" ]; then
  echo "ERROR: could not read WebBucketName / WebDistributionId from stack $STACK" >&2
  exit 1
fi

echo "Syncing $repo/frontend/out → s3://$BUCKET/"
aws s3 sync "$repo/frontend/out/" "s3://$BUCKET/" --delete

echo "Creating CloudFront invalidation on $DIST"
aws cloudfront create-invalidation \
  --distribution-id "$DIST" \
  --paths '/*' \
  --query 'Invalidation.{Id:Id,Status:Status}' \
  --output table

DOMAIN="$(aws cloudformation describe-stacks \
  --region "$REGION" \
  --stack-name "$STACK" \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDomain`].OutputValue' \
  --output text)"
echo
echo "App URL: https://$DOMAIN/"
