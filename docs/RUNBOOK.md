# Compass operations and recording runbook

This runbook takes the current candidate from source to a live, rehearsed
recording environment. Commands assume the repository root and
`AWS_REGION=us-east-1`.

## Current Satsyil evidence snapshot

The HA stack was deployed and live-verified on 2026-08-11. This snapshot is
release evidence, not a substitute for the final exact-commit workflow record
or human rehearsal:

- 25 protected API operations across 23 URL paths
- 17 functions, 11 alarms, and 2 dashboards
- private encrypted Aurora writer and reader, 14-day backups, and deletion
  protection
- poweruser, reviewer, and viewer personas ready with password plus TOTP
- bounded preparation ready with 19 of 19 checks passing
- CORS passing on all 25 protected operations
- all nine screens verified through a real Cognito session with no
  `Failed to fetch` response or browser command error
- 1K, 10K, 100K, and 1M live Scale Runs completed with ready Parquet exports

The saved Scale acceptance receipts use direct IAM Lambda invocation with a
staged `/prod` event. They exercise the deployed route handler and live data
plane but bypass Cognito, API Gateway transport, WAF, and the browser. The
separate browser pass verifies those interactive boundaries. Recording release
remains false until the exact commit has its required workflow evidence and a
human completes the timed rehearsal.

## 1. Operator inputs

Prepare these outside the repository:

- AWS account and an approved deployment role for `us-east-1`
- GitHub environment named `demo` with required reviewers
- GitHub variable `AWS_REGION`
- GitHub variable `STACK_NAME`
- GitHub variable `EXPORT_MAX_ROWS`, recommended `250` for the rehearsed demo
- GitHub variable `DATABASE_RESILIENCE_MODE`, recommended `demo`; use `ha` only
  as an intentional higher-cost opt-in
- GitHub secret `AWS_DEPLOY_ROLE_ARN`
- Bedrock model access for `amazon.nova-lite-v1:0` and
  `amazon.titan-embed-text-v2:0`
- Three enrolled TOTP demo accounts: one scoped viewer and two distinct
  powerusers for requester and reviewer duties
- Authenticator access during the recording
- A recording operator who is not narrating

Do not put passwords, TOTP secrets, bearer tokens, AWS keys, or evaluator
credentials in the repository, terminal history, video, or System Inspector.

## 2. Release gates before deployment

Run the same checks as `.github/workflows/quality.yml`:

```bash
python3 scripts/check_no_em_dash.py
ruff check src scripts
pip-audit --no-deps --disable-pip \
  -r src/common/requirements.txt \
  -r src/functions/authorizer/requirements.txt \
  -r src/functions/rmf_artifact/requirements.txt \
  -r src/functions/analytics/requirements.txt
PYTHONPATH=src/common/python python3 -m pytest -q scripts/tests src/common/tests src/functions/*/tests
./src/functions/migrator/prepare_migrations.sh
git diff --exit-code -- db/migrations src/functions/migrator/migrations
sam validate --lint
sam build --use-container
cd frontend
pnpm install --frozen-lockfile
pnpm audit --prod
pnpm typecheck
pnpm test:scenario
NEXT_PUBLIC_USE_MOCK=true NEXT_PUBLIC_AUTH_DISABLED=true pnpm build
pnpm exec playwright install chromium
pnpm test:e2e
```

Stop if any check fails. Preserve the browser report as rehearsal evidence.

## 3. Preferred controlled deployment

Use the manually dispatched `Controlled demo deployment` workflow. It must:

1. Run only from the reviewed recording commit.
2. Enter the protected `demo` environment.
3. Assume AWS access through OIDC.
4. Stamp `DeployRevision` with the short commit SHA.
5. Validate `EXPORT_MAX_ROWS` as a positive integer and
   `DATABASE_RESILIENCE_MODE` as `demo` or `ha`.
6. Stage migrations and build Lambda artifacts in a Linux arm64 container.
7. Detect whether the stack already exists and derive the exact CloudFront
   origin and `/login/` callback values from stack outputs when it does.
8. For an existing stack, send the compatible additive source migrations to
   the deployed migrator before changing application code.
9. Require an `ok` response and `role_bootstrap.status=granted` from that
   expansion pass.
10. Deploy the reviewed infrastructure change set with the validated export
    threshold and database mode. For a fresh stack, deploy once with bootstrap
    web values, derive the CloudFront origin, and automatically deploy a second
    time with the exact origin and `/login/` callback and logout values.
11. Invoke the newly bundled migrator with `{"migrate":"all"}` and require the
    same `ok` and `granted` results.
12. Build the frontend with live authentication and API values.
13. Publish the immutable static output and invalidate CloudFront.
14. Confirm the public page is reachable with the expected transport and
    browser security headers, and the unauthenticated System Inspector API
    request returns 401.

Save the workflow run URL as internal release evidence. Do not put it into
Volume IV unless evaluator access is approved.

No operator-supplied public web URL variables are required by this workflow.
Existing stacks derive them before the change set. Fresh stacks complete the
required two-phase identity binding within the same controlled workflow run.

## 4. Manual deployment fallback

```bash
cp samconfig.toml.template samconfig.toml
./src/functions/migrator/prepare_migrations.sh
sam validate --lint
sam build --use-container
```

For an existing stack, apply the additive source migrations through the
currently deployed migrator before `sam deploy`:

```bash
python3 scripts/prepare_migration_payload.py /tmp/compass-migration-request.json
aws lambda invoke \
  --region us-east-1 \
  --function-name compass-demo-migrator \
  --payload fileb:///tmp/compass-migration-request.json \
  --cli-binary-format raw-in-base64-out \
  /tmp/compass-migration-expand-response.json \
  --query '{StatusCode:StatusCode,FunctionError:FunctionError}' \
  --output json >/tmp/compass-migration-expand-invoke.json
python3 -c 'import json; meta=json.load(open("/tmp/compass-migration-expand-invoke.json")); data=json.load(open("/tmp/compass-migration-expand-response.json")); assert meta.get("StatusCode")==200 and not meta.get("FunctionError"), meta; assert data.get("status")=="ok", data; assert data.get("role_bootstrap", {}).get("status")=="granted", data'
```

The response must report `status: ok` and
`role_bootstrap.status: granted`. Stop before deploying code if either value is
absent. A brand-new stack skips this pre-deploy pass because no migrator exists
yet.

Deploy the built stack:

```bash
sam deploy
```

The manual fallback still requires a second deployment for a fresh stack
because the Cognito callback values depend on the generated CloudFront domain.
Capture the stack output privately, set these parameter overrides, and deploy
again:

```text
WebCallbackUrl=https://<CloudFrontDomain>/login/
WebLogoutUrl=https://<CloudFrontDomain>/login/
WebOrigin=https://<CloudFrontDomain>
DeployRevision=<12-character recording commit>
DatabaseResilienceMode=demo
ExportMaxRows=250
```

`demo` is the default and lowest-cost database mode. Use `ha` only when the
team accepts the additional database cost and the teardown implications.

After `sam deploy`, apply the migrations bundled with the new function:

```bash
./scripts/migrate.sh compass-demo
```

The response must list or skip all four migrations without error:

- `001_schema`
- `002_rls`
- `003_security_hardening`
- `004_opaque_approval_capability`

Verify the role bootstrap reports `granted`. Bootstrap failure is fatal and
must stop the release.

Build and publish the live frontend:

```bash
./scripts/build-frontend.sh compass-demo
./scripts/upload-to-cloudfront.sh compass-demo
```

## 5. Database resilience selection

| Mode | Writer | Reader | Backup retention | Deletion protection | Demonstrated claim |
|---|---:|---:|---:|---|---|
| `demo` | 1 | 0 | 7 days | Off | Reproducible single-region demo with point-in-time backup retention |
| `ha` | 1 | 1 cluster reader | 14 days | On | Single-region reader promotion posture; verify actual AZ placement |

Neither mode proves production disaster recovery. Do not state an RTO or RPO
unless it has been approved and measured in a documented exercise.

If `ha` is selected, deletion protection must be turned off through an
approved stack change before teardown.

## 6. Create and enroll demo users

Supply the expected account identifier through the protected shell environment,
then run the bounded named-profile utility:

```bash
AWS_PROFILE=satsyil \
SATSYIL_EXPECTED_ACCOUNT_ID="$SATSYIL_EXPECTED_ACCOUNT_ID" \
./scripts/enroll_users.sh compass-demo
```

The utility creates one strong shared password, creates or updates the three
operator accounts, and completes Cognito software-token MFA setup with three
unique RFC 6238 factors:

- `poweruser@compass.demo` as the requester in `compass-poweruser`
- `reviewer@compass.demo` as the reviewer in `compass-poweruser`
- `viewer@compass.demo` as the scoped viewer in `compass-viewer`

Credentials are written only to the ignored
`artifacts/private/demo-identities.json` artifact with mode `0600`. The utility
does not print credentials or AWS identifiers. Transfer each factor to the
protected presenter authenticator without displaying it in a terminal or on
camera. The temporary password-auth client is deleted after enrollment,
including after a failure. A rerun reuses completed factors and resumes an
incomplete enrollment safely. Test all three logins at least one day before
recording.

The four-eyes approval control requires different authenticated identities for
request and decision. Enroll one poweruser requester, one poweruser reviewer,
and the scoped viewer. Rehearse the supported reviewer-inbox flow in three
separate browser profiles. The requester session must remain open so it can
retry the exact export after the reviewer decides it.

## 7. Prepare the rehearsal baseline

Regenerate fixtures only when a reviewed fixture change is intended. The
generator is deterministic except for documented date-relative license
fields.

```bash
python3 scripts/seed_data.py
git diff -- seed/
```

Do not run `scripts/seed.sh` against the recording stack. That legacy helper
publishes all three demonstration drops into the live ingest prefix.

After migrations and all three TOTP enrollments are complete, run the bounded
operator preparation workflow:

```bash
python3 scripts/prepare_demo.py prepare \
  --stack compass-demo \
  --region us-east-1 \
  --confirm-synthetic-reset RESET_FIXED_SYNTHETIC_DEMO_DATA \
  --receipt artifacts/demo-preflight.json
```

The exact confirmation value is intentional. Preparation then:

1. Validates five fixed local fixtures against the synthetic contract,
   generator seed, allowlisted identifiers, record counts, mock markings, and
   license identities.
2. Requires `poweruser@compass.demo`, `reviewer@compass.demo`, and
   `viewer@compass.demo` to be enabled, confirmed, enrolled in TOTP, and in
   exactly their expected Compass group among the supported groups.
3. Stages the five fixtures with SHA-256 metadata under `demo-stage/` using a
   non-ingestible `.fixture` suffix. The EventBridge rule accepts only the
   separate `drops/` prefix.
4. Deletes only the three fixed live drop keys and verifies that all three are
   absent before preparation continues.
5. Applies the migrations idempotently and requires the runtime-role bootstrap
   to report `granted`.
6. Refuses all database deletion if any non-demo curated grant, raw row,
   quality receipt, license, approval, model run, anomaly, lineage record, or
   topic assignment is present. Otherwise, one transaction removes only the
   allowlisted synthetic demo state while preserving the append-only audit log.
7. Loads 400 baseline grants, eight licenses, five quality receipts, and the
   baseline lineage receipt.
8. Invokes the deployed Analytics Lambda through its fixed, IAM-protected
   preparation action as service actor `compass-demo-preparer`, then accepts
   only one completed run over 400 documents with eight topics and persisted
   topic assignments.
9. Writes a redacted machine-readable receipt with logical locators and hashes,
   never a physical bucket name.

The final receipt must say `status: ready`, `ready: true`, and show all three
live drop keys as `absent`. Keep the receipt as internal release evidence. It
is ignored by Git under `artifacts/`.

The same `prepare` command is the supported reset after a failed rehearsal or
abandoned take. It never creates users, resets passwords, changes group
membership, or enrolls MFA. Its destructive scope cannot be widened with a
caller-selected table, batch, run, license, approval actor, or object key.

Run the read-only check again immediately before recording:

```bash
python3 scripts/prepare_demo.py check \
  --stack compass-demo \
  --region us-east-1 \
  --receipt artifacts/demo-preflight.json
```

The check validates Cognito readiness, fixture hashes, live-key absence, the
database baseline, quality and lineage receipts, license count, and baseline
analytics without reseeding or changing identity state.

## 8. Recording configuration

Use these explicit settings for the recording stack:

| Setting | Recording value | Reason |
|---|---|---|
| `NEXT_PUBLIC_USE_MOCK` | `false` | The primary recording proves the live backend |
| `NEXT_PUBLIC_AUTH_DISABLED` | `false` | Cognito and MFA stay in the path |
| `ExportMaxRows` | `250`, after confirming the full-portfolio request exceeds it | Enables the cross-persona guard path through a reviewed deployment value |
| `APPROVAL_REQUIRE_FOUR_EYES` | `true` | A requester cannot decide the same approval |
| `StreamTickerState` | `ENABLED` | Shows the synthetic activity stream |
| `DatabaseResilienceMode` | State the deployed value on camera | Prevents HA or DR overclaiming |

Prefer CSV for the recorded release. Use parquet only if pyarrow is included,
the container build passes, and the exact path was rehearsed. Do not rely on a
format fallback during the recording.

## 9. Live verification matrix

Complete every row after deployment and before the timed rehearsal.

| Check | Expected evidence |
|---|---|
| Public landing | CloudFront page renders at desktop and phone widths |
| Unauthenticated boundary | `GET /system/evidence` returns 401 |
| Poweruser login | Cognito presents TOTP and `/me` resolves corporate scope |
| Viewer login | `/me` resolves Code-30; funding values are masked or refused |
| System Inspector | Badge says Live service; revision matches recording commit; refresh changes correlation ID |
| Identity contract | All 25 protected operations accept the intended Cognito session when Scale Run is enabled |
| CORS | Approved origin succeeds; a random origin is not reflected |
| Clean intake | Batch passes and curated row count is positive |
| Legacy intake | Compatible renamed schema normalizes and reaches an allowed disposition |
| Defective intake | Batch is quarantined and curated row count is zero |
| Activity ticker | Database projection remains ordered; recent Kinesis receipts merge without duplicates; an unscoped receipt is corporate-only |
| Catalog lineage | New batch opens through `/catalog/lineage/?batch=<id>` without a rebuild |
| Analytics | New run completes and System Inspector shows model-run metadata |
| RAG | Answer is returned with governed citations under the current persona |
| Four eyes | Requester cannot self-approve; other persona can decide |
| Approval binding | Changed export filters do not accept the old approval |
| Approval consumption | Exact approved request succeeds once; second use is denied |
| Server audit | System Inspector displays sanitized approval and export receipts |
| OpenAPI | Protected OpenAPI 3.1 panel loads |
| Observability | Eleven alarms exist and both dashboards receive current metrics |
| Preparation receipt | Redacted receipt says ready, fixture hashes match, and all three live drop keys are absent |
| Scale Lab authorization | `/admin/scale/` and all eight Scale Run operations allow only the corporate poweruser |
| Scale Run receipts | Completed acceptance evidence reconciles records and includes Run Manifest, Quality, Intelligence, Performance, and Cost Receipts |
| Scale Export Job | Ready receipt reports exact rows, bytes, Parquet format, SHA-256, expiry, and audit evidence |
| Scale disclosure | Browser receipts show logical locators and no physical infrastructure identifiers |

## 10. Recording preflight

Perform these steps 30 to 60 minutes before the take:

1. Run the read-only `prepare_demo.py check` command and require a ready
   receipt.
2. Confirm the recording commit and deploy revision match.
3. Confirm the mode badge says Live service, not Replay fixture.
4. Warm dashboard, analytics, RAG, catalog, export, and System Inspector once.
5. Confirm the receipt shows every live drop key absent and the baseline
   analytics and license checks passing.
6. Prepare separate viewer, poweruser requester, and poweruser reviewer browser
   profiles at the intended pages. Do not expose saved passwords or bearer
   tokens.
7. Close browser developer tools, notifications, password managers, chat apps,
   and unrelated tabs.
8. Set browser zoom to the rehearsed value and test the mobile drawer only if
   it is in the script.
9. Close Presenter Guide. It is a rehearsal aid and would be an overlay in the
   submitted recording.
10. Use a local printed or second-device run sheet. Do not show slides.
11. Start a private timer. Target 39:15 and stop before 50:00.
12. Record one continuous take with no post-production edits or marketing
    overlays.

## 11. Live Element 3 drop commands

For the primary on-camera path, use the three Live release buttons on the
Ingest page. Each protected request releases exactly one receipted fixture and
lets the object-created event start the workflow once. The commands below are
operator fallbacks. Each downloads and revalidates the exact staged bytes,
publishes them to the fixed live landing key, and prints only logical locators.

```bash
python3 scripts/prepare_demo.py release-drop good \
  --stack compass-demo --region us-east-1

python3 scripts/prepare_demo.py release-drop bad \
  --stack compass-demo --region us-east-1

python3 scripts/prepare_demo.py release-drop compatible \
  --stack compass-demo --region us-east-1
```

Each drop is one-shot by default. The command refuses when its target already
exists. `--allow-redrop` is only for a deliberate recovery after diagnosing a
failed ingestion attempt. Do not use it in a normal recording. Never resolve
or print the physical bucket name on camera.

## 12. Replay fallback

If the live environment is unavailable before recording, fix it and reschedule
the take. Do not silently switch the submitted cloud proof to replay.

Replay remains useful for rehearsal and evaluator reproduction:

```bash
cd frontend
NEXT_PUBLIC_USE_MOCK=true NEXT_PUBLIC_AUTH_DISABLED=true pnpm dev
```

The UI must show Replay fixture. Use `Reset replay` before each rehearsal.
Replay can prove interaction design and deterministic business rules, but not
AWS runtime, Cognito, network, database, workflow, or Bedrock execution.

## 13. Volume IV completion

After recording:

1. Record the exact video runtime and actual start time for every element and
   strategic prompt in `volume_iv/TIMESTAMP_INDEX.md`.
2. Enter presenter names exactly as they appear in Attachment 7 and Volume II.
3. Tag the exact recording commit and record its full SHA.
4. Configure read-only repository access and test it outside the offeror
   organization.
5. Upload the single continuous video to the approved private host.
6. Enter the URL and password in `volume_iv/SUBMISSION_LINKS.md`.
7. Test video and repository access in a clean desktop browser and on a phone.
8. Remove all instructional notes marked `EXTERNAL INPUT` from the final
   submission copy after each value is supplied.

## 14. Troubleshooting

| Symptom | Check |
|---|---|
| SAM dependency import failure | Rebuild with `sam build --use-container`; all functions target arm64 |
| Migrator reports no files | Run `prepare_migrations.sh`, rebuild, redeploy, then invoke `{"migrate":"all"}` |
| Migrator omits migration 003 or 004 | Confirm staged and source migration directories match exactly |
| Login redirect error | Confirm both Cognito callback values end in `/login/` and match frontend values exactly |
| All API routes return 401 | Confirm token issuer, client audience, expiration, and deployed web client |
| Valid user receives 403 | Confirm membership in exactly one supported Cognito group |
| Viewer sees no portfolio rows | Confirm the baseline contains curated Code-30 records |
| System Inspector says Replay fixture | The frontend was built with mock mode; rebuild and publish with live values |
| System Inspector unavailable | Check evidence Lambda log and database reachability; do not expose raw errors in the video |
| Bad batch appears curated | Stop the rehearsal and investigate; the release invariant has failed |
| Self-approval succeeds | Stop the rehearsal and verify `APPROVAL_REQUIRE_FOUR_EYES=true` |
| Approved export accepts changed filters | Stop the rehearsal; exact fingerprint binding has failed |
| Approval works twice | Stop the rehearsal; one-time consumption has failed |
| New lineage route returns 404 | Use `/catalog/lineage/?batch=<id>` and confirm the latest frontend is published |
| Bedrock call fails | Confirm account model access and function IAM for the declared model IDs |
| Prepare stops at confirmation | Supply the exact value `RESET_FIXED_SYNTHETIC_DEMO_DATA` only after confirming this is the synthetic recording stack |
| Prepare stops at identity verification | Confirm all three exact users are enabled, confirmed, uniquely grouped, and enrolled in software-token MFA |
| Prepare refuses synthetic reset | A non-demo curated grant exists; stop and use a clean demonstration stack rather than widening the reset scope |
| Release-drop says the key exists | The scenario is not at baseline; rerun bounded preparation or diagnose before using the explicit retry flag |

## 15. Production Scale Run operator and evaluator path

This section is an additional Scale Run path. It does not replace the fixed
Factor 3 preparation and recording sequence above. Source code, deployment
configuration, and pre-run estimates are not evidence that the path is live or
that a profile has completed. Make a runtime claim only after preserving the
corresponding acceptance receipt and independently verifying browser identity.

### 15.1 Choose the database cost posture

The [cost model](COST_MODEL.md) forecasts fixed platform cost at $119.90 per
730-hour month for `demo` and $163.70 for `ha`. The `ha` forecast adds one
Aurora reader. Both figures are planning estimates and exclude
usage-sensitive storage, transfer, API traffic, Lambda, Bedrock, tax, support,
discounts, and free tier. `scripts/deploy_satsyil.sh` defaults to `ha`; select
`demo` deliberately when the lower fixed cost and single-writer limitation are
appropriate. The Satsyil deployment used `ha`; $163.70 is still a monthly
forecast, not observed billing.

### 15.2 Deploy the Scale Adapter path

The bounded named-profile entrypoint requires `AWS_PROFILE=satsyil`,
`AWS_REGION=us-east-1`, and the expected 12-digit account identifier in
`SATSYIL_EXPECTED_ACCOUNT_ID`. Supply that value through a protected shell
environment and do not place it in the repository or command history:

```bash
AWS_PROFILE=satsyil \
AWS_REGION=us-east-1 \
SATSYIL_EXPECTED_ACCOUNT_ID="$SATSYIL_EXPECTED_ACCOUNT_ID" \
STACK_NAME=compass-demo \
DATABASE_MODE=ha \
./scripts/deploy_satsyil.sh
```

This is a local named-IAM deployment path, not the GitHub OIDC deployment. The
script removes ambient credential overrides, passes the literal profile to
every AWS and SAM operation, and fails unless STS resolves to the expected
account. It also verifies Docker and, for a fresh stack, available VPC and
Elastic IP quota. It stages migrations, runs SAM lint, builds Linux ARM
packages in a container, deploys the stack, migrates the database, builds the
authenticated frontend, publishes it, and waits for the CloudFront
invalidation. A fresh stack uses two passes to bind its generated CloudFront
domain to the exact Cognito callback and origin values. An existing stack uses
one pass with its current output, and any ambiguous stack lookup or non-updateable
stack state stops before deployment.

The default Scale Run controls are:

| Control | Default |
|---|---:|
| Maximum records | 1,000,000 |
| Worker concurrency | 4 |
| Export concurrency | 2 |
| Deployment hard cost cap | $10.00 |
| Scale data retention | 7 days |
| Scale evidence retention | 30 days |
| Athena per-query scan cutoff | 10 GiB |
| Governed synchronous export threshold | 5,000 rows |
| WAF rate limit | 2,000 requests per five minutes |

The entrypoint enables the Scale Run feature and activity ticker, while leaving
the optional account-level security baseline disabled. Review those choices,
the `ha` or `demo` selection, and the [production architecture](PRODUCTION_ARCHITECTURE.md)
before deployment.

### 15.3 Exercise the live data plane with direct IAM

Start with `10k` for a bounded acceptance run:

```bash
python3 scripts/run_scale_acceptance.py \
  --stack compass-demo \
  --aws-profile satsyil \
  --region us-east-1 \
  --workload 10k \
  --receipt artifacts/scale/10k-acceptance.json
```

The runner discovers the deployed Scale Control function from stack outputs,
creates a Scale Plan, launches one Scale Run, polls the durable Serving
Projection, requests a Parquet Export Job, and requires both a completed run
and ready export. Its defaults are seed `20260811`, a 3,600-second run timeout,
a 900-second export timeout, and five-second polling.

This acceptance transport invokes the Scale Control Lambda directly through
AWS IAM with a constructed API Gateway v2 event and corporate poweruser claims.
It exercises the same route handler and live SQS, Lambda, S3, DynamoDB, Step
Functions, Glue, Athena, and export flow, but it bypasses API Gateway network
transport, Cognito and TOTP, and WAF. The saved
`compass.scale-acceptance.v1` receipt declares
`transport=iam_direct_lambda_http_event` and sets the export `download_url` to
null. Never present it as end-to-end browser authentication proof. Verify the
interactive Cognito and TOTP path separately.

The `1m` Workload Profile has two prerequisites: `ScaleMaxRecords` must be at
least 1,000,000 and a successful `100k` proof receipt must remain in DynamoDB.
Run the profiles in this order:

```bash
python3 scripts/run_scale_acceptance.py \
  --stack compass-demo --aws-profile satsyil --region us-east-1 \
  --workload 100k --receipt artifacts/scale/100k-acceptance.json

python3 scripts/run_scale_acceptance.py \
  --stack compass-demo --aws-profile satsyil --region us-east-1 \
  --workload 1m --receipt artifacts/scale/1m-acceptance.json
```

Do not bypass the `100k` proof gate, widen the one-active-run limit, or increase
worker concurrency to make a rehearsal finish faster.

The 2026-08-11 Satsyil acceptance matrix completed in the required order and
is preserved under `artifacts/scale/`:

| Profile | Partitions | Duration | Quality | Passed | Quarantined | Anomalies | Export rows | Planned | Accrued estimate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1K | 6 | 21.351 s | 98.90 | 989 | 11 | 143 | 989 | $0.01898818 | $0.01227206 |
| 10K | 6 | 20.329 s | 98.91 | 9,891 | 109 | 1,403 | 9,891 | $0.01915314 | $0.01232190 |
| 100K | 11 | 25.853 s | 98.92 | 98,921 | 1,079 | 13,727 | 98,921 | $0.03380464 | $0.01785423 |
| 1M | 41 | 72.615 s | 98.98 | 989,852 | 10,148 | 137,852 | 989,852 | $0.13937136 | $0.05309299 |

The planned total was $0.21131732 and the accrued model estimate was
$0.09554118. The 1M Intelligence Receipt analyzed all 200,000 grant records.
These are modeled cost values, not billed cost.

### 15.4 Rehearse the Scale Lab evaluator tour

After direct-IAM acceptance and separate Cognito verification, use a corporate
poweruser session at `/admin/scale/`:

1. Confirm the page is labeled Scale Lab and its source is Live, not the
   Rehearsal Adapter.
2. Show the fixed `1k`, `10k`, `100k`, and `1m` Workload Profiles. Explain that
   the profile number is the total physical record count across all datasets.
3. Select `10k` and preview the Scale Plan. Verify the exact mix: 2,000 grants,
   3,000 finance records, 2,000 milestones, 1,000 documents, 200 licenses, and
   1,800 stream events.
4. Point to the deterministic seed, six partitions, bounded concurrency,
   official price snapshot, Cost Estimate with 25% contingency, and enforced
   upper bound before launch.
5. Explain that the 15-minute actor-bound plan can be consumed once. The Run
   Gate denies stale prices, an expired or reused plan, an active run, an
   over-limit profile, an estimate above either cap, or a missing `100k` proof
   for `1m`.
6. Launch once. Follow Standard Step Functions dispatch through SQS, bounded
   Lambda workers, S3 landing and governed zones, DynamoDB Partition Receipts,
   six Glue tables, bounded Athena conversion, and terminal finalization.
7. Use the interactive progress, quality, intelligence, performance, cost,
   recovery, and evidence panels. State observed performance only when a
   completed Performance Receipt supplies it.
8. On completion, verify the Run Manifest and Partition, Quality,
   Intelligence, Performance, and Cost Receipts. Confirm generated records
   reconcile to curated plus quarantined records and checksums are present.
9. Keep the completed run selected and open Decision Brief. Confirm the active
   evidence label names the selected Scale Run, the total matches the run
   profile, and the grant count matches 20 percent of that total. The 1M run
   must show 1,000,000 synthetic records and 200,000 grants, with no curated
   400-grant summary or `Failed to fetch` result.
10. Select `Use curated baseline`. Confirm the 400-grant record-level workspace
    returns and the Scale decision context disappears. Reopen the completed
    Scale Run if the Scale context should remain staged.
11. Request the governed Parquet Export Job. Wait for a ready receipt, then
   verify exact rows, bytes, format, checksum, expiry, and audit evidence.
12. Confirm browser receipt fields show only logical `lake://scale-runs/...`
    and `run://...` locators. Stop if the UI renders a bucket name, S3 key, ARN,
    queue URL, table name, workflow execution ID, or other physical identifier.

These checks passed in the Satsyil target environment on 2026-08-11. Before a
recording, confirm that the current deployment still matches the preserved
receipts and rerun the interactive browser checks. Describe the result as a
measured bounded synthetic Scale Run, not an ATO, Exhibit B certification,
unlimited-load result, sustained-concurrency result, multi-terabyte test, or
Government-data result.

## 16. Teardown

Archive required recording evidence before teardown. Empty versioned buckets,
disable database deletion protection if `ha` was used through an approved
stack change, then run `sam delete --stack-name compass-demo`.

The KMS key enters its configured pending-deletion window. Confirm no shared or
Government data was placed in the demonstration account before deleting the
stack.
