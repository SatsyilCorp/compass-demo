# Compass interface contracts

This document is the cross-component contract for the demonstration. The
source of truth remains the implementation in `template.yaml`,
`db/migrations/`, `src/`, and `frontend/lib/types.ts`.

## 1. Domain and data boundary

Compass is an S&T Portfolio Intelligence platform. A synthetic research grant
moves from raw landing through normalization, quality control, curation,
catalog and lineage, analytics, decision support, and governed release.

All seed and replay records are synthetic. The strings `CUI-Mock` and
`Public-Mock` are demonstration labels, not real security markings. The
separate public-intelligence interface reads PII-minimized public records from
a checksummed S3 evidence index. It never merges those records into the
synthetic portfolio or accepts CUI.

## 2. Database contract

The PostgreSQL schema is `compass`. Versioned migrations are applied in order.

| Migration | Contract |
|---|---|
| `001_schema.sql` | Tables, pgvector extension, indexes, and base schema |
| `002_rls.sql` | `compass_app` runtime role, FORCE RLS policy, corporate view, and initial grants |
| `003_security_hardening.sql` | Explicit grants, corporate GUC gate, append-only audit, expiry, and one-time consumption fields |
| `004_opaque_approval_capability.sql` | Additive SHA-256 capability verifier column and its exact runtime update grant |

Core relations:

- `grants_raw(id, source_file, ingested_at, raw_jsonb, batch_id)`
- `grants_curated(id, grant_no, title, abstract, program_area, fiscal_year,
  amount_usd, awardee, org_unit, classification_band, created_at, batch_id)`
- `grant_quality(batch_id, rule, passed_rows, failed_rows, score,
  details_jsonb, run_id, created_at)`
- `lineage_nodes(run_id, node_id, kind, label, meta_jsonb)`
- `lineage_edges(run_id, from_node, to_node)`
- `topics`, `grant_topics`, and `model_runs`
- `anomalies` and `approvals`
- `licenses`
- `audit_log`
- `_schema_migrations`

### Runtime database identity

- The migrator owns the schema.
- Application functions connect as the non-owner `compass_app` role.
- Each request binds `SET LOCAL compass.org_unit` inside its transaction.
- `grants_curated` has RLS enabled and forced.
- `ONR-Corporate` receives the corporate row branch. `Code-30` receives only
  Code-30 rows.
- The base relation does not grant `amount_usd` to the shared runtime role.
- The corporate view includes an explicit `ONR-Corporate` GUC gate before it
  can expose funding values.
- Runtime access to `audit_log` is read plus insert. A database trigger rejects
  update and delete attempts.

## 3. Identity and HTTP contract

All 48 method-and-path operations across 45 URL paths use the Cognito JWT
authorizer by default when the Scale Run feature is enabled. No application
operation is intentionally public. The eight Scale Run operations also require
the corporate poweruser persona.

`compass_common.http.get_claims()` normalizes both API Gateway native JWT
events and the optional request-authorizer context. It derives role and
organization from `cognito:groups`. A token with no recognized Compass group
is denied. A forwarded role cannot override a recognized group, and a supplied
organization that conflicts with the resolved role is denied.

| Cognito group | Role | Organization scope |
|---|---|---|
| `compass-poweruser` | `poweruser` | `ONR-Corporate` |
| `compass-viewer` | `viewer` | `Code-30` |

CORS is allowlisted. The backend only reflects an `Origin` that appears in
`CORS_ALLOW_ORIGINS`; API Gateway uses the same configured web origin plus the
local development origin. There is no wildcard origin response.

`GET /stream/recent` treats the database's ordered recent activity projection
as authoritative. Recent Kinesis transport receipts are merged by stable event
identifier when available. A Kinesis receipt without organization scope is
visible only to the corporate poweruser; it is not disclosed to the scoped
viewer.

## 4. Protected API routes

| # | Method | Route | Purpose | Primary element |
|---:|---|---|---|---:|
| 1 | GET | `/me` | Resolved identity, role, groups, and organization | 1 |
| 2 | GET | `/catalog` | Governed datasets, metadata, and quality score | 4 |
| 3 | GET | `/catalog/{id}/lineage` | Nodes and edges emitted for a batch run | 4 |
| 4 | POST | `/ingest/simulate` | Poweruser trigger for a sanitized drop | 3 |
| 5 | GET | `/ingest/status` | Batch, rule, quality, and disposition status | 3 |
| 6 | GET | `/stream/recent` | Ordered governed activity projection with merged recent Kinesis transport receipts | 3 |
| 6a | GET | `/demo-stream` | Current operator-controlled continuous stream session and latest receipt | 3 |
| 6b | POST | `/demo-stream/start` | Start synthetic S3 drops every one or two seconds until Stop | 3 |
| 6c | POST | `/demo-stream/stop` | Stop the current continuous synthetic stream | 3 |
| 7 | POST | `/analytics/run` | Execute a governed topic-model run | 5 |
| 8 | GET | `/analytics/{run_id}` | Topics, trends, metrics, and recommendation | 5 |
| 9 | GET | `/dashboard` | Persona-scoped KPIs and chart series | 6 |
| 10 | POST | `/chat` | Bedrock RAG answer over RLS-scoped retrieval | 6 |
| 11 | GET | `/anomalies` | Scoped findings queue | 6 |
| 12 | GET | `/approvals` | Scoped pending reviewer inbox without capability tokens | 6 and 7 |
| 13 | POST | `/approvals` | Request or decide a governed approval | 6 and 7 |
| 14 | GET | `/licenses` | License and entitlement register | 6 |
| 15 | POST | `/export` | RLS and CLS governed export with aggregation guard | 7 |
| 16 | GET | `/openapi.json` | Served OpenAPI 3.1 contract | 7 |
| 17 | GET | `/system/evidence` | Poweruser-only sanitized runtime projection | 2 and cross-cutting |
| 18 | GET | `/scale/profiles` | List fixed Workload Profiles and capacity state | Cross-cutting |
| 19 | POST | `/scale/plans` | Create an actor-bound, price-backed Scale Plan | Cross-cutting |
| 20 | GET | `/scale/runs` | List durable Scale Run Serving Projections | Cross-cutting |
| 21 | POST | `/scale/runs` | Consume one Scale Plan and launch one Scale Run | Cross-cutting |
| 22 | GET | `/scale/runs/{run_id}` | Read progress, receipts, cost, and terminal state | Cross-cutting |
| 23 | POST | `/scale/runs/{run_id}/cancel` | Request cooperative, durable cancellation | Cross-cutting |
| 24 | POST | `/scale/runs/{run_id}/exports` | Request an asynchronous governed Parquet Export Job | 7 and cross-cutting |
| 25 | GET | `/scale/runs/{run_id}/exports/{export_id}` | Read an Export Job receipt and readiness state | 7 and cross-cutting |
| 26 | POST | `/documents/uploads` | Request a bounded browser upload for an unstructured or semi-structured document | 3 and 5 |
| 27 | GET | `/documents/runs` | List document inspect, quality, curate, or quarantine receipts | 3 and 5 |
| 28 | GET | `/documents/runs/{run_id}` | Read one document run and logical lineage | 3 and 5 |
| 29 | POST | `/ml/train` | Train and evaluate the shared six-class document classifier | 5 |
| 30 | GET | `/ml/models` | List model versions and champion state | 5 |
| 31 | POST | `/ml/models/{version}/deploy` | Promote an approved model version to champion | 5 |
| 32 | POST | `/ml/drift/evaluate` | Produce label-distribution and vocabulary-drift evidence | 5 |
| 33 | GET | `/ml/ops/evidence` | Read sanitized training, registry, deployment, and drift evidence | 5 and cross-cutting |
| 34 | GET | `/public-intelligence/snapshot` | Read a versioned, checksummed public-evidence snapshot | 5 and cross-cutting |
| 35 | POST | `/public-intelligence/explain` | Produce a bounded cited explanation or an explicit evidence refusal | 5 and 6 |
| 36 | GET | `/public-intelligence/model-executions` | Read the newest durable, governed public-model execution receipts | 5 and cross-cutting |
| 37 | POST | `/public-intelligence/model-executions` | Start one bounded public SBIR candidate Batch Transform run | 5 |
| 38 | GET | `/public-intelligence/model-executions/{executionId}` | Reconcile one Batch Transform run to its terminal receipt | 5 and cross-cutting |
| 39 | GET | `/public-intelligence/acquisitions` | List scheduled USAspending acquisition watermarks and change receipts | 3, 4, and cross-cutting |
| 40 | POST | `/public-intelligence/acquisitions/run` | Start one bounded public-source micro-batch poll | 3 and cross-cutting |
| 41 | GET | `/operations/signals` | Read safe in-app and SNS delivery evidence for operational events | Cross-cutting |
| 42 | POST | `/operations/signals/{eventId}/acknowledge` | Record a poweruser acknowledgement without deleting the signal | Cross-cutting |
| 43 | GET | `/operations/lineage` | List recent cross-workflow run projections | 3, 4, 5, and cross-cutting |
| 44 | GET | `/operations/lineage/{runId}` | Read ordered stage receipts, hashes, model, and consumer for one run | 3, 4, 5, and cross-cutting |
| 45 | GET | `/operations/summary` | Read the current operational scorecard and public-source watermark | Cross-cutting |

The live operations list, lineage, and summary responses declare
`evidence_scope=public-only`. The service excludes synthetic, mixed, and
unclassified receipts before calculating counts. Synthetic operational
receipts are available only through the explicitly selected rehearsal adapter.

The document upload request accepts either `synthetic-demo` input or a
PII-minimized `public` document. A public upload must explicitly declare
`contains_cui=false` and `pii_minimized=true`; any other classification is
rejected before a presigned upload is issued. Every request must also declare
the browser-computed `source_sha256`; server inspection recomputes the digest
from the retrieved object and quarantines a mismatch. This is an admission assertion,
not automated content accreditation, so quality and sensitive-pattern checks
still run after landing.

### Public intelligence contract

The public-intelligence Lambda is isolated from the synthetic portfolio
database. It reads only `public-intelligence/*` in the configured KMS-encrypted
data bucket. The current manifest points to an immutable index under
`public-intelligence/snapshots/<snapshot-id>/` and carries the exact index
SHA-256 digest. The read fails closed unless the manifest declares public
classification, no CUI, PII minimization, a supported version, and one HTTPS
source URL per record.

`POST /public-intelligence/explain` accepts a question of at most 1,200
characters, up to 12 explicit record identifiers, and a retrieval limit of no
more than six. Retrieval uses only the verified local evidence index. The
handler makes at most one Bedrock request with a fixed 500-token output cap.
Every citation includes the record identifier, source URL, evidence class,
snapshot, record digest, model run identifier when one exists, and reported
uncertainty. No supporting record produces
`INSUFFICIENT_CITABLE_EVIDENCE` without calling a model. A Bedrock outage
returns a conservative deterministic answer with the same citations.

The model-execution interface uses one exact registered public SBIR candidate
without approving or deploying it. A corporate poweruser can submit 1 to 25
PII-minimized, label-excluded public Navy Phase I records that occur after the
model evaluation cutoff. Compass
verifies the package ARN, training job, source object version, registry bundle
digest, model-card digest, image digest, and versioned, write-once per-run model copy before starting one
network-isolated `ml.m5.large` Batch Transform job. It caps concurrency at one,
enforces the 1,800-second runtime limit through a per-run EventBridge Scheduler
cleanup guard, requires finite probabilities from zero through one, binary
labels, nonempty semantics, and a mandatory human-review flag, and deletes the
temporary SageMaker Model after terminal reconciliation. The receipt records package,
training, candidate-pool, input, output, object-version, and receipt digests,
per-record probabilities, review flags, observed duration, and an estimate-only
compute cost. No endpoint or automatic promotion is created.

### Scale Run contract

The Scale Adapter accepts only a fixed Workload Profile and deterministic
seed. It never accepts a caller-selected raw record count, partition size,
concurrency, retention, model-spend limit, or cost ceiling.

| Workload Profile | Total physical records | Default partition size | Exact partitions | Profile envelope |
|---|---:|---:|---:|---:|
| `1k` | 1,000 | 1,000 | 6 | $0.10 |
| `10k` | 10,000 | 5,000 | 6 | $0.25 |
| `100k` | 100,000 | 10,000 | 11 | $1.00 |
| `1m` | 1,000,000 | 25,000 | 41 | $10.00 |

Profile totals span exactly six linked synthetic datasets:

| Dataset | Mix | Records in `10k` |
|---|---:|---:|
| grants | 20% | 2,000 |
| finance | 30% | 3,000 |
| milestones | 20% | 2,000 |
| documents | 10% | 1,000 |
| licenses | 2% | 200 |
| stream events | 18% | 1,800 |

Every child record references a grant in the same profile. The Run Manifest
seals `synthetic_only=true`, generator version, seed, and fixed as-of time. A
deployed record ceiling of at least 1,000,000 and a retained successful `100k`
proof receipt are both prerequisites for `1m`.

`POST /scale/plans` returns a 15-minute, actor-bound Scale Plan with an exact
dataset allocation, partition ceiling, concurrency limit, and Cost Estimate.
The Run Gate fails closed when the feature is disabled, the profile exceeds
the deployed maximum, another run is active, a plan is expired, consumed, or
owned by another actor, the estimate exceeds the profile or deployment cap,
the `1m` prerequisite is absent, or price evidence is outside its freshness
boundary. Price evidence comes from an AWS Price List Query API snapshot. Its
maximum age is 30 days, with a bounded one-day tolerance for clock skew. The
Cost Estimate includes a 25% contingency.

`POST /scale/runs` requires the plan identifier and an idempotency key of 12 to
128 characters. One transactional Run Gate decision consumes the plan and
acquires the one-active-run lock. Retrying the same accepted command resolves
to the same operation. Partition retries are idempotent, cancellation is
cooperative and durable, and a run identifier is never used as a
high-cardinality metric dimension.

The Standard Step Functions workflow carries only `run_id`. It dispatches work
through SQS, bounded Lambda workers generate deterministic partitions, and S3
holds compressed landing, curated, quarantine, Parquet, and evidence objects.
DynamoDB is the durable run and partition ledger. Glue catalogs six datasets,
and an Athena workgroup with a 10 GiB per-query scan cutoff converts and
analyzes the full run. Aurora retains the broader identity, approval, audit,
and Serving Projection boundary.

A terminal run exposes a Run Manifest and Partition, Quality, Intelligence,
Performance, and Cost Receipts. Generated records reconcile to curated plus
quarantined records unless an explicit batch-held condition is recorded. Every
part and terminal receipt carries a SHA-256 checksum. Intelligence declares
full-corpus or sampled coverage. Performance values are observed, while costs
are labeled estimated, metered, or billed reconciliation pending.

An Export Job is asynchronous and allowed only for a completed Scale Run. Its
terminal receipt identifies exact row count, byte count, Parquet format,
SHA-256 checksum, expiry, and audit evidence. Browser-facing receipt fields use
logical `lake://scale-runs/...` and `run://...` locators. They do not contain
bucket names, S3 keys, ARNs, queue URLs, table names, workflow execution IDs,
or other physical infrastructure identifiers. A ready job may return a
short-lived download action, but the UI does not render its physical target as
receipt evidence.

`scripts/run_scale_acceptance.py` is a direct-IAM acceptance adapter. It
invokes the deployed Scale Control Lambda with a constructed API Gateway v2
event and corporate poweruser claims, so it exercises the same route handler
and live data plane. It bypasses API Gateway transport, Cognito and TOTP, WAF,
and the browser network path. Its receipt declares
`transport=iam_direct_lambda_http_event` and removes the export download URL.
It must not be presented as end-to-end browser authentication evidence.

### Dashboard filter contract

`GET /dashboard` accepts optional `program_area`, `fiscal_year`, `org_unit`,
and `q` query parameters. Unsupported keys and invalid values return 400. A
viewer cannot use `org_unit` to widen beyond the organization derived from the
verified identity. The backend binds every predicate as a SQL parameter inside
the same RLS transaction used for the dashboard aggregates.

The response returns `filters_applied` and `filter_options`. Options are
calculated before the requested predicates but after RLS is active, so the UI
can offer useful choices without disclosing values outside the caller's scope.

### Export approval contract

The export service counts every row matched by the normalized filters. A
client cannot bypass the aggregation threshold by lowering a page limit. When
the matched count exceeds `EXPORT_MAX_ROWS`, the service returns HTTP 428 with
a subject identifier derived from the exact organization, format, columns,
and filters.

An approval can clear the guard only when all conditions are true:

1. Its subject type is `export`.
2. Its subject identifier exactly matches the current `exp-` fingerprint.
3. Its state is approved.
4. A different authorized persona made the decision.
5. Its opaque secret matches the stored SHA-256 digest using constant-time comparison.
6. It has not expired.
7. It has not been consumed.

The export transaction locks and consumes the approval before release. A
second request cannot reuse it. Export and approval decisions append to
`audit_log`.

`GET /approvals` is the reviewer handoff. A poweruser sees the shared pending
queue; a viewer sees only requests made by that exact actor. The response never
contains capability tokens. The short-lived opaque one-time token is returned
only in the successful POST decision response to the independent reviewer,
then passed to the original requester for the exact retry. Its internal format
is not a public contract. The plaintext capability is never stored, listed,
put in a URL, or written to the audit record. Legacy predictable values fail
closed.

Export columns are a top-level `columns` array. The `filters` object contains
the whitelisted predicates and an optional materialization `limit`. The guard
always counts the full predicate match, so lowering `limit` cannot bypass the
threshold. The normalized limit is also part of the request fingerprint. The
requester must retry the unchanged format, columns, and filters with the token.

### System evidence contract

`GET /system/evidence` is read-only and restricted to the poweruser corporate
scope. It returns:

- `mode`, which is `live` for the service adapter
- evidence class, generation time, deploy revision, and correlation ID
- sanitized request status and latency
- the resolved policy decision
- portfolio counts
- recent workflow runs and a stage trace derived from quality and curated
  projections
- recent allowlisted audit fields
- latest model-run metadata
- service and control posture

It does not return infrastructure identifiers, credentials, bearer tokens,
raw claims, usernames, email addresses, IP addresses, SQL, prompts, abstracts,
raw source records, presigned URLs, exceptions, or stack traces.

## 5. Frontend contract

The static Next.js application uses these environment values:

- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_COGNITO_AUTHORITY`
- `NEXT_PUBLIC_COGNITO_DOMAIN`
- `NEXT_PUBLIC_COGNITO_CLIENT_ID`
- `NEXT_PUBLIC_COGNITO_REDIRECT_URI`
- `NEXT_PUBLIC_COGNITO_POST_LOGOUT_REDIRECT_URI`
- `NEXT_PUBLIC_AUTH_DISABLED`

Runtime evidence selection is not an environment switch. Live public evidence
is the fail-closed default, and a user must explicitly activate the persistent
Rehearsal mode before fixture-backed adapters can run.

Primary routes are `/login/`, `/dashboard/`, `/ingest/`, `/catalog/`,
`/catalog/lineage/?batch=<id>`, `/analytics/`, `/licenses/`, `/export/`, and
`/admin/pipeline/`. The corporate poweruser Scale Run Mission Workspace is
`/admin/scale/`.

The frontend shows an explicit live or replay label. Presenter Guide is an
in-product rehearsal aid opened from the shell. It is not part of the recorded
evidence run.

Authenticated pages share one tab-scoped Mission Evidence selection. It is
either the curated demo or a strictly validated Scale Run identifier. Opening,
launching, or deep-linking a Scale Run selects it. In Scale mode,
`/dashboard/` calls only the selected Scale Adapter receipt and renders an
aggregate Scale decision context. It does not call the curated dashboard or
invent row-level grants, citations, funding charts, filters, or disposition
queues from an aggregate receipt. Missing, active, failed, cancelled, and
completed receipts remain explicit. `Use curated baseline` returns the tab to
the record-level dashboard.

## 6. Deterministic replay contract

Replay mode stores a versioned scenario in browser storage. State-changing
portfolio adapters read and mutate that one state. A clean or compatible
legacy batch can curate rows; a defective batch always curates zero rows and
produces no downstream curated lineage. Analytics, dashboard, stream,
approvals, exports, and System Inspector replay evidence derive from the same
state and fixed logical clock. Reference-only fixtures such as licenses remain
static.

Replay actions are reproducible and resettable. They are labeled as replay and
must not be narrated as live AWS execution. The Rehearsal Adapter can validate
interaction design and deterministic state transitions, but it is not capacity
proof. Only the Scale Adapter can provide a live Scale Run receipt, and that
receipt is evidence only after the deployed path completes successfully.

## 7. AI contract

Model calls use `compass_common/llm.py` and Amazon Bedrock only:

- `amazon.nova-lite-v1:0` for chat and summaries
- `amazon.titan-embed-text-v2:0` for 1024-dimensional embeddings

RAG retrieval runs inside the caller's RLS transaction. The RMF artifact
generator does not use an LLM because its output must be deterministic.

## 8. Operator preparation contract

`scripts/prepare_demo.py` is an operator-only workflow. It is not an HTTP API
and the migrator actions it invokes are not exposed through API Gateway.

The workflow recognizes exactly five source-controlled fixtures:

- one 400-record baseline portfolio
- one eight-record license register
- clean, compatible legacy, and defective live demonstration drops

Every fixture must carry `fixture_contract=compass.synthetic.v1`,
`synthetic_only=true`, the fixed generator seed, its expected batch or license
identity, and its exact record count. Staged bytes must match their SHA-256
object metadata. Staging uses fixed `demo-stage/` keys with a non-ingestible
`.fixture` suffix, while EventBridge accepts only the separate `drops/`
prefix.

`prepare` requires the literal confirmation value
`RESET_FIXED_SYNTHETIC_DEMO_DATA`. Before any database deletion, the migrator
checks for curated grants outside the four allowlisted synthetic batch IDs and
refuses the entire transaction if one exists. The caller cannot select table
names, batch IDs, run IDs, license identities, approval actors, users, or
object keys. Append-only audit rows are not reset.

Preparation requires three enabled, confirmed, password-only team users plus
one enabled, confirmed, TOTP-enrolled formal presenter in their expected
Compass groups. It does not create identities, alter passwords, change groups,
or enroll MFA. It runs the real Analytics Lambda for the fixed
baseline through an IAM-protected direct action and finalizes only a topic-model
run attributed to service actor `compass-demo-preparer` over exactly 400
documents and eight topics.

The `compass.demo-preflight.v1` receipt contains logical fixture and landing
locators, hashes, counts, identity readiness, migration state, analytics
metrics, and pass or fail checks. It does not contain a physical bucket name.
`check` is read-only. The protected ingest API accepts only the fixed fixture
names `good`, `compatible`, and `bad`, validates bytes against the latest
immutable preparation hash receipt, and relies on EventBridge as the sole
workflow starter. `release-drop` provides the same fixed operator fallback and
refuses an existing target unless the operator explicitly supplies
`--allow-redrop`.
