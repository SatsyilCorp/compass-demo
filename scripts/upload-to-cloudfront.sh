#!/usr/bin/env bash
# Upload frontend/out → the Compass web S3 bucket, then invalidate CloudFront.
# Reads WebBucketName + WebDistributionId from the CFN stack outputs.
# Adapted from exim-eol-poc/scripts/upload-to-cloudfront.sh.
#
# Usage: ./scripts/upload-to-cloudfront.sh [stack-name] [aws-profile]
set -euo pipefail

STACK="${1:-compass-demo}"
PROFILE="${2:-${AWS_PROFILE:-}}"
REGION="${REGION:-us-east-1}"
AWS_CLI=(aws)
if [ -n "$PROFILE" ]; then
  AWS_CLI+=(--profile "$PROFILE")
fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/.." && pwd)"

if [ ! -d "$repo/frontend/out" ]; then
  echo "ERROR: $repo/frontend/out not found - run scripts/build-frontend.sh first." >&2
  exit 1
fi

BUCKET="$("${AWS_CLI[@]}" cloudformation describe-stacks \
  --region "$REGION" \
  --stack-name "$STACK" \
  --query 'Stacks[0].Outputs[?OutputKey==`WebBucketName`].OutputValue' \
  --output text)"
DIST="$("${AWS_CLI[@]}" cloudformation describe-stacks \
  --region "$REGION" \
  --stack-name "$STACK" \
  --query 'Stacks[0].Outputs[?OutputKey==`WebDistributionId`].OutputValue' \
  --output text)"

if [ -z "$BUCKET" ] || [ "$BUCKET" = "None" ] || [ -z "$DIST" ] || [ "$DIST" = "None" ]; then
  echo "ERROR: could not read WebBucketName / WebDistributionId from stack $STACK" >&2
  exit 1
fi

echo "Syncing $repo/frontend/out → s3://$BUCKET/"
"${AWS_CLI[@]}" s3 sync "$repo/frontend/out/" "s3://$BUCKET/" --delete

echo "Creating CloudFront invalidation on $DIST"
INVALIDATION_ID="$("${AWS_CLI[@]}" cloudfront create-invalidation \
  --distribution-id "$DIST" \
  --paths '/*' \
  --query 'Invalidation.Id' \
  --output text)"
echo "Invalidation: $INVALIDATION_ID"

if [ "${WAIT_FOR_INVALIDATION:-true}" = "true" ]; then
  echo "Waiting for CloudFront invalidation to complete"
  "${AWS_CLI[@]}" cloudfront wait invalidation-completed \
    --distribution-id "$DIST" \
    --id "$INVALIDATION_ID"
fi

DOMAIN="$("${AWS_CLI[@]}" cloudformation describe-stacks \
  --region "$REGION" \
  --stack-name "$STACK" \
  --query 'Stacks[0].Outputs[?OutputKey==`CloudFrontDomain`].OutputValue' \
  --output text)"
echo
echo "App URL: https://$DOMAIN/"
