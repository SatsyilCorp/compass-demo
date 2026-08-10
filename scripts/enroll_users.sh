#!/usr/bin/env bash
# ============================================================================
# OPERATOR-ONLY. Creates the two Compass demo personas in Cognito.
#
#   poweruser@compass.demo  -> group compass-poweruser (org_unit ONR-Corporate)
#   viewer@compass.demo     -> group compass-viewer    (org_unit Code-30)
#
# This script sets a PERMANENT password for each user via
# admin-set-user-password. It does NOT and CANNOT enroll TOTP MFA — the user
# pool has MfaConfiguration=ON / SOFTWARE_TOKEN_MFA, and TOTP secret
# generation (associate-software-token) must happen inside an authenticated
# session (a real sign-in, or an authenticated InitiateAuth/RespondToAuth
# flow) so the QR code / secret can be shown to and scanned by a HUMAN. A
# script cannot scan a QR code. Read the printed instructions at the end of
# this script and complete that step yourself, well before recording day
# (docs/RUNBOOK.md §6).
#
# Idempotent: admin-create-user's UsernameExistsException is ignored, so this
# is safe to re-run (e.g. to reset a forgotten permanent password).
#
# Usage: ./scripts/enroll_users.sh [stack-name] [password]
#   password defaults to a generated 20-char value printed once below if
#   not supplied — the pool requires 16+ chars, upper+lower+number+symbol.
# ============================================================================
set -euo pipefail

STACK="${1:-compass-demo}"
REGION="${REGION:-us-east-1}"
PASSWORD="${2:-}"

if [ -z "$PASSWORD" ]; then
  PASSWORD="Cmp$(date +%s)!Aa9$(head -c6 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c6)Zz"
  echo "No password supplied — generated one (16+ chars, upper/lower/number/symbol)."
fi

echo "==> Resolving UserPoolId from stack outputs ($STACK)"
POOL_ID="$(aws cloudformation describe-stacks \
  --region "$REGION" \
  --stack-name "$STACK" \
  --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' \
  --output text)"

if [ -z "$POOL_ID" ] || [ "$POOL_ID" = "None" ]; then
  echo "ERROR: could not read UserPoolId from stack $STACK" >&2
  exit 1
fi
echo "    UserPoolId: $POOL_ID"

create_user() {
  local email="$1" group="$2"
  echo "==> $email -> $group"

  if aws cognito-idp admin-create-user \
      --region "$REGION" \
      --user-pool-id "$POOL_ID" \
      --username "$email" \
      --user-attributes Name=email,Value="$email" Name=email_verified,Value=true \
      --message-action SUPPRESS >/dev/null 2>&1; then
    echo "    created"
  else
    # Idempotent: ignore "already exists", surface anything else.
    if aws cognito-idp admin-get-user --region "$REGION" --user-pool-id "$POOL_ID" \
        --username "$email" >/dev/null 2>&1; then
      echo "    already exists — continuing (idempotent)"
    else
      echo "ERROR: admin-create-user failed for $email and the user does not appear to exist" >&2
      return 1
    fi
  fi

  aws cognito-idp admin-set-user-password \
    --region "$REGION" \
    --user-pool-id "$POOL_ID" \
    --username "$email" \
    --password "$PASSWORD" \
    --permanent
  echo "    permanent password set"

  aws cognito-idp admin-add-user-to-group \
    --region "$REGION" \
    --user-pool-id "$POOL_ID" \
    --username "$email" \
    --group-name "$group"
  echo "    added to $group"
}

create_user "poweruser@compass.demo" "compass-poweruser"
create_user "viewer@compass.demo" "compass-viewer"

cat <<EOF

============================================================================
Cognito users created / updated:
  poweruser@compass.demo  (compass-poweruser, org_unit ONR-Corporate)
  viewer@compass.demo     (compass-viewer, org_unit Code-30)
  Permanent password: $PASSWORD
============================================================================

REMAINING STEP — MUST BE DONE BY A HUMAN, INTERACTIVELY:

The user pool has MfaConfiguration=ON (SOFTWARE_TOKEN_MFA only). Every user
must enroll a TOTP authenticator before they can complete sign-in. This
CANNOT be scripted end-to-end: a person has to scan the QR code (or type the
secret) into an authenticator app.

Do this once per user, well before recording day:

  1) Sign in via the Cognito Hosted UI (or CLI) to get a valid session, then
     start software-token association. From the CLI, first obtain a session
     via an admin-initiated auth challenge:

       aws cognito-idp admin-initiate-auth --region $REGION \\
         --user-pool-id $POOL_ID \\
         --client-id <WebClientId> \\
         --auth-flow ADMIN_USER_PASSWORD_AUTH \\
         --auth-parameters USERNAME=poweruser@compass.demo,PASSWORD='$PASSWORD'

     This returns an AuthenticationResult with an AccessToken (MFA may
     already be REQUIRED at this point if a device is already set up — for
     first-time enrollment it returns the tokens directly since no MFA
     device exists yet).

  2) Associate a software token using that AccessToken:

       aws cognito-idp associate-software-token --region $REGION \\
         --access-token <AccessToken>

     This returns a SecretCode. THIS IS THE STEP A HUMAN MUST DO: take the
     SecretCode, add it to an authenticator app (as a manual entry, or
     render it as a QR code yourself — otpauth://totp/Compass:poweruser@compass.demo?secret=<SecretCode>&issuer=Compass)
     and get the current 6-digit TOTP code from the app.

  3) Verify the software token with that 6-digit code:

       aws cognito-idp verify-software-token --region $REGION \\
         --access-token <AccessToken> \\
         --user-code <6-digit-code-from-authenticator-app>

  4) Mark TOTP as the preferred MFA method for the user:

       aws cognito-idp admin-set-user-mfa-preference --region $REGION \\
         --user-pool-id $POOL_ID \\
         --username poweruser@compass.demo \\
         --software-token-mfa-settings Enabled=true,PreferredMfa=true

  Repeat steps 1-4 for viewer@compass.demo.

  Easiest in practice: sign in through the deployed Hosted UI in a browser —
  it walks each user through TOTP enrollment (QR code shown on screen) on
  first login automatically. Keep both demo accounts in the same
  authenticator app so a presenter can switch personas without juggling
  phones. Do this well before recording day, not on it.
============================================================================
EOF
