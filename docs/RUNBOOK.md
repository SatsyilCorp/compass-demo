# Compass — Operations Runbook

Everything needed to go from a clean AWS account to the recorded
demonstration, in order: deploy → migrate → seed → enroll users → publish
frontend → record → tear down. Commands assume the repo root, bash/zsh, and
`AWS_REGION=us-east-1`.

## 0. Prerequisites

- AWS account with admin-capable credentials; region **us-east-1** (pinned —
  the WAF WebACL is CLOUDFRONT scope, which only exists there).
- AWS CLI v2, AWS SAM CLI, Docker (required: `sam build --use-container`
  resolves linux/arm64 wheels for psycopg2/numpy — a macOS-native build will
  produce broken layers).
- Python 3.11+, Node 20+, pnpm.
- Bedrock model access enabled in the account for `amazon.nova-lite-v1:0` and
  `amazon.titan-embed-text-v2:0` (Bedrock console → Model access). Without
  it, chat/summary/embedding calls fail at runtime with an access error.

Zero-AWS alternative: the frontend mock mode (`README.md` quickstart) needs
none of the above.

## 1. Configure

```bash
cp samconfig.toml.template samconfig.toml
```

Leave the `Web*` overrides empty for the first deploy (the CloudFront domain
does not exist yet). `parameter_overrides` is a TOML array of `"Key=Value"`
strings — no spaces inside values.

## 2. First deploy

```bash
./src/functions/migrator/prepare_migrations.sh   # stage db/migrations into the migrator package
sam build --use-container
sam deploy                                        # confirm the changeset
```

First deploy takes ~20–30 min (Aurora + CloudFront dominate). Capture the
outputs:

```bash
aws cloudformation describe-stacks --stack-name compass-demo \
  --query 'Stacks[0].Outputs' --output table
```

You will use: `ApiBaseUrl`, `CloudFrontDomain`, `UserPoolId`, `WebClientId`,
`CognitoDomain`, `WebBucketName`, `WebDistributionId`, `RawBucketName`,
`MigratorFunctionName`.

## 3. Second deploy (the two-deploy dance)

Cognito callback URLs need the CloudFront domain from step 2. Edit
`samconfig.toml`:

```toml
"WebCallbackUrl=https://<CloudFrontDomain>/login/",
"WebLogoutUrl=https://<CloudFrontDomain>/login/",
"WebOrigin=https://<CloudFrontDomain>",
```

Then `sam deploy` again (fast — only Cognito/API CORS change).
`http://localhost:3000` remains registered for local dev either way.

## 4. Migrate the database

The cluster has no public endpoint; the in-VPC migrator Lambda applies
`db/migrations/*.sql` in order and records each in
`compass._schema_migrations` (idempotent — safe to re-run):

```bash
aws lambda invoke --function-name compass-demo-migrator \
  --payload '{"migrate":"all"}' \
  --cli-binary-format raw-in-base64-out /dev/stdout
```

Expect a JSON result listing `001_schema` and `002_rls` as applied. If it
reports no migrations found, you skipped `prepare_migrations.sh` before
`sam build` — run it and redeploy, or pass the SQL inline (the handler
accepts `{"migrate":"all","migrations":[{"name":...,"sql":...}]}`).

## 5. Seed data

Fixtures are committed under `seed/`; regenerate any time (stdlib-only,
deterministic except license renewal dates, which track "now"):

```bash
python3 scripts/seed_data.py
```

Load by running the **real pipeline** — upload to the raw bucket and let
EventBridge → Step Functions ingest, gate, and curate:

```bash
RAW_BUCKET=$(aws cloudformation describe-stacks --stack-name compass-demo \
  --query 'Stacks[0].Outputs[?OutputKey==`RawBucketName`].OutputValue' --output text)

# Baseline portfolio (~400 grants, batch seed-initial-2026):
aws s3 cp seed/grants_portfolio.json s3://$RAW_BUCKET/drops/grants_portfolio.json
# Licenses (no pipeline — small reference table; see below)
```

**Do NOT pre-load the three demo drops** (`seed/drops/*.json`) before
recording day — they are ingested live during Element 3 of the demo script.
For a non-recording environment, upload them the same way.

Licenses: `seed/licenses.json` feeds the `licenses` table. Load it via the
migrator's SQL path or a one-off insert (adjust if the ops tooling grows a
dedicated loader):

```bash
python3 - <<'EOF'
# Renders seed/licenses.json into INSERT statements and applies them via the
# migrator Lambda's inline-SQL mode.
import json, subprocess
recs = json.load(open("seed/licenses.json"))["licenses"]
rows = []
for r in recs:
    ds = "ARRAY[" + ",".join("'" + d.replace("'", "''") + "'" for d in r.get("datasets", [])) + "]::text[]"
    vals = (r["vendor"].replace("'", "''"), r["product"].replace("'", "''"), ds,
            (r.get("entitlements") or "").replace("'", "''"), r.get("seats_used") or 0,
            r.get("seats_total") or 0, r["renews_on"], (r.get("owner") or "").replace("'", "''"),
            r.get("status") or "active")
    rows.append("INSERT INTO licenses (vendor,product,datasets,entitlements,seats_used,seats_total,renews_on,owner,status) "
                f"VALUES ('{vals[0]}','{vals[1]}',{vals[2]},'{vals[3]}',{vals[4]},{vals[5]},'{vals[6]}','{vals[7]}','{vals[8]}');")
sql = "DELETE FROM licenses;\n" + "\n".join(rows)
payload = json.dumps({"migrate": "all", "force": True,
                      "migrations": [{"name": "seed_licenses", "sql": sql}]})
subprocess.run(["aws", "lambda", "invoke", "--function-name", "compass-demo-migrator",
                "--payload", payload, "--cli-binary-format", "raw-in-base64-out", "/dev/stdout"], check=True)
EOF
```

Verify ingest end to end (with a poweruser token from §6):

```bash
curl -s $API/ingest/status -H "Authorization: Bearer $TOKEN" | python3 -m json.tool | head -30
```

## 6. Enroll demo users

MFA is ON (TOTP only) and self-signup is disabled. Create the two personas:

```bash
POOL=<UserPoolId>
for u in demo-poweruser demo-viewer; do
  aws cognito-idp admin-create-user --user-pool-id $POOL \
    --username "$u@example.com" --user-attributes Name=email,Value="$u@example.com" \
      Name=email_verified,Value=true --message-action SUPPRESS
  aws cognito-idp admin-set-user-password --user-pool-id $POOL \
    --username "$u@example.com" --password '<16+ char password>' --permanent
done
aws cognito-idp admin-add-user-to-group --user-pool-id $POOL \
  --username demo-poweruser@example.com --group-name compass-poweruser
aws cognito-idp admin-add-user-to-group --user-pool-id $POOL \
  --username demo-viewer@example.com --group-name compass-viewer
```

First hosted-UI sign-in prompts each user to **register a TOTP authenticator**
— do this well before recording day and keep both accounts in the same
authenticator app. Group membership is what drives role/org_unit
(poweruser → ONR-Corporate; viewer → Code-30); a user in neither group is
denied by the handlers.

## 7. Build and publish the frontend

```bash
cd frontend
cp .env.example .env.local
# In .env.local set:
#   NEXT_PUBLIC_USE_MOCK=false
#   NEXT_PUBLIC_AUTH_DISABLED=false
#   NEXT_PUBLIC_API_BASE_URL=<ApiBaseUrl>
#   NEXT_PUBLIC_COGNITO_AUTHORITY=https://cognito-idp.us-east-1.amazonaws.com/<UserPoolId>
#   NEXT_PUBLIC_COGNITO_DOMAIN=https://<CognitoDomain>
#   NEXT_PUBLIC_COGNITO_CLIENT_ID=<WebClientId>
#   NEXT_PUBLIC_COGNITO_REDIRECT_URI=https://<CloudFrontDomain>/login/
#   NEXT_PUBLIC_COGNITO_POST_LOGOUT_REDIRECT_URI=https://<CloudFrontDomain>/login/
pnpm install && pnpm build      # static export → out/
aws s3 sync out/ s3://<WebBucketName>/ --delete
aws cloudfront create-invalidation --distribution-id <WebDistributionId> --paths '/*'
```

Smoke-check: open `https://<CloudFrontDomain>`, sign in as each persona,
confirm `/dashboard` shows scoped vs. full data.

## 8. Recording-day configuration

Per `docs/DEMO_SCRIPT.md` preflight — these are deploy parameters, not code
changes, and the script discloses them on camera:

1. **Trip-able aggregation guard:** redeploy with `ExportMaxRows=250`
   (`samconfig.toml` override). The synthetic portfolio (~480 curated rows)
   never trips the 5000 default.
2. **Parquet on (recommended):** uncomment `pyarrow==17.0.0` in
   `src/functions/export/requirements.txt`, `sam build --use-container`,
   `sam deploy`. If skipped, the export API honestly reports the parquet
   layer absent and returns CSV — the script has a branch for that.
3. **Ticker on:** `StreamTickerState=ENABLED` (default).
4. Ensure the three `seed/drops/*.json` files are **not** in the bucket yet;
   ensure at least one analytics run exists (`POST /analytics/run` as
   poweruser) so catalog/dashboard are populated at minute 2.
5. One timed full rehearsal. Then record per `docs/DEMO_SCRIPT.md`.

After recording: fill `volume_iv/TIMESTAMP_INDEX.md`, upload per
`volume_iv/SUBMISSION_LINKS.md`. If the stack stays up for the Government's
optional live session, restore `ExportMaxRows` to the production-like default
or leave 250 and disclose it again — consistency with the video matters more.

## 9. Routine operations

| Task | Command |
|---|---|
| Re-run migrations (idempotent) | §4 command |
| Re-seed / add a batch | `aws s3 cp <file> s3://$RAW_BUCKET/drops/` (pipeline fires automatically) |
| Trigger ingest from the API | `POST /ingest/simulate` (poweruser token; empty body = most recent drop) |
| Run analytics | `POST /analytics/run` (poweruser) |
| Generate RMF artifact locally | `python3 src/functions/rmf_artifact/app.py -o /tmp/pps.md` |
| Pause the ticker between demos | redeploy with `StreamTickerState=DISABLED` |
| Isolated experiments | `sam deploy --config-env dev` (separate `compass-demo-dev` stack; ticker off) |
| Tail a function's logs | `sam logs -n <LogicalId> --stack-name compass-demo --tail` |

## 10. Teardown

Buckets must be emptied first (versioned buckets: delete versions too), then
delete the stack:

```bash
for b in $(aws cloudformation describe-stacks --stack-name compass-demo \
    --query 'Stacks[0].Outputs[?contains(OutputKey,`BucketName`)].OutputValue' --output text); do
  aws s3 rm s3://$b --recursive
  aws s3api delete-objects --bucket $b --delete "$(aws s3api list-object-versions --bucket $b \
    --query '{Objects: [Versions,DeleteMarkers][][].{Key:Key,VersionId:VersionId}}' --output json)" 2>/dev/null || true
done
sam delete --stack-name compass-demo
```

`DeletionProtection` is false by design. The KMS key enters its 7-day pending
deletion window.

## 11. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `sam deploy` fails on WAF | Stack not in us-east-1 — the region is pinned; check `samconfig.toml` |
| Migrator: "no migrations found" | `prepare_migrations.sh` not run before `sam build`; run it and redeploy, or use the inline-SQL payload |
| Lambda import errors (`psycopg2`/`numpy`) | Built without `--use-container` on macOS — darwin wheels in a linux/arm64 layer; rebuild in container |
| 401 on every API call | Missing/expired bearer token, or token from the wrong client — API accepts the stack's `WebClient` audience only |
| Login loop / redirect mismatch | Second deploy (step 3) not done, or `.env.local` redirect URIs don't match Cognito's registered callbacks exactly |
| Viewer sees no rows anywhere | Correct behavior if no `Code-30` rows are curated yet — seed the baseline (§5) |
| Chat/summary/embeddings error | Bedrock model access not enabled in the account (§0) |
| Batch stuck "queued" | Check the state machine: `aws stepfunctions list-executions --state-machine-arn <IntakeStateMachineArn>`; express-run details are in the CloudWatch vended log group |
| Export 413 | Result exceeds inline limit with no `EXPORT_BUCKET`, or the hard row cap — narrow filters |
| CloudFront 404s on routes | `out/` not synced or invalidation missed; the path-rewrite function expects the static-export layout |
