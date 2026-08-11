#!/usr/bin/env bash
# Compatibility entrypoint for secure, resumable Cognito identity enrollment.
set -euo pipefail

if [ "$#" -gt 1 ]; then
  echo "ERROR: this command accepts only an optional stack name" >&2
  exit 2
fi

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$here/provision_demo_identities.py" --stack "${1:-compass-demo}"
