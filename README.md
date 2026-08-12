# Compass: S&T Portfolio Intelligence

Compass is a working Navy and ONR styled demonstration platform for
N0001426R4002 Volume IV, Factor 3. It turns a synthetic research portfolio into
an evidence-backed workflow:

`Ingest -> Govern -> Discover -> Decide -> Release`

The repository contains one AWS SAM stack and a responsive Next.js application.
The live path uses Cognito, API Gateway, Lambda, Step Functions, SQS, Kinesis,
Aurora PostgreSQL, DynamoDB, S3, Glue, Athena, Bedrock, CloudFront, WAF, KMS,
CloudWatch, and GitHub Actions.
The deterministic replay path uses one persistent browser scenario so that an
ingest decision is reflected consistently across catalog, lineage, analytics,
dashboard, approval, export, and system evidence views.

## Current live boundary

The current Satsyil stack at `https://compass.aws.satsyil.com/` is deployed at
`public-intel-20260812-full`. It has 38 protected operations across 35 URL paths, 19 Lambda
functions, 13 alarms, 2 dashboards, and 3 state machines. The stack is in HA
mode, Scale is enabled through 1,000,000 records, and document MLOps uses the
bounded Lambda `demo` Adapter.

The earlier revision retains dated acceptance evidence for HA, ingestion,
governance, analytics, dashboard, export, document success and quarantine, and
all four Scale Run profiles. A public-intelligence path now serves 177,503
records across 12 source families through a 1,098-record bounded index. An
authentic 11,287-row public Navy SBIR transition model completed a
network-isolated SageMaker job and is registered as `PendingManualApproval`.
No SageMaker endpoint exists.

Scale and document seed data remain synthetic and contain no CUI or direct PII.
Public intelligence is a separate, provenance-bound public corpus with direct
PII minimized. See `seed/SYNTHETIC-DATA-MANIFEST.md` and
`docs/PUBLIC_ONR_INTELLIGENCE.md`.

## What evaluators can see

The seven required scenario elements are presented in sequence.

| # | Required element | Product proof |
|---|---|---|
| 1 | Secure access, MFA, and Zero Trust | Cognito optional TOTP for the formal presenter, JWT protection on all 38 current method-and-path operations across 35 URL paths, centralized group-to-role normalization, transaction-scoped RLS, and role-gated funding data |
| 2 | Infrastructure as Code and automation | `template.yaml`, forward SQL migrations, automated quality gates, controlled OIDC deployment, deploy revision evidence, and deterministic RMF artifact generation |
| 3 | Automated ingestion, DataOps, and streaming | S3 and EventBridge trigger an Express Step Functions workflow with normalization, quality scoring, curate or quarantine decisions, an ordered database activity projection, and deduplicated Kinesis transport receipts |
| 4 | Governance, quality, and cataloging | Explainable quality scores, a governed catalog, and run-emitted lineage at `/catalog/lineage/?batch=<id>` |
| 5 | Decision-support analytics | Deterministic TF-IDF plus NMF topic analysis, trend views, anomaly evidence, and a persisted recommendation |
| 6 | Unified dashboard and process automation | Persona-scoped KPIs, server-backed search and filters, decision views, Bedrock RAG, anomaly approval workflow, and license lifecycle register |
| 7 | Interoperability and secure export | CSV, JSON, and optional parquet export under RLS and CLS, exact-query aggregation approval, append-only audit, and a served OpenAPI 3.1 contract |

Two features provide unusually strong proof for this demonstration:

- The aggregation guard returns HTTP 428 for a bulk extraction, binds an
  approval to the exact query fingerprint, expires the approval, and consumes
  an opaque approval capability once in the authorized export transaction.
- The RMF generator reads the same SAM template that provisions the system and
  emits deterministic control evidence with a template hash and cited source
  properties.

## Product view, System view, and Scale Lab

The application has three complementary proof surfaces:

- Product view shows the mission workflow and decisions.
- System view at `/admin/pipeline/` shows a protected, read-only System
  Inspector. In live mode it polls `GET /system/evidence` every five seconds.
  The response includes deploy revision, request correlation, policy decision,
  recent application-projected workflow receipts, model-run evidence, and a
  sanitized audit projection. It deliberately excludes account identifiers,
  ARNs, bucket keys, database endpoints, secrets, tokens, claims, personal
  data, SQL, prompts,
  source records, and exception detail.
- Scale Lab at `/admin/scale/` is the corporate poweruser Mission Workspace for
  a bounded production Scale Run. It previews the Workload Profile, exact
  Scale Plan, Run Gate result, price-backed Cost Estimate, partition ceiling,
  six-dataset allocation, durable progress, receipts, and governed Export Job
  from one interactive evaluator surface.

Every System Inspector response says whether its source is `live` or `replay`.
Replay evidence is deterministic test data and is never presented as cloud
runtime proof.

## Run locally in deterministic replay mode

```bash
cd frontend
cp .env.example .env.local
pnpm install
pnpm dev
```

The default local settings enable replay data and disable external identity.
Use the persona switcher to compare the corporate and Code-30 scopes. Run a
clean, legacy, or defective intake from `/ingest/`; the durable browser scenario
will update the rest of the application. Use `Reset replay` to restore the
known baseline.

Replay is a rehearsal and evaluator quickstart. It is not evidence that the AWS
backend executed.

## Production Scale Run path

The optional Scale Adapter is separate from the browser Rehearsal Adapter. A
caller chooses only a fixed Workload Profile and deterministic seed. The
server creates a 15-minute Scale Plan and applies the Run Gate before any work
starts. Browser callers cannot supply raw record counts, partition size,
concurrency, retention, model spend, or the cost ceiling.

| Workload Profile | Total records | Default partition size | Exact partitions |
|---|---:|---:|---:|
| `1k` | 1,000 | 1,000 | 6 |
| `10k` | 10,000 | 5,000 | 6 |
| `100k` | 100,000 | 10,000 | 11 |
| `1m` | 1,000,000 | 25,000 | 41 |

Each profile total is distributed across six linked synthetic datasets, not
repeated for each dataset: grants 20%, finance 30%, milestones 20%, documents
10%, licenses 2%, and stream events 18%. The `1m` profile is available only
when the deployment allows at least 1,000,000 records and a successful `100k`
proof receipt remains in the Scale Run ledger.

After the Run Gate consumes one actor-bound plan, a Standard Step Functions
workflow coordinates SQS dispatch, bounded Lambda workers, compressed JSON
Lines in S3, DynamoDB state and Partition Receipts, Glue and Athena conversion
of all six datasets to Parquet, full-corpus Quality and Intelligence Receipts,
Performance and Cost Receipts, and an asynchronous governed Export Job. The
browser receives logical `lake://` and `run://` receipt locators, never bucket
names, object keys, ARNs, queue URLs, table names, or workflow execution IDs.

Launching, opening, or deep-linking a Scale Run makes that run the active
evidence set for the current browser tab. Opening Decision Brief then renders
an aggregate decision context from that exact Scale receipt, including corpus
size, grant count, quality, quarantine, anomaly, partition, throughput, and
modeled cost evidence. It does not mix those values with the fixed 400-grant
curated baseline. The explicit `Use curated baseline` action restores the
record-level dashboard. Other mission pages continue to use their curated
record-level adapters and show the active evidence label; they do not claim a
Scale-specific row view.

See `docs/PRODUCTION_ARCHITECTURE.md` for the production-shaped design and
`docs/COST_MODEL.md` for the pre-deployment cost model. Both documents are
planning evidence. They do not claim that a Scale Run has been deployed or
measured.

## Deploy the live stack

Prerequisites are AWS credentials for `us-east-1`, AWS CLI v2, AWS SAM CLI,
Docker, Python 3.12, Node 22, and pnpm. Bedrock model access must be enabled for
the two model IDs declared in `template.yaml`.

The preferred path is the controlled GitHub Actions deployment in
`.github/workflows/deploy.yml`. It assumes AWS credentials through OIDC,
applies compatible additive migrations before switching code on an existing
stack, deploys the reviewed revision, reruns the bundled migrations, builds the
live frontend, publishes it, and verifies the public and protected boundaries.
Both migration passes require a successful runtime-role bootstrap. The GitHub
environment, OIDC role, export threshold, and database mode are validated
deployment-time inputs. The workflow derives the CloudFront origin and Cognito
callback values from stack outputs. A fresh stack completes that binding with
an automatic second deployment pass. The recommended recording values are
`EXPORT_MAX_ROWS=250` and `DATABASE_RESILIENCE_MODE=demo`; `ha` is an
intentional higher-cost opt-in.

The complete manual path is in `docs/RUNBOOK.md`. Its core is:

```bash
cp samconfig.toml.template samconfig.toml
./src/functions/migrator/prepare_migrations.sh
sam validate --lint
sam build --use-container
sam deploy
```

The default `DatabaseResilienceMode=demo` provisions one writer, seven-day
backup retention, and no deletion protection so the demonstration can be torn
down cleanly. `DatabaseResilienceMode=ha` adds a cluster reader, changes backup
retention to 14 days, and enables deletion protection. Neither setting by
itself is a production disaster recovery implementation. See
`docs/ARCHITECTURE.md` and `docs/RUNBOOK.md` for the explicit production target.

After deployment, migrations, user creation, and identity verification, prepare the
fixed synthetic recording state with the bounded operator workflow:

```bash
python3 scripts/prepare_demo.py prepare \
  --stack compass-demo \
  --region us-east-1 \
  --confirm-synthetic-reset RESET_FIXED_SYNTHETIC_DEMO_DATA \
  --receipt artifacts/demo-preflight.json
```

The command refuses to delete anything when unexpected UI-driving state is
present. It stages five validated fixtures outside the live ingest prefix,
loads the baseline portfolio and license register, runs baseline analytics as
service actor `compass-demo-preparer`, verifies the four fixed identity paths,
confirms the live drop keys are absent, and writes a redacted readiness
receipt. The live Ingest page then exposes three protected, one-shot fixture
release controls. The complete safety boundary and read-only check command are
in `docs/RUNBOOK.md`.

## Delivery gates

`.github/workflows/quality.yml` runs the repository content policy, Python
lint, Python and frontend production dependency audits, backend contract tests,
migration synchronization check, SAM validation and build, frontend typecheck,
deterministic scenario tests, static build, and responsive accessibility smoke
tests. The content policy rejects the Unicode U+2014 code point throughout
tracked and untracked source files.

Run the same core checks locally before a recording:

```bash
python3 scripts/check_no_em_dash.py
ruff check src scripts
PYTHONPATH=src/common/python python3 -m pytest -q src/common/tests src/functions/*/tests
./src/functions/migrator/prepare_migrations.sh
git diff --exit-code -- db/migrations src/functions/migrator/migrations
sam validate --lint
cd frontend && pnpm typecheck && pnpm test:scenario && pnpm build && pnpm test:e2e
```

## Repository map

| Path | Purpose |
|---|---|
| `template.yaml` | Reproducible AWS environment, 38 protected API operations, document MLOps, optional Scale Run resources, observability, and resilience modes |
| `db/migrations/` | Versioned schema, RLS and CLS, explicit runtime grants, append-only audit, and opaque approval verifier storage |
| `src/common/` | Shared database, identity, HTTP, CORS, Bedrock, audit, deterministic workload, and price-backed cost contracts |
| `src/functions/` | Application handlers, System Inspector, Scale Control, Scale Worker, Scale Export, migrator, and RMF generator |
| `statemachines/` | Express intake and Standard Scale Run workflow definitions |
| `scripts/prepare_demo.py` | Bounded synthetic reset, baseline preparation, read-only preflight, and one-shot live drop release |
| `scripts/deploy_satsyil.sh` | Named-profile deployment path with Scale Run controls enabled |
| `scripts/run_scale_acceptance.py` | Direct-IAM Scale Adapter acceptance runner and sanitized receipt writer |
| `frontend/` | Responsive mission application with live, Scale, and deterministic Rehearsal Adapters |
| `.github/workflows/` | Quality gates and controlled OIDC deployment |
| `docs/` | Contracts, architecture, security, operations, verification, and recording script |
| `volume_iv/` | Submission link, presenter, timestamp, and repository access package |

## Documentation

| Document | Use |
|---|---|
| `docs/CONTRACTS.md` | Database, identity, API, replay, and evidence contracts |
| `docs/ARCHITECTURE.md` | Components, flows, element mapping, portability, and production deltas |
| `docs/PRODUCTION_ARCHITECTURE.md` | Scale Run planes, limits, receipts, lifecycle, and production boundary |
| `docs/COST_MODEL.md` | Price evidence, per-profile estimates, and demo versus HA fixed-cost comparison |
| `docs/SECURITY.md` | Enforced controls, System Inspector disclosure boundary, and honest limitations |
| `docs/RUNBOOK.md` | Deploy, migrate, seed, verify, rehearse, record, and tear down |
| `docs/BUILD_REPORT.md` | Current candidate evidence and release gates |
| `docs/OPPORTUNITY_REQUIREMENTS_BOUNDARY.md` | Authoritative workload targets, PWS mapping, and public or restricted data boundaries |
| `docs/PUBLIC_ONR_INTELLIGENCE.md` | Public source contracts, provenance, model boundaries, and gated sources |
| `docs/AWS_PUBLIC_SBIR_MODEL.md` | Authentic SageMaker training, evaluation, registry, security, and cost receipt |
| `docs/DEMO_SCRIPT.md` | A 39-minute evidence-first recording run |
| `volume_iv/` | Evaluator-ready shells with external inputs clearly marked |
