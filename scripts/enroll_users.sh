#!/usr/bin/env bash
# Canonical entrypoint for password-only team identities and a TOTP presenter.
set -euo pipefail

if [ "$#" -gt 1 ]; then
  echo "ERROR: this command accepts only an optional stack name" >&2
  exit 2
fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$here/configure_demo_identity_posture.py" --stack "${1:-compass-demo}"
