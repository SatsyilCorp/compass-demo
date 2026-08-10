#!/usr/bin/env bash
# Stage db/migrations into the migrator's Lambda package.
#
# `sam build` can only package files under the function's CodeUri
# (src/functions/migrator/), but the SQL lives at the repo root in
# db/migrations/. Run this before `sam build` and the migrator's
# {"migrate":"all"} event will find the files inside the deployed package.
#
#   ./src/functions/migrator/prepare_migrations.sh && sam build
#   aws lambda invoke --function-name compass-demo-migrator \
#     --payload '{"migrate":"all"}' --cli-binary-format raw-in-base64-out /dev/stdout
#
# Not required for local runs: the handler also walks up from its own directory
# and finds db/migrations directly (see migrator/app.py:candidate_roots).
#
# The alternative — no staging at all — is to have the deploy script read the
# files itself and invoke with
#   {"migrate":"all","migrations":[{"name":"001_schema","sql":"..."}]}
# which the handler supports and which keeps a single copy of the SQL.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../../.." && pwd)"
src="$repo/db/migrations"
dst="$here/migrations"

[ -d "$src" ] || { echo "no migrations at $src" >&2; exit 1; }

rm -rf "$dst"
mkdir -p "$dst"
cp -R "$src"/*.sql "$dst"/

echo "staged $(ls -1 "$dst" | wc -l | tr -d ' ') migration file(s) into $dst"
ls -1 "$dst"
