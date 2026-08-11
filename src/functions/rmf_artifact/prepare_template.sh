#!/usr/bin/env bash
# Stage the root SAM template inside the RMF Lambda CodeUri. SAM packages only
# files below CodeUri, while the artifact generator intentionally reads this
# bundled copy before any network source.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
source_template="$repo/template.yaml"
bundled_template="$here/template.yaml"

if [ "${1:-}" = "--check" ]; then
  if ! cmp -s "$source_template" "$bundled_template"; then
    echo "ERROR: RMF bundled template is stale; run $0" >&2
    exit 1
  fi
  exit 0
fi

if [ "$#" -ne 0 ]; then
  echo "Usage: $0 [--check]" >&2
  exit 2
fi

temporary_template="$(mktemp "${bundled_template}.tmp.XXXXXX")"
trap 'rm -f "$temporary_template"' EXIT
cp "$source_template" "$temporary_template"
chmod 0644 "$temporary_template"
cmp -s "$source_template" "$temporary_template"
mv "$temporary_template" "$bundled_template"
trap - EXIT
