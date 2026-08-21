# Compass technical demonstration script

**Target runtime:** 39:15
**Hard maximum:** 50:00
**Format:** one continuous evidence-first recording
**Required order:** Elements 1 through 7, with all five strategic prompts

This script is a run sheet and narration guide. It is not a slide deck. During
the submitted recording, show only the live application, terminal, and exact
repository that produced the environment. Close Presenter Guide before the
take. Do not add marketing overlays, post-production callouts, edits, or
title cards.

## Timing map

| Segment | Start | End | Duration |
|---|---:|---:|---:|
| Opening and environment attestation | 00:00 | 01:30 | 01:30 |
| Element 1: Secure access and Zero Trust | 01:30 | 05:30 | 04:00 |
| Element 2: IaC and automation | 05:30 | 10:30 | 05:00 |
| Element 3: Ingestion, DataOps, and streaming | 10:30 | 16:00 | 05:30 |
| Element 4: Governance, quality, and catalog | 16:00 | 20:00 | 04:00 |
| Element 5: Decision-support analytics | 20:00 | 25:30 | 05:30 |
| Element 6: Dashboard and process automation | 25:30 | 32:30 | 07:00 |
| Element 7: Interoperability and secure export | 32:30 | 38:30 | 06:00 |
| Close | 38:30 | 39:15 | 00:45 |

Strategic prompts are named explicitly at these planned starts:

| Prompt | Topic | Planned start | Embedded in |
|---|---|---:|---|
| (c) | Zero Trust and IL4 or IL5 baseline | 04:15 | Element 1 |
| (d) | Disaster recovery, resilience, and failover | 08:45 | Element 2 |
| (a) | Sustainment of the legacy footprint | 13:15 | Element 3 |
| (b) | Financial and budgetary analytical integration | 23:15 | Element 5 |
| (e) | Data vendor and lifecycle management | 29:30 | Element 6 |

## Roles and prepared surfaces

Replace position labels with the approved Key Personnel names only after they
are confirmed against Attachment 7 and Volume II.

| Position | Primary segments |
|---|---|
| Chief Enterprise Architect | Opening, Elements 4 and 7, close |
| DevSecOps Engineer | Elements 1 and 2, prompts (c) and (d) |
| Data Architect | Element 3 and prompt (a) |
| Data Scientist | Element 5 and prompt (b) |
| Web Software Developer | Element 6 and prompt (e) |

Prepare these surfaces before pressing Record:

- Live CloudFront application on the public landing page
- Three authenticated browser profiles: scoped viewer, poweruser requester,
  and poweruser reviewer
- Poweruser requester profile on `/export/`, with its session retained for
  Element 7
- Poweruser reviewer profile ready for the approval reviewer inbox
- Terminal in the repository root with safe environment variables already set
- Redacted `artifacts/demo-preflight.json` verified as ready off camera, with
  all three live drop keys absent
- Redacted `artifacts/scale/` receipts for the completed 1K, 10K, 100K, and 1M
  acceptance runs, opened only when presenting their transport disclosure
- Repository viewer at `template.yaml`, `.github/workflows/quality.yml`,
  `.github/workflows/deploy.yml`, `db/migrations/003_security_hardening.sql`,
  and `db/migrations/004_opaque_approval_capability.sql`
- No notifications, secrets, tokens, account numbers, ARNs, bucket names,
  password manager popups, or unrelated tabs visible

The recording operator controls switching and timing. Technical narration is
performed by proposed Key Personnel.

## 00:00 to 01:30: Opening and environment attestation

### Screen

Show the public landing page at desktop width. The Government site banner,
Compass mission statement, workflow, and synthetic-data disclosure should be
visible. Do not open Presenter Guide.

### Narration

> This is Compass, our working S&T Portfolio Intelligence demonstration for
> N0001426R4002. This is one continuous recording. We will use the live
> application, the live cloud service, and the exact source repository that
> built it. There are no slides or marketing overlays.

> Every record shown today is machine-generated synthetic data. There is no
> CUI, PII, classified data, or real award information in this environment.

Point to the landing-page trust indicator, which must read Live services and
Synthetic data.

> This public indicator says Live services and Synthetic data. After sign-in,
> the protected System Inspector will identify its backend source separately.
> Compass also has a deterministic replay adapter for rehearsal and evaluator
> reproduction, but replay is labeled separately and is not used as evidence
> of cloud execution in this recording.

> We will follow all seven required elements in order. For each one, we will
> make a claim, perform an action, show the resulting receipt, and state the
> boundary of what this demonstration proves.

Transition to the signed-out login surface.

## 01:30 to 05:30: Element 1, Secure access, authentication, and Zero Trust

### 01:30 to 02:35: Strong authentication

Sign in as `presenter@compass.demo` through the Cognito hosted UI. Complete the
already enrolled TOTP challenge. Do not show enrollment secrets or a QR code.

### Narration

> Element 1 starts with identity. Self-registration is disabled. This formal
> presenter identity requires TOTP, while collaboration accounts stay
> password-only. The API validates the Cognito token before an application
> handler runs.

After redirect, point to the signed-in identity and organization scope.

> The verified Cognito group is authoritative. The shared identity module maps
> `compass-poweruser` to the poweruser role and the ONR-Corporate scope. It
> handles both native API Gateway JWT events and request-authorizer events. A
> forwarded role cannot override the verified group, and conflicting
> organization context fails closed.

### 02:35 to 03:15: Deny boundary

In the prepared terminal, run only the status check:

```bash
curl --silent --output /dev/null --write-out '%{http_code}\n' \
  "$API/system/evidence"
```

Point to `401`.

> This request has no bearer token, so the protected evidence route stops at
> the API boundary with 401. All 38 method-and-path operations across 35 URL
> paths use the JWT authorizer by default, including Scale Run, OpenAPI, and System
> Inspector.

### 03:15 to 04:15: Row and column policy

Switch to the prepared viewer browser profile on the dashboard. Point to the
Code-30 scope, lower visible row count, and masked funding value. Return to the
poweruser profile and point to the corporate value.

> The page did not filter these rows. Each request binds its organization with
> `SET LOCAL` inside a database transaction, and PostgreSQL FORCE RLS makes the
> decision. The application role is not the table owner.

> Funding is a separate database entitlement. The base curated relation does
> not grant the funding column to the shared runtime role. The corporate view
> has its own ONR-Corporate context gate. The viewer cannot select or filter on
> that hidden column.

### 04:15 to 05:30: Strategic prompt (c)

### Narration

> Strategic prompt (c) is Zero Trust and cybersecurity compliance for an IL4
> or IL5 baseline. The demonstrated controls are MFA, deny-by-default JWT
> authorization, transaction-scoped RLS, role-gated funding, private data
> subnets, KMS encryption, WAF, append-only audit, and an in-boundary Bedrock
> adapter.

> The boundary matters. This stack runs in commercial us-east-1 with
> security-baseline equivalents. It is not an accredited IL4 or IL5 enclave,
> and this demonstration does not imply an ATO. The production path is to
> deploy the versioned template into the Government landing zone, use approved
> identity and FIPS endpoints, apply required STIG and Compliance-as-Code
> profiles, forward events to the Government SIEM, and complete the formal
> authorization process.

Return to the poweruser profile and open Mission Control.

## 05:30 to 10:30: Element 2, Infrastructure as Code and automation

### 05:30 to 06:25: Deployed revision and source

In System Inspector, point to Live service, deploy revision, generated time,
request status and latency, correlation ID, and the explicit policy decision.
Refresh once and show a new correlation ID.

Run:

```bash
git rev-parse --short=12 HEAD
```

### Narration

> Element 2 begins with traceability. The revision returned by the protected
> service matches the exact source revision in this repository. Refreshing the
> projection produces a new request receipt and correlation ID.

> The projection is intentionally sanitized. It contains application evidence,
> not account IDs, ARNs, resource names, credentials, tokens, personal data,
> SQL, prompts, source records, presigned URLs, or raw exceptions.

### 06:25 to 07:35: Quality and deployment workflows

Show `.github/workflows/quality.yml` and the green run for the recording
commit. Point to the source policy, lint, dependency audits, tests, migration
comparison, SAM validation and build, typecheck, scenario tests, static build,
and browser smoke stages.

Show `.github/workflows/deploy.yml` and its green run for this environment.
Point to protected environment dispatch, OIDC credential setup, deploy
revision, expand-before-code migration, post-deploy bundled migration, live
frontend build, publish, and boundary check.

### Narration

> This is working CI and controlled deployment, not a future-state diagram.
> The quality workflow rebuilds and tests the candidate from a clean checkout.
> The deployment workflow is manually dispatched into a protected GitHub
> environment and receives short-lived AWS credentials through OIDC. No
> long-lived AWS key is committed here.

> For an existing stack, the deployment applies compatible additive
> migrations before switching application code, then reruns the bundled
> migration set after deployment. Both applicable passes require a successful
> role bootstrap. It publishes the live frontend and verifies both the public
> web edge and the unauthenticated 401 boundary.

### 07:35 to 08:45: Template validation and RMF evidence

Run:

```bash
sam validate --lint
python3 src/functions/rmf_artifact/app.py -o /tmp/compass-rmf.md
sed -n '1,45p' /tmp/compass-rmf.md
```

### Narration

> The SAM template provisions the network, identity, API, functions, workflow,
> database, encryption, web edge, logs, alarms, and operations dashboard. The
> validator checks the deployable source.

> The RMF generator reads that same template and emits deterministic ports,
> protocols, services, topology, protection inventory, and candidate NIST
> mappings. It stamps the template hash and cites source properties. It does
> not use an LLM, and it states what it cannot prove, including runtime drift
> and non-technical controls.

### 08:45 to 10:30: Strategic prompt (d)

Show `DatabaseResilienceMode`, its condition, database cluster, writer, reader,
backup retention, and deletion protection in `template.yaml`.

### Narration

> Strategic prompt (d) is disaster recovery, resilience, and failover. The
> recorded stack declares its actual database mode. In the default demo mode,
> Compass has one writer, seven-day backup retention, and deletion protection
> off. That is reproducible and supports point-in-time backup retention, but it
> is not database instance failover.

> The optional `ha` mode adds a cluster reader, changes backup retention to 14
> days, and enables deletion protection. That demonstrates a stronger
> single-region database posture. It still does not provide cross-region
> disaster recovery.

> The cluster subnet group spans two availability zones, but this template does
> not pin either instance to a named zone. We verify deployed placement before
> making any AZ-specific claim.

> Production recovery objectives come from the mission impact analysis and
> must be proven by exercises. The production target adds approved cross-region
> backup copy or replication, restore automation, reader promotion and traffic
> failover, per-AZ egress, longer retention, capacity validation, monitoring
> integration, and recurring drills. We do not claim a tested production RTO
> or RPO from this demo.

Navigate to Ingest.

## 10:30 to 16:00: Element 3, Automated ingestion, DataOps, and streaming

### 10:30 to 11:20: Pipeline definition and live state

Point to the live mode label, the batch ledger, quality-rule columns, activity
ticker, and three ingestion velocities. Do not call the ticker a
high-throughput workload.

### Narration

> Element 3 is one event-driven intake path. A sanitized object-created event
> starts the Express workflow. Workers pass a small manifest through Fetch,
> Validate, Quality Gate, and either Persist or Quarantine. Complete records do
> not travel in workflow state.

> The ticker orders the governed database projection first, then merges recent
> Kinesis transport receipts by stable event ID. A transport receipt with no
> organization scope is corporate-only. The once-per-minute synthetic signal
> proves stream integration and source labeling, not a measured production
> throughput rate.

### 11:20 to 12:05: Clean batch

Run the prepared clean drop command. Watch the new batch appear and complete.
Expand it.

```bash
python3 scripts/prepare_demo.py release-drop good \
  --stack compass-demo --region us-east-1
```

> This canonical synthetic drop passed the deterministic rules. The positive
> curated count is the persist receipt.

### 12:05 to 13:15: Defective batch

Run the defective drop. Watch it reach quarantined status. Point to zero
curated rows and failed-rule counts.

```bash
python3 scripts/prepare_demo.py release-drop bad \
  --stack compass-demo --region us-east-1
```

> This batch contains incompatible and malformed records. The gate retained
> the raw evidence, reported the failed rules, quarantined the batch, and wrote
> zero curated rows. Downstream catalog, model, and dashboard state cannot
> treat this batch as governed data.

### 13:15 to 14:35: Strategic prompt (a)

Run the compatible legacy drop and show the detected schema variant and
resulting disposition.

```bash
python3 scripts/prepare_demo.py release-drop compatible \
  --stack compass-demo --region us-east-1
```

### Narration

> Strategic prompt (a) is sustainment of the legacy footprint. This file uses
> compatible renamed fields. An edge adapter maps it to the canonical grant
> contract, while the quality gate remains unchanged.

> Our modernization pattern is incremental: observe the legacy source, place
> an anti-corruption adapter at the edge, compare old and new outcomes, move
> one bounded capability at a time, and retire it only after acceptance and
> rollback criteria pass. The incompatible batch shows the other side of that
> policy: Compass does not guess when meaning is unsafe.

> This demonstrates the adapter and strangler pattern. It does not claim that
> an actual Government legacy estate has already been migrated.

> Each release command copied one previously validated synthetic fixture from
> a non-triggering staging prefix into its fixed live landing key. It returned
> only logical locators, so the terminal did not disclose the physical bucket
> name. Each key is one-shot by default.

### 14:35 to 16:00: Backend receipts

Open System Inspector in the poweruser profile. Select each new run in turn.
Point to stages, quality score, curated or quarantined outcome, generated time,
and database projection source.

> The product screen showed the decision. System view now shows the backend
> receipts from the quality and curated projections. For the quarantined run,
> Persist is skipped and no curated rows were written.

Navigate to Catalog.

## 16:00 to 20:00: Element 4, Data governance, quality, and cataloging

### 16:00 to 17:20: Governed catalog

Find the newly curated clean or legacy batch. Use the keyboard-accessible row
action to open it. Point to source, record count, classification label,
quality score, and rule explanation.

### Narration

> Element 4 turns an intake run into a governed data product. The catalog score
> is calculated from recorded rule results. It is not a decorative health
> number. Source, classification, row count, and quality provenance stay tied
> to the batch.

> The defective batch remains visible as operational quality evidence on the
> ingest page, but it is not presented here as a curated data product.

### 17:20 to 19:05: Live lineage

Open `/catalog/lineage/?batch=<new-batch-id>`. Traverse the source, raw,
quality, curated, and dashboard nodes that actually exist for this intake
run. Do not describe an edge that is absent, and do not imply that a later
analytics or export run shares this run identifier.

### Narration

> These nodes and edges were emitted by the run. The lineage view accepts the
> live batch identifier as a query parameter, so this static web deployment can
> open a batch created after the frontend build. There is no static-page
> rebuild between ingestion and this graph.

> Lineage stops where execution stops. A quarantined batch does not receive a
> fictional curated, model, or dashboard path.

### 19:05 to 20:00: Governance summary

> The governance chain is therefore inspectable: source object, normalization,
> quality decision, curated data product, downstream processing, and audit
> evidence. The API still enforces the caller's row and column policy when a
> user follows that chain.

Navigate to Analytics.

## 20:00 to 25:30: Element 5, Decision-support analytics and modeling

### 20:00 to 21:05: Run the model

Start one analytics run. Point to the run ID, status, parameters, and elapsed
state. Wait for completion without filling silence with claims.

### Narration

> Element 5 runs a transparent topic model over governed curated records. The
> implementation uses TF-IDF plus non-negative matrix factorization with
> explicit topic count and seed. It persists the run, topics, grant weights,
> metrics, recommendation, and lineage.

### 21:05 to 22:20: Inspect results

Select two topics. Point to top terms, grant count, trend values, any funding
value available to the corporate persona, model metrics, and the persisted
recommendation.

> These terms and trends are model output, while grant counts and governed
> funding totals are database evidence. Compass keeps those concepts separate.
> The recommendation is tied to this stored run ID so an evaluator can follow
> it back to parameters and inputs.

### 22:20 to 23:15: Model evidence boundary

Open System Inspector and point to latest model-run metadata. Do not claim a
metric that is blank or absent.

> System view confirms that a model run was stored and identifies its safe
> metrics. It does not expose abstracts, prompts, embeddings, or raw portfolio
> rows.

### 23:15 to 25:00: Strategic prompt (b)

Return to the analytics trend view and then open the dashboard funding by
fiscal year card at the transition to Element 6.

### Narration

> Strategic prompt (b) is financial and budgetary analytical integration. The
> demonstrated data is obligated award value joined to program area, fiscal
> year, organization, topic, quality, and anomaly context. Compass can compare
> concentration and change through the same governed model-run contract.

> The fiscal-year card uses those obligated award values. Its dashed line is a
> computed even-spend mean across the visible years. Compass does not ingest an
> appropriation, Program and Budget, or authoritative budget-authority feed in
> this demonstration, so we do not label that computed baseline as budget
> authority.

> The integration approach for approved financial sources is a versioned
> source adapter, reconciliation controls, accounting dimensions and lineage,
> and policy applied before analytics. This run proves the governed analytical
> path, not production financial-system integration.

### 25:00 to 25:30: Decision handoff

> The analytical output now feeds the decision surface. We will keep the same
> identity and data scope as we move into Element 6.

## 25:30 to 32:30: Element 6, Unified dashboard, visualization, and automation

### 25:30 to 27:00: Decision brief

On the dashboard, point to identity scope, grants, governed funding, program
areas, quality, open anomalies, pending approvals, summary, and charts. Apply
one rehearsed program-area or fiscal-year filter. Point to the result count,
decision brief, KPIs, and charts as they recut. Clear the filter, then open a
chart's values table to demonstrate a non-visual alternative.

### Narration

> Element 6 assembles the current scope in one dashboard request. A leader can
> see portfolio size, investment concentration, quality trend, topic mix,
> findings, and pending decisions. The chart values table carries the same
> evidence without relying on color or pointer interaction.

> This filter is not client-only hiding. The selected predicate is sent to the
> protected dashboard API, where parameterized SQL applies it inside the same
> row-level security transaction. The allowed filter choices and returned
> result set remain bounded by the signed-in identity.

> Funding is visible here because this is the corporate persona. The viewer
> saw the same product shell with a smaller row scope and masked funding in
> Element 1.

### 27:00 to 28:20: In-boundary question answering

Ask one rehearsed question, for example:

```text
Which program areas have the strongest recent concentration, and which source records support that conclusion?
```

Point to the answer, citations, model label, and scope disclosure.

### Narration

> Ask Compass retrieves cited records inside the caller's RLS transaction and
> sends the bounded context through the Bedrock adapter. The answer inherits
> the data policy. This demonstrates governed RAG over synthetic data, not an
> autonomous decision authority.

### 28:20 to 29:30: Findings workflow

Open the anomaly queue. Select one finding, generate its rehearsed two-sentence
triage note, and request a review. Point to the returned approval record and
its pending state. Do not use the cached dashboard counter as the immediate
receipt for this write.

> A finding becomes a human decision record. Request and decision are separate
> states, and each state change appends audit evidence in the same database
> transaction. We will complete a separate-persona approval in Element 7.

### 29:30 to 31:15: Strategic prompt (e)

Open Licenses. Point to renewal urgency, owner, entitlements, seat utilization,
and named dataset dependencies.

### Narration

> Strategic prompt (e) is data vendor and lifecycle management. This register
> connects vendor, product, entitlements, seats, renewal date, accountable
> owner, and the named datasets that depend on the agreement. It exposes both
> utilization risk and renewal risk before a source stops refreshing.

> The boundary is explicit. Renewal urgency is computed in the browser from
> `renews_on`; no scheduled notification job is implemented. Dataset
> dependencies are stored names in this prototype, not enforced relational
> foreign keys. A production service would make those dependencies canonical,
> run renewal evaluation server-side, notify accountable owners, and link
> procurement evidence and disposition workflow.

### 31:15 to 32:30: Responsive and accessible interaction

Briefly narrow the browser to the rehearsed mobile width. Open the navigation
drawer, move to Dashboard, and close it. Restore desktop width.

> The same mission workflow is usable at mobile and desktop widths. Navigation
> is keyboard and touch accessible, focus is visible, and reduced-motion
> preferences are honored. The responsive shell is part of the working
> application, not a separate mockup.

Switch to the prepared poweruser requester profile on Export.

## 32:30 to 38:30: Element 7, Interoperability, portability, and secure export

### 32:30 to 33:35: Trigger the aggregation guard

As the poweruser requester, choose the rehearsed CSV export that exceeds the
configured threshold. Submit it. Point to HTTP 428, matched row count,
threshold, and exact `exp-` subject identifier.

### Narration

> Element 7 treats release as a governed decision. The API counted every row
> matched by this normalized request, independent of a page limit. Because the
> count exceeds the recording threshold, it returned HTTP 428 before creating
> a file.

> The subject identifier fingerprints this organization's exact format,
> columns, and filters. Approval for a different request cannot clear it.

### 33:35 to 34:20: Request approval

Click Request approval. Point to requester, pending state, subject identifier,
and the note that the requester cannot decide it. Leave this requester window
open.

> This poweruser can request the release, but four-eyes is enforced in this
> deployed stack, so the same authenticated identity cannot approve its own
> request. A second poweruser identity must make the decision.

### 34:20 to 35:20: Independent reviewer inbox

Switch to the separate poweruser reviewer browser profile. Open the approval
reviewer inbox, which reads protected `GET /approvals`. Find the pending export
by its subject identifier. Approve it and copy the issued opaque one-time
token. Do not expose a bearer token; this is the application approval
capability only.

### Narration

> This is a separate authenticated reviewer. The inbox is a live protected API
> projection, not local browser state. The decision records requester,
> reviewer, time, expiration, and exact subject. The issued capability is an
> opaque, short-lived token that can be consumed once. Only its SHA-256 verifier
> is stored.

### 35:20 to 36:20: Exact retry and one-time release

Return to the original poweruser requester session. Paste the opaque one-time
approval token into the pending request and retry without changing the format,
columns, or filters. Point to export ID, row count, format, audited status, and
short-lived download.

### Narration

> The requester retried the same endpoint. The server locked the approval,
> verified the exact fingerprint and expiry, marked it consumed in the
> authorized transaction, appended the audit receipt, and only then returned
> the release reference.

Click Verify one-time use. The application replays the exact request once with
the capability held only in page memory. Point to the 403 denial and the
single-use verified receipt.

> The second spend is denied. This approval is a one-time capability, not a
> reusable bypass flag.

### 36:20 to 37:20: Authoritative backend readback

Switch to poweruser Mission Control. Open Control receipts and sanitized audit
readback. Point to the approval and export categories, time, allowed safe
detail, request correlation, and current live label.

> The export page showed the interaction ledger. This System Inspector view is
> the authoritative sanitized server projection from append-only audit and
> application tables. Sensitive infrastructure, identity, source data, SQL,
> prompts, and presigned URLs remain excluded.

### 37:20 to 38:05: OpenAPI and portability

Return to Export and open the protected OpenAPI 3.1 panel. Point to the served
contract and the 38 protected operations across 35 URL paths. Mention the
selected CSV format.

### Narration

> Interoperability starts with a contract the running service serves itself.
> Data is stored in PostgreSQL with versioned SQL, identity uses OIDC and JWT,
> and release formats are CSV, JSON, and optional parquet.

> Managed AWS services are deliberate for this demonstration. Portability
> means portable data, standard contracts, and replaceable adapters. It does
> not mean the current stack has no cloud dependencies.

### 38:05 to 38:30: Element 7 receipt

> The evidence chain is complete: scoped request, threshold decision, exact
> fingerprint, independent approval, expiry, one-time consumption, release,
> server audit readback, and published interface contract.

Return to the dashboard or landing page.

## 38:30 to 39:15: Close

### Narration

> Compass has now demonstrated all seven elements in sequence and answered all
> five strategic prompts. The same synthetic portfolio and the new batch moved
> through identity, infrastructure, ingestion, governance, analytics, decision
> support, and controlled release, with backend evidence available from the
> product.

> We have also kept the boundaries visible: replay is not live proof, the
> commercial stack is not accredited IL5, the financial baseline is computed,
> license alerts are not scheduled, and production disaster recovery requires
> approved objectives and tested cross-region procedures.

> The submitted repository tag matches the deployed revision shown today. The
> Volume IV index provides the exact timestamps, presenters, video access, and
> read-only repository access. Thank you.

Stop the recording. Do not add a title card or edit the take.

## Separate Scale Lab evaluator tour

This tour is outside the fixed 39:15 Factor 3 sequence. Use it as a separate
evaluator walkthrough or as a rehearsed extension only after the submission
timing and required order are reapproved. Do not replace any of the seven
required elements with this section.

The Satsyil target completed all four direct-IAM acceptance runs on 2026-08-11.
A separate live browser pass completed Cognito password and TOTP, loaded all
nine screens without `Failed to fetch`, exercised the Scale controls, showed
the 1M profile unlocked with its exact cost gate enabled, and found no browser
command errors. Confirm that evidence is still current before the recording.
Repository code, a Scale Plan, and a pre-run Cost Estimate alone are not
measured execution evidence.

### Scale Lab screen and bounded intent

Sign in as the corporate poweruser and open `/admin/scale/`. Point to the Live
source label, fixed Workload Profile cards, deterministic seed, interactive
architecture, and empty or selected run console.

### Narration

> Scale Lab is a Mission Workspace for one bounded production Scale Run. The
> browser chooses a fixed Workload Profile and a deterministic seed. It cannot
> choose a raw record count, partition size, concurrency, retention, model
> spend, or cost ceiling.

> The profiles are `1k`, `10k`, `100k`, and `1m` total physical records across
> six linked synthetic datasets. Every profile uses 20 percent grants, 30
> percent finance, 20 percent milestones, 10 percent documents, 2 percent
> licenses, and 18 percent stream events. For `10k`, that is exactly 2,000,
> 3,000, 2,000, 1,000, 200, and 1,800 records.

Select `10k`. Preview the Scale Plan and point to six exact partitions, seed,
concurrency, official price snapshot, estimate, contingency, and upper bound.

> This 15-minute Scale Plan is actor-bound and can be consumed once. The Run
> Gate verifies identity, feature state, profile limit, one active run,
> idempotency, price freshness, and both the profile and deployment cost caps.
> The estimate includes 25 percent contingency. Missing or stale price
> evidence fails closed.

> The `1m` profile remains locked unless this deployment allows one million
> records and a successful `100k` proof receipt remains in the durable ledger.
> That prerequisite is evidence-based progressive capacity, not a browser
> override.

Launch once. Use the interactive four-plane architecture while the run console
polls.

> A Standard Step Functions workflow carries only the run identifier. It
> dispatches bounded partitions through SQS to Lambda workers. Each worker
> deterministically generates and validates linked records, writes compressed
> landing, curated, or quarantine objects to S3, and commits a DynamoDB
> Partition Receipt. Glue catalogs all six datasets. Athena converts them to
> Parquet under a 10 GiB per-query cutoff and completes full-corpus
> intelligence. The Scale Lab reads a compact Serving Projection instead of
> scanning the lake during interaction.

Point to stage progress, records, partitions, queue recovery depth, quality,
intelligence coverage, observed performance, and cost status. If the run has
not completed, say so and do not narrate projected values as results.

> The terminal evidence chain is the Run Manifest plus Partition, Quality,
> Intelligence, Performance, and Cost Receipts. Generated records must
> reconcile to curated plus quarantined records, every part and terminal
> receipt carries SHA-256 evidence, intelligence declares corpus coverage,
> performance is observed, and cost is labeled estimated, metered, or billed
> reconciliation pending.

Open the compact acceptance summary or the corresponding redacted receipt and
show one row at a time:

| Profile | Partitions | Duration | Quality | Curated | Quarantined | Anomalies | Export rows |
|---|---:|---:|---:|---:|---:|---:|---:|
| 1K | 6 | 21.351 s | 98.90 | 989 | 11 | 143 | 989 |
| 10K | 6 | 20.329 s | 98.91 | 9,891 | 109 | 1,403 | 9,891 |
| 100K | 11 | 25.853 s | 98.92 | 98,921 | 1,079 | 13,727 | 98,921 |
| 1M | 41 | 72.615 s | 98.98 | 989,852 | 10,148 | 137,852 | 989,852 |

### Measured result narration

> These four bounded synthetic runs completed in this target environment. The
> million-record run used 41 partitions, analyzed all 200,000 grant records,
> reconciled 989,852 curated records and 10,148 quarantined records, detected
> 137,852 deterministic anomalies, and exported 989,852 Parquet rows. Its
> observed duration was 72.615 seconds.

> The four pre-run estimates totaled $0.21131732. Their accrued model estimates
> totaled $0.09554118. These are price-model outputs, not billed cost. The HA
> monthly forecast is $163.70 for a 730-hour month and is not observed billing.

Keep the completed run selected and open `Decision brief` from the mission
navigation. Point to `Selected Scale Run`, `1,000,000 synthetic records`, and
`200,000` grants analyzed.

> The active evidence set follows us from Scale Lab into Decision Brief. This
> view reads the selected run receipt, so it shows the million-record corpus
> and its 200,000 grant records instead of mixing in the curated 400-grant
> baseline. It is an aggregate receipt view for quality, quarantine,
> anomalies, partitions, throughput, and modeled cost. Record filters,
> citations, funding charts, and workflow dispositions remain in the curated
> baseline because the Scale receipt does not contain those row-level views.

Select `Use curated baseline`, confirm that the 400-grant record-level
workspace returns, then reopen the completed Scale Run before continuing if
you want the Scale context staged for questions.

After a completed run, request the governed Parquet Export Job and wait for a
ready receipt.

> Export is asynchronous. Its receipt binds exact rows, bytes, format,
> checksum, expiry, and audit evidence. Browser receipts use logical
> `lake://scale-runs/...` and `run://...` locators. They do not reveal bucket
> names, S3 keys, ARNs, queue URLs, table names, or workflow execution IDs.

If showing an acceptance artifact, state its transport disclosure verbatim in
substance:

> This acceptance receipt exercised the deployed Scale Control route handler
> and live data plane through direct AWS IAM. It bypassed API Gateway transport,
> Cognito and TOTP, WAF, and the browser network path. Interactive identity was
> verified separately, and the saved receipt removed the export download URL.

Close by linking the architecture and cost boundaries.

> The production architecture and cost model are source-controlled planning
> evidence. The cost model compares demo and HA fixed monthly forecasts and
> applies a fresh price-backed gate to each run. Only a completed receipt from
> this target environment supports a measured Scale Run claim.

> This proves a production-shaped bounded synthetic path. It does not prove an
> ATO, unlimited load, sustained evaluator concurrency, multi-terabyte scale,
> Government-data operation, or Exhibit B certification.

## Rehearsal acceptance checklist

Do not record until every item is true.

- Runtime finishes between 38:00 and 40:00 in one take.
- All seven elements are in order.
- Each strategic prompt is named exactly once at its indexed primary moment.
- Mode badge says Live service whenever runtime evidence is shown.
- Recording revision equals `git rev-parse --short=12 HEAD`.
- All three password-only team sessions are stable, and the formal presenter
  TOTP path was verified before recording.
- Viewer and poweruser scopes differ as expected.
- All 38 protected operations work with the intended identity when Scale Run is enabled.
- Clean, legacy, and defective files are absent before the take.
- The redacted preparation receipt says ready and all five fixture hashes
  match.
- Defective batch always curates zero rows.
- Query-based lineage opens the newly created batch.
- Analytics completes within the allotted time.
- RAG response returns with governed citations.
- Poweruser requester item appears in the separate poweruser reviewer inbox.
- Requester cannot approve its own request.
- Reviewer can issue the short-lived approval capability.
- Exact request succeeds once and token reuse fails.
- System Inspector shows server audit readback without sensitive fields.
- OpenAPI reflects 38 operations across 35 URL paths.
- Presenter Guide is closed.
- No secret, token, account ID, ARN, bucket name, email notification, chat
  message, or password manager appears on screen.
- No slide, marketing overlay, or post-production edit is used.

## Stop and restart conditions

Restart the take after correcting the environment if any of these occurs:

- The UI says Replay fixture during a cloud-proof segment.
- The revision does not match the recording commit.
- MFA, a protected route, database policy, or Bedrock call fails.
- A quarantined batch shows curated rows or downstream curated lineage.
- An analytics run does not complete.
- Self-approval succeeds.
- A changed fingerprint accepts an old approval.
- An opaque approval capability succeeds more than once.
- System Inspector exposes a prohibited field.
- The run passes 43 minutes before Element 7 finishes.

Do not hide a failed control with narration. Fix it, reset the synthetic
scenario, and record a new continuous take.

Use the bounded reset between takes:

```bash
python3 scripts/prepare_demo.py prepare \
  --stack compass-demo \
  --region us-east-1 \
  --confirm-synthetic-reset RESET_FIXED_SYNTHETIC_DEMO_DATA \
  --receipt artifacts/demo-preflight.json
```
