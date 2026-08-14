#!/usr/bin/env bash
# Build the Next.js static export against a deployed Compass stack.
#
# Reads ApiBaseUrl, CognitoDomain, UserPoolId, WebClientId, CloudFrontDomain,
# and the optional CustomDomainUrl
# from the CFN stack outputs and exports them as the NEXT_PUBLIC_* vars read
# by frontend/lib/api.ts and frontend/lib/auth/{providers.tsx,use-app-auth.ts}
# (see frontend/.env.example / docs/RUNBOOK.md §7). The deployed product keeps
# authentication enabled and uses live public evidence as its fail-closed
# runtime default.
#
# Usage: ./scripts/build-frontend.sh [stack-name] [aws-profile]
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

outputs() {
  "${AWS_CLI[@]}" cloudformation describe-stacks \
    --region "$REGION" \
    --stack-name "$STACK" \
    --query "Stacks[0].Outputs[?OutputKey==\`$1\`].OutputValue" \
    --output text
}

parameter() {
  "${AWS_CLI[@]}" cloudformation describe-stacks \
    --region "$REGION" \
    --stack-name "$STACK" \
    --query "Stacks[0].Parameters[?ParameterKey==\`$1\`].ParameterValue | [0]" \
    --output text
}

echo "==> Resolving stack outputs from $STACK"
API_BASE_URL="$(outputs ApiBaseUrl)"
COGNITO_DOMAIN_HOST="$(outputs CognitoDomain)"
USER_POOL_ID="$(outputs UserPoolId)"
WEB_CLIENT_ID="$(outputs WebClientId)"
CLOUDFRONT_DOMAIN="$(outputs CloudFrontDomain)"
CUSTOM_DOMAIN_URL="$(outputs CustomDomainUrl)"
SOURCE_REVISION="$(parameter DeployRevision)"
if [ -n "${WEB_CUSTOM_DOMAIN_NAME:-}" ]; then
  PUBLIC_WEB_ORIGIN="https://${WEB_CUSTOM_DOMAIN_NAME}"
elif [ -n "$CUSTOM_DOMAIN_URL" ] && [ "$CUSTOM_DOMAIN_URL" != "None" ]; then
  case "$CUSTOM_DOMAIN_URL" in
    https://*) PUBLIC_WEB_ORIGIN="${CUSTOM_DOMAIN_URL%/}" ;;
    *)
      echo "ERROR: stack output CustomDomainUrl must use HTTPS" >&2
      exit 1
      ;;
  esac
else
  PUBLIC_WEB_ORIGIN="https://${CLOUDFRONT_DOMAIN}"
fi

for name_val in "ApiBaseUrl:$API_BASE_URL" "CognitoDomain:$COGNITO_DOMAIN_HOST" \
    "UserPoolId:$USER_POOL_ID" "WebClientId:$WEB_CLIENT_ID" "CloudFrontDomain:$CLOUDFRONT_DOMAIN"; do
  key="${name_val%%:*}"
  val="${name_val#*:}"
  if [ -z "$val" ] || [ "$val" = "None" ]; then
    echo "ERROR: stack output $key not found on $STACK" >&2
    exit 1
  fi
done

if ! [[ "$SOURCE_REVISION" =~ ^[0-9a-f]{40}$ ]]; then
  echo "ERROR: stack parameter DeployRevision is not an exact lowercase commit SHA" >&2
  exit 1
fi

QUALITY_STATUS="unverified"
QUALITY_RUN_URL=""
QUALITY_REPOSITORY="${QUALITY_REPOSITORY:-SatsyilCorp/compass-demo}"
if command -v gh >/dev/null 2>&1; then
  if quality_runs="$(gh run list \
      --repo "$QUALITY_REPOSITORY" \
      --workflow quality.yml \
      --commit "$SOURCE_REVISION" \
      --limit 20 \
      --json headSha,status,conclusion,url 2>/dev/null)"; then
    quality_receipt="$(QUALITY_RUNS_JSON="$quality_runs" SOURCE_REVISION="$SOURCE_REVISION" python3 - <<'PY'
import json
import os

runs = json.loads(os.environ["QUALITY_RUNS_JSON"])
revision = os.environ["SOURCE_REVISION"]
match = next((run for run in runs if run.get("headSha") == revision), None)
if not match:
    print("unverified\t")
elif match.get("status") == "completed":
    print(f"{match.get('conclusion') or 'unverified'}\t{match.get('url') or ''}")
else:
    print(f"pending\t{match.get('url') or ''}")
PY
)"
    IFS=$'\t' read -r QUALITY_STATUS QUALITY_RUN_URL <<< "$quality_receipt"
  fi
fi

export NEXT_PUBLIC_AUTH_DISABLED=false
export NEXT_PUBLIC_API_BASE_URL="$API_BASE_URL"
export NEXT_PUBLIC_COGNITO_AUTHORITY="https://cognito-idp.${REGION}.amazonaws.com/${USER_POOL_ID}"
export NEXT_PUBLIC_COGNITO_DOMAIN="https://${COGNITO_DOMAIN_HOST}"
export NEXT_PUBLIC_COGNITO_CLIENT_ID="$WEB_CLIENT_ID"
export NEXT_PUBLIC_COGNITO_REDIRECT_URI="${PUBLIC_WEB_ORIGIN}/login/"
export NEXT_PUBLIC_COGNITO_POST_LOGOUT_REDIRECT_URI="${PUBLIC_WEB_ORIGIN}/login/"
export NEXT_PUBLIC_SOURCE_REVISION="$SOURCE_REVISION"
export NEXT_PUBLIC_QUALITY_STATUS="$QUALITY_STATUS"
export NEXT_PUBLIC_QUALITY_RUN_URL="$QUALITY_RUN_URL"

echo "==> Frontend env:"
echo "  NEXT_PUBLIC_AUTH_DISABLED=$NEXT_PUBLIC_AUTH_DISABLED"
echo "  NEXT_PUBLIC_API_BASE_URL=$NEXT_PUBLIC_API_BASE_URL"
echo "  NEXT_PUBLIC_COGNITO_AUTHORITY=$NEXT_PUBLIC_COGNITO_AUTHORITY"
echo "  NEXT_PUBLIC_COGNITO_DOMAIN=$NEXT_PUBLIC_COGNITO_DOMAIN"
echo "  NEXT_PUBLIC_COGNITO_CLIENT_ID=$NEXT_PUBLIC_COGNITO_CLIENT_ID"
echo "  NEXT_PUBLIC_COGNITO_REDIRECT_URI=$NEXT_PUBLIC_COGNITO_REDIRECT_URI"
echo "  NEXT_PUBLIC_COGNITO_POST_LOGOUT_REDIRECT_URI=$NEXT_PUBLIC_COGNITO_POST_LOGOUT_REDIRECT_URI"
echo "  NEXT_PUBLIC_SOURCE_REVISION=$NEXT_PUBLIC_SOURCE_REVISION"
echo "  NEXT_PUBLIC_QUALITY_STATUS=$NEXT_PUBLIC_QUALITY_STATUS"
echo "  NEXT_PUBLIC_QUALITY_RUN_URL=$NEXT_PUBLIC_QUALITY_RUN_URL"

cd "$repo/frontend"
readonly PNPM_VERSION="10.33.2"
PNPM=(corepack "pnpm@$PNPM_VERSION")
echo "==> pnpm $PNPM_VERSION install --frozen-lockfile"
"${PNPM[@]}" install --frozen-lockfile
echo "==> pnpm $PNPM_VERSION build"
"${PNPM[@]}" build

echo
echo "Static export written to $repo/frontend/out/ - publish with scripts/upload-to-cloudfront.sh"
