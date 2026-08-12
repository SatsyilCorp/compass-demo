# Compass candidate verification report

**Report date:** 2026-08-12
**Purpose:** evaluator orientation and recording release gate

This report distinguishes deployed resources from accepted execution evidence.
The current Satsyil stack is deployed with 35 protected
operations, 19 Lambda functions, 13 alarms, 2 dashboards, and 3 state machines.
The HA stack, identity preparation, fixed baseline, four Scale Runs, governed
exports, interactive browser path, document success and quarantine paths,
model training, Champion promotion, and drift evaluation have accepted live
receipts. The authentic public SBIR candidate completed a 109-second SageMaker
training job and entered Model Registry as `PendingManualApproval`. No endpoint
was created. The working tree is
not yet an exact committed revision
with GitHub workflow evidence. The candidate is not the recording release until
the applicable evidence and one timed human rehearsal pass exist.

## 1. Current implementation by source inspection

| Area | Current evidence |
|---|---|
| API | 33 JWT-protected method-and-path operations across 31 URL paths, including eight Scale operations, eight document MLOps operations, the reviewer inbox, and `GET /system/evidence` |
| Identity | Shared Cognito group normalization for native JWT and request-authorizer events; verified groups override forwarded roles and conflicting organizations fail closed |
| CORS | Exact-origin allowlist in API Gateway and shared Lambda response helpers |
| Database security | FORCE RLS, non-owner runtime role, corporate GUC gate, explicit runtime grants, and append-only audit trigger |
| Export approval | Exact `exp-` fingerprint, separate-persona decision, opaque token with stored SHA-256 verifier, expiration, row lock, and one-time consumption |
| Backend visibility | Poweruser-only System Inspector with sanitized application projections and explicit live or replay mode |
| Delivery | Pull-request quality workflow and manually dispatched protected-environment deployment through AWS OIDC |
| Demo preparation | Explicitly confirmed, synthetic-only bounded reset and seed; fixed non-triggering staged fixtures; real baseline analytics; redacted readiness receipt; one-shot live drop release |
| Scale data plane | Deterministic six-domain generator, maximum 25,000 records per partition, one-active-run gate, Standard workflow, SQS and DLQ, DynamoDB ledger, governed lake zones, Glue, Athena, and asynchronous Parquet export |
| Observability | 14-day API, workflow, and centralized application log groups, function-specific streams, X-Ray, 13 deployed alarms, and 2 CloudWatch dashboards |
| Database resilience | Source supports demo and HA modes; the accepted Satsyil live revision uses one private encrypted writer and one reader, 14-day backups, and deletion protection |
| Frontend | Responsive mission shell, mobile drawer, server-backed scoped dashboard filters, tab-scoped evidence selection, Scale receipt Decision Brief, presenter rehearsal guide, accessible interactions, interactive Scale Lab, and static deployment |
| Replay | One persistent deterministic scenario shared by ingest, catalog, lineage, analytics, dashboard, approvals, export, stream, and evidence |
| Lineage | Query-based `/catalog/lineage/?batch=<id>` route supports batches created after static frontend build |
| Activity ticker | Ordered database projection is authoritative; recent Kinesis receipts merge by stable ID; missing transport organization scope is corporate-only |
| Application compute | 18 deployed Lambda functions behind the narrow API, workflow, queue, and data adapters |
| Document intelligence and MLOps | Deployed eight-operation document and model contract with a bounded Step Functions workflow, Lambda classifier, optional SageMaker submission seam, accepted success and quarantine runs, 1.0 accuracy and macro F1 training evidence, exact-version Champion promotion, and shifted-data drift evidence |

## 2. Required automated gate

`.github/workflows/quality.yml` is the release authority for source checks. It
runs these categories from a clean checkout:

| Gate | Failure meaning |
|---|---|
| Repository content policy | A tracked or untracked source file contains the prohibited U+2014 code point |
| Python lint | Backend or operator code fails the configured static rules |
| Production dependency audits | A Python or frontend runtime dependency fails the configured audit |
| Offline tests | Identity, CORS, database contract, analytics, evidence, export, or other function tests fail |
| Migration synchronization | Packaged migrator SQL differs from root source SQL |
| SAM validation and build | Infrastructure is invalid or deployable artifacts cannot be produced |
| Frontend typecheck | Live or replay contracts do not satisfy TypeScript |
| Replay invariants | Cross-screen deterministic state or quarantine behavior is inconsistent |
| Static frontend build | The deployable site cannot be exported |
| Responsive browser smoke | Core routes, mobile navigation, or accessibility checks fail |

The recording tag must point to a commit whose quality workflow is green. A
local pass is useful but does not replace the clean-checkout workflow record.

## 3. Controlled deployment gate

`.github/workflows/deploy.yml` is manually dispatched into the protected demo
environment. The reviewed workflow:

1. obtains short-lived AWS credentials through OIDC
2. stamps the short source revision
3. validates the protected export-threshold and database-resilience values
4. stages migrations and container-builds backend artifacts
5. sends the additive source migrations to the deployed migrator before code
   on an existing stack
6. derives the CloudFront origin and Cognito `/login/` values from stack
   outputs, using an automatic two-phase deployment for a fresh stack
7. deploys the SAM stack with those reviewed policy values
8. invokes the newly bundled migrations with `{"migrate":"all"}`
9. requires `ok` and a `granted` runtime-role bootstrap from both applicable
   migration passes
10. builds the frontend with live identity and API values
11. publishes static output and invalidates CloudFront
12. checks the expected public security headers and confirms the UI is
    reachable
13. checks that unauthenticated `GET /system/evidence` returns 401

The GitHub environment configuration and AWS OIDC trust policy are external
deployment controls. Verify required reviewers, allowed branches, role trust,
and environment values before the recording release.

## 4. Contract reconciliation

The following previously risky seams are now represented in the candidate:

- Every handler uses a shared identity contract that derives the two personas
  from Cognito groups.
- A forwarded role or organization cannot override the verified group mapping.
- CORS no longer uses a wildcard Lambda response.
- The runtime database role no longer has broad write access to every table.
- Corporate funding access requires both the corporate view and corporate
  transaction context.
- `audit_log` has no runtime mutation path and has a trigger backstop.
- Export approval cannot be unbound, reused after expiry, or spent twice.
- Backend evidence is no longer a build-time architecture snapshot only.
- Replay data no longer fabricates independent contradictory state on each
  page.
- A live batch lineage page no longer depends on static route generation.
- CI and controlled deployment are executable repository workflows, not a
  narrated future state.

## 5. Live acceptance evidence

The following checks passed against the current Satsyil HA deployment on
2026-08-11:

| Observed check | Result |
|---|---|
| Stack | Deployment completed with 18 functions, 13 alarms, 2 dashboards, and 3 workflows |
| Database | Private encrypted Aurora writer and reader available, 14-day backups configured, deletion protection enabled, all four migrations applied, and runtime-role bootstrap granted |
| Identity | Poweruser, reviewer, and viewer accounts enabled for password-only team access; a separate presenter identity is enrolled with TOTP |
| Preparation | Redacted receipt reported ready with all 19 of 19 checks passing |
| API contract | OpenAPI described 33 protected operations across 31 URL paths; unauthenticated protected requests returned 401 |
| Browser | Real password-only poweruser login loaded the current dashboard with 480 grants across eight program areas and no `Failed to fetch` or console errors; the MLOps screen trained, promoted, and evaluated the exact live model version |
| Document intelligence | One document reached `gold-published` with a `technical_report` classification at 0.999991 confidence; one failed extractable-content and produced a quarantine receipt |
| MLOps | Model `doc-nb-f828a29acd1e` reached 1.0 accuracy, 1.0 macro F1, and 6 of 6 classes; Champion promotion and shifted drift with PSI 11.51, 91 percent OOV, and `retrain-and-review` passed |
| Public protection | CSP, Permissions Policy, HSTS, and WAF were present on the live boundary |
| Scale data plane | 1K, 10K, 100K, and 1M runs completed, reconciled, and produced ready governed Parquet exports |
| Local automation | 229 backend tests, 42 frontend scenarios, lint, typecheck, a 31-page production build, SAM validation, git whitespace checks, and the repository no-em-dash policy passed |

The direct acceptance path invoked the deployed Scale Control Lambda through
AWS IAM with a staged `/prod` event. It exercised the production route handler
and live SQS, Lambda, S3, DynamoDB, Step Functions, Glue, Athena, and export
flow. It bypassed Cognito, API Gateway transport, WAF, and the browser. Those
interfaces were verified separately through the real Cognito browser pass and
the 25-operation CORS check.

| Profile | Partitions | Duration | Quality | Passed | Quarantined | Anomalies | Export rows | Planned | Accrued estimate |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 1K | 6 | 21.351 s | 98.90 | 989 | 11 | 143 | 989 | $0.01898818 | $0.01227206 |
| 10K | 6 | 20.329 s | 98.91 | 9,891 | 109 | 1,403 | 9,891 | $0.01915314 | $0.01232190 |
| 100K | 11 | 25.853 s | 98.92 | 98,921 | 1,079 | 13,727 | 98,921 | $0.03380464 | $0.01785423 |
| 1M | 41 | 72.615 s | 98.98 | 989,852 | 10,148 | 137,852 | 989,852 | $0.13937136 | $0.05309299 |

The 1M run analyzed the full 200,000-record grant corpus. Planned incremental
cost totaled $0.21131732 and accrued model estimates totaled $0.09554118.
These values are estimates, not observed billing.

The technical acceptance matrix is complete. Recording release still requires
an exact committed revision with successful quality and deployment workflow
records and a continuous human rehearsal between 38 and 40 minutes.

## 6. Strategic prompt truth table

| Prompt | Demonstrated capability | Explicit boundary |
|---|---|---|
| Legacy sustainment | Compatible renamed schema adapter, canonical contract, and quarantine for incompatible input | This demonstrates an incremental adapter pattern, not migration of an actual legacy system |
| Financial integration | Governed award obligations, fiscal-year and program trends, anomalies, and a computed even-spend baseline | No appropriation, PB, or authoritative budget-authority feed is loaded |
| Zero Trust and IL4 or IL5 | MFA, JWT, RLS, CLS, private subnets, KMS, WAF, audit, Bedrock boundary, and generated RMF candidates | Commercial demo with equivalent controls; no ATO or IL4 or IL5 accreditation |
| Disaster recovery | Source-reproducible stack plus deployed HA mode with one reader, 14-day backups, and deletion protection | No cross-region DR and no tested production RTO or RPO |
| Vendor and lifecycle management | License register, entitlements, utilization, dataset names, and renewal urgency | Renewal timing is browser-computed; no scheduled notification job and no relational dataset foreign keys |

## 7. Scale posture

Exhibit B provides target baselines of 500 to 1,000 total users, 200 to 300
power users, 10 to 20 sources, 1 to 20 TB managed data, at least 1 TB of annual
growth, daily incremental and full refresh patterns, modular parameterized
infrastructure-as-code pipelines, and 50 to 75 Tier 1 and Tier 2 tickets per
month. QASP targets include 99 percent uptime during core hours and 95 percent
ticket service-level attainment, with cloud-log inspection, FinOps, and
Responsible AI review. See `docs/OPPORTUNITY_REQUIREMENTS_BOUNDARY.md`.

The demonstration now includes bounded measured evidence through 1,000,000
synthetic records, 41 partitions, a ready 989,852-row Parquet export, and
full-corpus deterministic intelligence over 200,000 grants. Aurora Serverless
scaling, stateless Lambda handlers, event-driven intake, on-demand Kinesis,
static web delivery, and replaceable adapters also provide design evidence.

This is not evidence for the Exhibit B total-user or power-user ranges,
sustained load, unlimited load, 1 to 20 TB, annual growth, daily refresh service
levels, monthly ticket volume, Government data, QASP attainment, or an
accredited environment. Those claims require separate tests and operational
records in the target landing zone.

## 8. Recording constraints

- The target run is 39:15 and must remain below 50:00.
- The seven scenario elements appear in required order.
- All five strategic prompts are explicitly named and indexed.
- The primary proof uses the live service.
- Replay is identified as a separate evaluator and rehearsal mode.
- The video is one continuous take.
- The screen shows the live application, terminal, and repository only.
- Presenter Guide is closed before recording.
- No slides, marketing overlays, post-production edits, or generated claims
  are added to the video.
- Key Personnel lead and narrate the technical content.

## 9. External inputs still required

The implementation must not invent these values:

- recording date and final runtime
- actual timestamps
- presenter names and exact proposed positions
- video URL and password
- repository URL and access method
- recording tag and full commit SHA
- offeror legal-name confirmation
- evaluator access duration and support contact
- GitHub environment and OIDC deployment configuration
- Bedrock model-access confirmation for the final recording path
- actual database instance placement before any AZ-specific narration
- exact-commit controlled deployment and quality workflow records
- final timed human rehearsal result

The files under `volume_iv/` label each of these as `EXTERNAL INPUT`.

## 10. Release decision

Release the candidate for recording only when all conditions are true:

1. Quality workflow is green on the exact commit.
2. Controlled deployment is green on the exact commit.
3. All four migrations are present in the deployed database. Verified on 2026-08-11.
4. The bounded preparation receipt says ready for the exact fixture revision. Passed 19 of 19 checks on 2026-08-11.
5. The complete technical live acceptance matrix passes. Passed in Satsyil on 2026-08-11.
6. A continuous rehearsal finishes between 38 and 40 minutes.
7. No narration claim exceeds the boundaries in this report.
8. Volume IV access values have owners and completion dates.

Until then, the correct status is live acceptance candidate, not final
recording release. `recording_release` remains false.
