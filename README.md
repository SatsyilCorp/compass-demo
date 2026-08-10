# Compass — S&T Portfolio Intelligence (demonstration platform)

Compass is a working demonstration of a Navy/ONR **Data & Analytics platform**
built for the N0001426R4002 technical demonstration (Volume IV, Factor 3). It
implements the full life of a research-portfolio record — raw file → automated
ingest → quality gate → curated, RLS-protected store → catalog & lineage →
topic-model analytics → executive dashboard with in-boundary AI → governed
export — as one deployable AWS stack plus a Next.js front end.

**All data in this repository and in any deployment of it is synthetic.**
Every grant, awardee, abstract, and dollar figure is machine-generated mock
data; there is no CUI, no PII, and no real award anywhere.
`seed/SYNTHETIC-DATA-MANIFEST.md` is the audited, per-file statement of that
claim and is regenerated with the data.

## What it demonstrates

The seven scenario elements of L 11.3, one page or route each:

| # | Element | Where |
|---|---|---|
| 1 | Secure access, MFA, Zero Trust | Cognito Hosted UI (MFA ON, TOTP), JWT-guarded API, `GET /me`, RLS personas |
| 2 | Infrastructure as Code & automation | `template.yaml` (single SAM stack), `db/migrations/`, RMF-artifact generator |
| 3 | Automated ingestion, DataOps, streaming | S3 → EventBridge → Step Functions intake pipeline, quality gate, Kinesis ticker (`/ingest`) |
| 4 | Governance, quality, cataloging | `/catalog` with explainable scores; run-emitted lineage graph (`/catalog/[id]`) |
| 5 | Decision-support analytics | numpy TF-IDF + NMF topic model, funding-anomaly z-scores, recommendations (`/analytics`) |
| 6 | Unified dashboard & process automation | `/dashboard` (one-round-trip KPIs, Bedrock exec summary, RAG "Ask Compass"), anomaly→approval routing, `/licenses` |
| 7 | Interoperability & secure export | `POST /export` (CSV/JSON/parquet, RLS/CLS-enforced, aggregation guard, audited), served OpenAPI 3.1 |

Two Exhibit-B requirements are implemented as first-class features rather than
narrative:

- **Aggregation-risk guard** — `POST /export` refuses bulk extractions above a
  configurable row threshold (HTTP 428) unless a query-fingerprint-bound
  approval is attached; every decision is audit-logged before bytes leave
  (`src/functions/export/app.py`).
- **RMF artifacts generated from the IaC** — a deterministic (no-LLM)
  generator parses `template.yaml` and emits the Ports/Protocols/Services
  tables, topology diagram, and cited NIST 800-53 candidate mapping
  (`src/functions/rmf_artifact/app.py`), so security documentation cannot
  drift from the infrastructure.

## Open-architecture posture

Compass's answer to vendor lock-in is **portable data + standard contracts +
replaceable adapters** — deliberately *not* "everything open":

- **Portable data.** The store is standard PostgreSQL; the schema is plain,
  versioned SQL in `db/migrations/`; exports are CSV, JSON, and parquet.
  You can leave with your data, schema, and history on any day.
- **Standard contracts.** The API publishes its own OpenAPI 3.1 document from
  the running service (`GET /openapi.json`); auth is standard OIDC/JWT. Any
  enterprise platform (Advana, Cloud One) integrates against a published
  contract, not against us.
- **Replaceable adapters.** The seams that touch vendors are narrow, named
  modules: the LLM gateway is Bedrock-only behind `compass_common/llm.py`
  (swap the transport, keep the callers); ingestion schema variants are
  handled by a normalizer at the edge (`src/functions/intake/normalize.py`);
  identity is an OIDC seam (Cognito today, any approved IdP by
  configuration); Kinesis/Step Functions are used through plain handlers
  that do not leak into business logic.

Managed AWS services are used on purpose — they are the fastest route to an
accreditable baseline — but every one of them sits behind one of those three
layers, with the exit path documented in `docs/ARCHITECTURE.md`.

## Quickstart — mock mode (zero AWS, ~2 minutes)

The entire UI runs against bundled fixtures with auth disabled. Nothing is
deployed, no credentials are needed.

```bash
cd frontend
cp .env.example .env.local     # defaults: NEXT_PUBLIC_USE_MOCK=true, AUTH_DISABLED=true
pnpm install
pnpm dev                       # → http://localhost:3000
```

Every route in `docs/CONTRACTS.md` renders on fixture data; a persona switcher
stands in for login so the RLS-scoped views can still be explored.

## Full deployment (real AWS stack)

Prerequisites: an AWS account (region **us-east-1** — the CloudFront-scope WAF
pins it), AWS SAM CLI, Docker (for `sam build --use-container`), Python 3.11+,
Node 20+ with pnpm.

```bash
cp samconfig.toml.template samconfig.toml
./src/functions/migrator/prepare_migrations.sh
sam build --use-container && sam deploy        # first deploy
# fill WebCallbackUrl/WebLogoutUrl/WebOrigin from the CloudFrontDomain output,
# then deploy again (Cognito needs the CloudFront domain — the "two-deploy dance")
```

Then: migrate, seed, enroll demo users, and publish the frontend — the exact
commands are in **`docs/RUNBOOK.md`**. There are **no secrets in this
repository**: the database credential is created and held by RDS/Secrets
Manager at deploy time.

## Repository map

```
template.yaml            single SAM/CloudFormation stack (VPC, Aurora, Cognito,
                         HttpApi, Lambdas, Step Functions, Kinesis, S3+CloudFront, WAF, KMS)
db/migrations/           001_schema.sql (schema `compass`), 002_rls.sql (FORCE RLS + CLS)
src/common/              shared Lambda layer: compass_common (config, db, http, llm, audit)
src/functions/<name>/    one Lambda per directory; routes per docs/CONTRACTS.md
statemachines/           intake.asl.yaml — express ingest workflow
scripts/seed_data.py     synthetic data generator (stdlib-only, deterministic)
seed/                    generated fixtures + SYNTHETIC-DATA-MANIFEST.md
frontend/                Next.js 15 App Router, static export; mock mode via lib/mock/*
docs/                    CONTRACTS.md · ARCHITECTURE.md · SECURITY.md · RUNBOOK.md · DEMO_SCRIPT.md
volume_iv/               Volume IV submission shells (links, presenters, timestamps, git access)
```

## Documentation

| Doc | Purpose |
|---|---|
| `docs/CONTRACTS.md` | The locked interface contracts every subsystem builds against |
| `docs/ARCHITECTURE.md` | Components, data flow, element mapping, portability seams |
| `docs/SECURITY.md` | Zero Trust, RLS/CLS, in-boundary AI, KMS/WAF, aggregation guard, RMF-as-code — with honest demo-vs-production deltas |
| `docs/RUNBOOK.md` | Deploy, migrate, seed, enroll users, publish frontend, record, tear down |
| `docs/DEMO_SCRIPT.md` | The word-for-word, timed 44:30 recording script |
| `seed/SYNTHETIC-DATA-MANIFEST.md` | Per-file proof that all data is synthetic |
