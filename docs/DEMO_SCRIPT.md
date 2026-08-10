# Compass — Pre-Recorded Technical Demonstration Script

**Solicitation:** N0001426R4002 — Volume IV, Factor 3 (Sub-Factor 3.1)
**Total planned runtime:** 44:30 (hard ceiling per L 11.2(b): 50:00)
**Format:** One continuous, uninterrupted screen recording with live narration.

This is the word-for-word script. Spoken narration is in blockquotes. Stage
directions — what is on screen, what the presenter clicks or types — are in
*[bracketed italics]*. Per-segment **HARD STOP** times are cut-offs, not
targets: if a segment runs long, the presenter jumps to the segment's marked
**[CUT LINE]** and moves on. Nothing after a hard stop may be borrowed except
from the 5:30 of reserve between 44:30 and the 50:00 ceiling.

---

## Single-take rules (from Section L 11.2 — read before recording)

1. **No slide decks.** PowerPoint or any static deck is strictly prohibited
   (L 11.2(c)). Everything on screen is the live application, a live terminal,
   or the live code repository.
2. **No heavy editing.** Highly edited captures, post-production marketing
   overlays, or simulated application videos draw an **Unacceptable** rating
   (L 11.2(c)). Record in one take. A single hard cut between takes only if a
   technical failure forces a restart — no overlays, no speed-ups, no dubbing.
3. **≤ 50 minutes total** (L 11.2(b)). This script plans 44:30.
4. **Elements run sequentially, 1 through 7** (L 11.3). Strategic prompts
   (L 11.4) are narrated while executing the elements, plus one dedicated
   segment for Prompt (d).
5. **Key Personnel present and narrate all technical content** (L 11.2(e)).
   No business-development or sales narration anywhere in the recording.
6. **Live, functioning cloud environment** (L 11.2(c)): the recording runs
   against the deployed `compass-demo` stack — not mock mode — plus the live
   git repository.
7. **Synthetic data only** (L 11.2(d)): every record shown is machine-generated
   (see `seed/SYNTHETIC-DATA-MANIFEST.md`). No CUI, no PII, no classified data.

---

## Run of show

| Segment | Time | HARD STOP | Presenter (Key Personnel) | Covers |
|---|---|---|---|---|
| Opening & environment attestation | 00:00–02:00 | 02:00 | Chief Enterprise Architect | Intro, rules of the recording |
| **Element 1** — Secure Access, Authentication, Zero Trust | 02:00–07:00 | 07:00 | DevSecOps Engineer | L 11.3 E1 + Prompt (c) part 1 |
| **Element 2** — Infrastructure as Code & Automation | 07:00–13:00 | 13:00 | DevSecOps Engineer | L 11.3 E2 + Prompt (c) part 2 + RMF-as-code |
| **Element 3** — Ingestion, Data Operations, Streaming | 13:00–19:00 | 19:00 | Data Architect | L 11.3 E3 + Prompt (a) legacy sustainment |
| **Element 4** — Governance, Quality, Cataloging | 19:00–24:00 | 24:00 | Chief Enterprise Architect | L 11.3 E4 |
| **Element 5** — Decision-Support Analytics & Modeling | 24:00–30:00 | 30:00 | Data Scientist | L 11.3 E5 + Prompt (b) financial analytics |
| **Element 6** — Unified Dashboard & Process Automation | 30:00–36:00 | 36:00 | Web Software Developer | L 11.3 E6 + Prompt (e) data-vendor licenses |
| **Element 7** — Interoperability, Portability, Secure Export | 36:00–41:00 | 41:00 | Chief Enterprise Architect | L 11.3 E7 + aggregation guard |
| **Prompt (d)** — DR, Resilience, Failover (dedicated address) | 41:00–43:30 | 43:30 | DevSecOps Engineer | L 11.4(d) |
| Close | 43:30–44:30 | 44:30 | Chief Enterprise Architect | Recap, strategic alignment |

Strategic-prompt coverage map (all five are mandatory — L 11.4):

| Prompt | Where addressed |
|---|---|
| (a) Sustainment of the legacy footprint | Element 3, 16:30–19:00 |
| (b) Financial & budgetary analytical integration | Element 5, 27:45–30:00 |
| (c) Zero Trust & cybersecurity compliance (IL4/IL5) | Elements 1 & 2, 05:30–07:00 and 11:00–13:00 |
| (d) Disaster recovery, resilience, failover | Dedicated segment, 41:00–43:30 |
| (e) Data vendor & lifecycle management | Element 6, 33:45–36:00 |

---

## Pre-recording checklist (do all of this BEFORE pressing record)

- [ ] Stack `compass-demo` deployed and healthy in us-east-1; frontend
      published to CloudFront; second deploy done so Cognito callbacks point at
      the CloudFront domain (see `docs/RUNBOOK.md` §3–§7).
- [ ] **`ExportMaxRows=250` for this recording** (parameter override at deploy).
      The synthetic portfolio is ~480 curated rows; the default 5,000-row guard
      threshold would never trip on it. 250 makes the aggregation guard
      demonstrable on real data with no code changes. Say this on camera —
      it is a configuration fact, not a trick.
- [ ] **pyarrow enabled** on the export function (uncomment the pin in
      `src/functions/export/requirements.txt`, `sam build --use-container`,
      redeploy) so the parquet export is real. If it is NOT enabled, the API
      returns CSV with an explicit note — present that honestly and skip the
      parquet click (Element 7 has a stage direction for both cases).
- [ ] `StreamTickerState=ENABLED` so the Kinesis ticker is live.
- [ ] Database migrated and seeded: baseline portfolio curated
      (`batch_id=seed-initial-2026`), at least one analytics run already
      completed earlier (so the catalog and dashboard are not empty at minute
      2), licenses loaded. The three demo drops (`drop_good`,
      `drop_compatible_variant`, `drop_incompatible_bad`) NOT yet ingested —
      they are ingested live during Element 3.
- [ ] Demo users enrolled with TOTP already registered in an authenticator app:
      `demo-poweruser@…` (group `compass-poweruser`) and `demo-viewer@…`
      (group `compass-viewer`). RUNBOOK §6.
- [ ] Browser window A (normal): logged OUT, at the app login page. Browser
      window B (separate profile/incognito): logged OUT. Terminal at repo root,
      font ≥ 16pt, `AWS_REGION=us-east-1`, helper env vars set:
      `API` (the HttpApi base URL), `RAW_BUCKET`, `VIEWER_TOKEN`/`POWER_TOKEN`
      left UNSET (tokens are obtained on camera).
- [ ] One full rehearsal timed within 30 seconds of plan. Screen resolution
      1920×1080, notifications off, single monitor recorded.

---
---

## 00:00 — Opening & environment attestation

**Presenter: Chief Enterprise Architect** · *HARD STOP 02:00*

*[Screen: the live Compass login page in browser window A — visibly a real URL
on a `cloudfront.net` domain. Terminal visible in a side pane at repo root.]*

> Good morning. This is the Satsyil team's technical demonstration for the ONR
> Code 08 Data and Analytics platform requirement. I'm the proposed Chief
> Enterprise Architect, and over the next forty-five minutes you will also hear
> from our proposed DevSecOps Engineer, Data Architect, Data Scientist, and Web
> Software Developer. Everyone narrating today is proposed Key Personnel on
> this contract, and everyone drives their own keyboard.
>
> Three facts about what you are about to see. First: this is a live,
> functioning cloud environment — a real AWS stack we call Compass, deployed
> from the repository on screen, and you will watch us provision, ingest,
> analyze, govern, and export against it in real time. No slides, and nothing
> pre-rendered. Second: every record in this system is synthetic. The grant
> portfolio is machine-generated mock data built to resemble a command S&T
> registry — there is no CUI, no PII, and no real award anywhere in this
> environment, and the repository carries a manifest proving that. Third: we
> will execute all seven scenario elements in order, and address all five
> strategic prompts as we go — we'll flag each one by name as we reach it.
>
> The platform models the workload in Exhibit B: a scalable analytics
> environment, row-level security for a distributed user hierarchy, automated
> pipelines, AI/ML that inherits the platform's access controls, and an
> automation-first operating posture. Two Exhibit B requirements most
> platforms treat as paperwork — automated defense against mass data
> extraction, and RMF artifacts generated from the infrastructure code itself —
> are built into what you'll see, and we will demonstrate both live.
>
> Let's begin with the front door. Over to our DevSecOps Engineer.

---

## 02:00 — Element 1: Secure Access, Authentication, and Zero Trust

**Presenter: DevSecOps Engineer** · *HARD STOP 07:00*
*(L 11.3 Element 1 — MFA, identity provider, DoD Zero Trust alignment; begins
Prompt (c).)*

*[02:00 — Screen: terminal.]*

> Before anyone logs in, let me show you what an unauthenticated caller gets.
> This platform's API is deny-by-default: every route sits behind a JSON Web
> Token authorizer, and there are no exceptions in the route table.

*[Type — and read the output aloud:]*

```bash
curl -si $API/dashboard | head -3
```

> No token — 401, unauthorized. Not a redirect, not a partial page: the gateway
> refuses the request before any of our code runs. That's the first Zero Trust
> principle on display: never trust, always verify, on every single request.

*[02:45 — Switch to browser window B (the separate profile). Navigate to the
app; click Sign in; authenticate as `demo-viewer@…`: password, then the TOTP
prompt. Narrate while typing:]*

> Now the front door. Identity is an OIDC identity provider — Amazon Cognito
> here — with multi-factor authentication set to ON, not optional, TOTP
> software tokens only, and a sixteen-character minimum password policy.
> Self-signup is disabled; accounts are provisioned by an administrator, which
> mirrors how ICAM-governed accounts work. Here is the second factor —
> *[enter TOTP code]* — and I'm in as our first persona: a program-office
> **viewer** assigned to Code 30. In production this same OIDC seam is where
> CAC-backed Navy ICAM federates in — the application trusts the identity
> provider's tokens, so swapping Cognito for an approved IdP is a
> configuration change at this seam, not a rebuild.

*[03:45 — In window B, open the dashboard. Point at the org-unit chart and
the KPI row.]*

> Look carefully at what this viewer can see: every number on this dashboard is
> scoped to Code 30. That's not a front-end filter. The access token carries
> the user's groups; the API derives the org unit from those claims; and the
> database itself enforces row-level security on the curated grants table —
> the policy is keyed to the org context that's bound inside each transaction.
> The application never writes a WHERE clause for this; the database will not
> hand back another code's rows, even to buggy or malicious application code.
> We'll prove the enforcement is in the database layer, not the UI, when we
> get to exports in Element 7.

*[04:30 — Switch to browser window A. Sign in as `demo-poweruser@…` with
password + TOTP, briskly. While typing:]*

> Second persona: a corporate-level power user — ONR-Corporate — whose policy
> branch reads across all codes. Same MFA ceremony, no shortcuts.

*[05:00 — In window A, open the same dashboard; the totals are visibly larger.
Then show identity explicitly in the terminal:]*

```bash
curl -s $API/me -H "Authorization: Bearer $POWER_TOKEN" | python3 -m json.tool
```

*[Set `POWER_TOKEN` by copying the session's access token per the rehearsed
step; keep it brisk.]*

> Same platform, same URL — the full portfolio this time. And `/me` shows you
> exactly what the platform believes about me: my role and my organizational
> unit, derived from the token's group claims. Every downstream authorization
> decision flows from these two fields.

**[CUT LINE — if behind schedule, jump to 05:30 narration now.]**

*[05:30 — Prompt (c), part 1. Stay on the dashboard; speak to camera.]*

> This is also the start of our answer to **Strategic Prompt (c) — Zero Trust
> and cybersecurity compliance at the IL4/IL5 baseline** — and I want to name
> the principles precisely. **Least privilege:** the application's database
> role is a deliberately unprivileged, non-owner role — it cannot create
> objects, and it cannot even read the dollar-amount column, which is revoked
> at the column level; entitlement to money data is a database grant, not an
> if-statement. **Continuous authorization:** access tokens live for one hour,
> every API call is re-verified at the gateway, and the org context is re-bound
> inside every database transaction — nothing is trusted because it was
> trusted a moment ago. **Micro-segmentation:** all data-touching compute runs
> in private subnets with no inbound path; the database accepts port 5432 from
> exactly one security group and nothing else; and the only ways in from
> outside are TLS edges — CloudFront behind a web application firewall for
> the UI, and the token-guarded API. My colleague will complete this answer in
> Element 2, because the rest of it lives in the infrastructure code — which
> is exactly where it should live.

---

## 07:00 — Element 2: Infrastructure as Code (IaC) and Automation

**Presenter: DevSecOps Engineer** · *HARD STOP 13:00*
*(L 11.3 Element 2 — live walk-through of how the environment was provisioned;
completes Prompt (c); demonstrates the RMF-as-code differentiator.)*

*[07:00 — Screen: terminal, full screen, at the repo root.]*

> Element 2: how this environment exists. The answer is one declarative
> template under version control. Everything you have seen and will see —
> network, database, identity, API, functions, pipeline, edge, encryption,
> WAF — is defined in a single CloudFormation-based SAM template, deployed by
> the AWS SAM toolchain. Let me show you, live.

*[Type each command; let output render; narrate over it:]*

```bash
git log --oneline -5
```

> Real history, real commits — this repository is the environment's source of
> truth.

```bash
grep -c "Type: AWS::" template.yaml && wc -l template.yaml
```

> Several dozen resources, one file. VPC and subnets, Aurora PostgreSQL,
> Cognito with MFA ON, the HTTP API with its JWT authorizer as the default,
> every Lambda function, the Step Functions pipeline, S3, Kinesis, CloudFront,
> the customer-managed KMS key, and the WAF — all in-template, which is why
> the whole platform stands up from a clean account with two deploy commands.

```bash
sam validate --lint
```

> Static validation and linting — the same gate a pipeline runs. Our delivery
> approach is that no change reaches an environment except through these
> stages: validate, build, deploy, from a reviewed commit. What you're
> watching here are exactly those stages run by hand so you can see them; in
> the Government's NRE/NRDE landing zone the same stages run from the CI/CD
> service the environment provides, with SAST, dependency, and infrastructure
> scanning wired into the same pipeline — automation-first, per Exhibit B.

*[08:45 — Database as code:]*

```bash
ls db/migrations/ && grep -n "FORCE ROW LEVEL SECURITY" db/migrations/002_rls.sql
```

> The database schema is code too — numbered, idempotent migrations applied by
> a migrator function that lives inside the VPC, because the database has no
> public endpoint. And this grep is the single most load-bearing line in the
> security story: row-level security is *forced*, which in PostgreSQL means
> even a table owner cannot bypass it. The migrator owns the tables; the
> application runs as a separate non-owner role. That separation is what makes
> the RLS you saw in Element 1 real rather than decorative.

**[CUT LINE — if behind schedule, jump to 10:00 now.]**

*[09:30 — Optionally show the two-deploy parameter flow:]*

```bash
head -30 samconfig.toml
```

> Deployment configuration is versioned alongside the template — including a
> second, isolated `dev` stack configuration we'll come back to in the
> disaster-recovery answer.

*[10:00 — The differentiator: generate the RMF artifact live.]*

> Now the part of Exhibit B most platforms handle with a Word document. The
> baseline requires technical RMF artifacts — ports, protocols and services,
> topology — to be **auto-generated from the IaC repositories**, so eMASS
> reflects the true state of the environment. Compass does exactly that, and
> I'll run it right now.

```bash
python3 src/functions/rmf_artifact/app.py -o /tmp/pps-topology.md && head -40 /tmp/pps-topology.md
```

*[Open `/tmp/pps-topology.md` in the editor; scroll steadily through the PPS
tables, the topology section, and the control-mapping table while narrating:]*

> This generator parsed the same template that provisioned the environment and
> produced, deterministically — no language model involved, same input gives
> byte-identical output — a Ports, Protocols and Services registration table
> split into boundary-crossing, internal, and outbound flows; the outbound
> table is derived from the IAM actions each function is actually granted, so
> a dependency the template doesn't authorize cannot appear, and one it does
> authorize cannot be omitted. Below that: a network topology diagram built
> from the parsed resources, the data-protection and identity inventories, and
> a candidate NIST 800-53 control mapping where every row cites the template
> property that evidences it. Note the artifact stamps the template's SHA-256,
> and — just as important — it ends with a section titled "what this artifact
> cannot assert." Evidence, not decoration. Because it regenerates on every
> change, the security documentation cannot drift from the infrastructure:
> that is continuous compliance as a property of the delivery system.

*[11:45 — Prompt (c), part 2. To camera:]*

> Completing **Strategic Prompt (c)**: in a DoD IL5 hosting environment this
> same template deploys into the Government-furnished landing zone —
> boundary and tenancy are Government-provided under the shared responsibility
> model, and everything you've seen remains our responsibility inside it.
> Micro-segmentation is what I showed you: private subnets, one-way
> security-group references, deny-by-default at every entry point, and a
> data layer that enforces row- and column-level policy itself.
> Least-privilege boundary configuration is per-function IAM scoped to named
> resources, a non-owner database role, and a customer-managed KMS key with
> rotation enabled over the database, both buckets, the stream, and the
> database secret. Continuous compliance is the artifact you just watched
> generate from the template, regenerated on every change, plus STIG and
> vulnerability scanning stages in the same pipeline in production. This demo
> runs in a commercial region configured to those baseline equivalents, as the
> solicitation directs — and because it is all declarative code, the IL5
> deployment is the same code, different landing zone.

---

## 13:00 — Element 3: Automated Ingestion, Data Operations, and Streaming

**Presenter: Data Architect** · *HARD STOP 19:00*
*(L 11.3 Element 3 — ingest a raw/semi-structured mock grants registry;
automated detection, quality checks, schema variation; streaming; weaves in
Prompt (a).)*

*[13:00 — Screen: split — terminal left, browser window A on the Ingest page
right. The stream ticker at the top of the page is visibly moving.]*

> Element 3: data operations. I'm going to ingest three raw files into this
> platform, live — a clean one, one in a legacy system's export format, and
> one with deliberately bad rows — and you'll watch the pipeline make three
> different decisions with no human in the loop.
>
> The mechanics: dropping a file into the landing bucket emits an event;
> an event rule starts an express Step Functions workflow — land and
> normalize, then a quality gate, then either curate or quarantine. The
> pipeline stages exchange only a small manifest — batch id, run id, counts —
> so payload size can never break orchestration. First file: a clean batch of
> forty mock grants.

*[Type:]*

```bash
aws s3 cp seed/drops/drop_good.json s3://$RAW_BUCKET/drops/
```

*[13:50 — Refresh the Ingest page; the new batch appears; open its quality
panel when it lands as curated. Narrate the rule rows:]*

> There it is — detected automatically, no poll, no cron, no button. The
> quality gate ran the rule set — required fields, type checks, value ranges,
> duplicate award numbers — every rule reporting rows passed and failed, and
> the batch score is displayed with its formula, not as a mystery number.
> Forty of forty rows passed; the batch is curated and those grants are now
> live in the portfolio you saw on the dashboard.
>
> Second file — and this one matters for any command with legacy exporters.
> Same grants, but shaped the way a real legacy reporting system would emit
> them: columns renamed — `award_id` for the grant number, `fy` as a string
> like "FY2026", dollar amounts with currency signs and commas — plus an
> extra column our schema doesn't want.

```bash
aws s3 cp seed/drops/drop_compatible_variant.json s3://$RAW_BUCKET/drops/
```

*[14:50 — Refresh; when it lands, show it curated with the same pass profile:]*

> The normalizer recognized the variant, mapped every renamed column back to
> the canonical schema, parsed the typed values, dropped the stray column, and
> the same quality gate passed it. Schema variation is handled as a mapping
> concern at the edge — the core pipeline is parameterized, exactly the
> modular, parameterized pipeline architecture Exhibit B calls for, so a new
> source format is an adapter, not a rebuild.
>
> Third file: sixty rows where fifteen are deliberately defective — missing
> org units, negative dollar amounts, a duplicate award number, a fiscal year
> of 1998, values of the wrong type.

```bash
aws s3 cp seed/drops/drop_incompatible_bad.json s3://$RAW_BUCKET/drops/
```

*[15:45 — Refresh; the batch shows quarantined. Open its quality panel:]*

> Seventy-five percent pass rate — below the ninety-percent gate — so the
> pipeline held the entire batch: nothing was curated, every row is retained
> in the landing zone with its per-rule verdict, and a batch anomaly was
> raised for a data steward. Bad data cannot leak into the analytics tier,
> and nothing is silently dropped — quarantine is a visible, auditable state.

**[CUT LINE — if behind schedule, jump to 16:30 now.]**

*[16:15 — Point at the stream ticker and the velocity badges on the page:]*

> And the streaming layer: this ticker is fed from a Kinesis data stream —
> Kafka-equivalent, managed — with a producer publishing pipeline activity
> continuously. The platform supports the three ingestion velocities in
> Exhibit B, and the interface labels each batch with its velocity: scheduled
> batch, like a nightly ERP pull; interval micro-batch; and on-demand — a
> user-triggered live refresh, which is precisely what I did three times just
> now from the command line, and which any authorized power user can do from
> this page.

*[16:30 — Prompt (a). To camera, over the Ingest page:]*

> Which brings me to **Strategic Prompt (a) — sustainment of the legacy
> footprint**. Our approach is strangler-fig modernization with the legacy
> estate treated as a production system, never a demolition site. Concretely,
> in phases. Phase one: assume operation of the current D&A Portal
> application, reporting systems, databases, and the existing ETL pipelines
> exactly as they run today — same schedules, same outputs — under our
> monitoring, with runbooks and SLOs, changing nothing. The variant file you
> just watched is the technical proof of phase two: the modern platform
> ingests legacy exports *as they are*, renamed columns, typed quirks and all,
> so both systems run in parallel on the same data with zero change demanded
> of the legacy side, and reports are reconciled between old and new until the
> numbers agree over an agreed soak period. Phase three: consumers cut over
> workload by workload behind stable interfaces, each cutover reversible,
> and a legacy pipeline is retired only after its replacement has run clean
> through a full reporting cycle. Zero service degradation is not a slogan —
> it falls out of never asking the legacy system to change, and never cutting
> over without a parallel run and a way back.

---

## 19:00 — Element 4: Data Governance, Quality, and Cataloging

**Presenter: Chief Enterprise Architect** · *HARD STOP 24:00*
*(L 11.3 Element 4 — catalog, metadata, quality scores, end-to-end visual
lineage.)*

*[19:00 — Screen: browser window A → Catalog page.]*

> Element 4: governance. This is the platform's data catalog — the registry of
> every dataset the platform holds: the curated grants portfolio, the landing
> zone, the analytics outputs, and the commercial data feeds you'll see in
> Element 6. For each entry: ownership, freshness, record counts, and — front
> and center — a data quality score. One thing to notice about that score —
> *[hover/click the score chip]* — it is shown **with its formula**. It is
> computed from the same per-rule pass and fail counts the quality gate wrote
> during the ingests my colleague just ran, so the catalog can never disagree
> with the pipeline: they are reading the same ledger. A health score nobody
> can explain is theater; this one is arithmetic you can check.

*[20:15 — Click into the curated grants dataset → lineage view. The lineage
graph renders. Trace it left to right with the cursor:]*

> And here is end-to-end lineage, visually mapped: source file, landing zone,
> normalization, the quality gate with its score, the curated table, the topic
> model run, and the dashboard tier that consumes it. The important thing
> about this graph is where it came from. Nobody drew it. Every node and every
> edge was **emitted by the pipeline run itself** and stored as lineage
> records at execution time — you can see the run identifier on the graph
> matches the batch my colleague ingested minutes ago. Documentation of the
> data flow that is generated by the data flow — the same design conviction as
> the RMF artifact in Element 2: the description of the system falls out of
> the system, so it cannot drift.

**[CUT LINE — if behind schedule, jump to 22:45 now.]**

*[21:45 — Briefly open the lineage for the quarantined batch:]*

> Lineage exists for the failed batch too — it ends at the quarantine node
> with the gate's score on the edge. Negative provenance — being able to show
> an auditor exactly where bad data stopped — is as much a governance feature
> as positive provenance.

*[22:45 — Wrap the element:]*

> Metadata capture, explainable quality scoring, and machine-generated lineage
> from raw file to visualization tier: that is the governance layer, and none
> of it depends on a human remembering to update a wiki. Now — what the
> platform does with governed data. Our Data Scientist.

---

## 24:00 — Element 5: Decision-Support Analytics and Modeling

**Presenter: Data Scientist** · *HARD STOP 30:00*
*(L 11.3 Element 5 — trigger and execute an analytical/ML routine live; show
structured outputs and decision support; weaves in Prompt (b).)*

*[24:00 — Screen: browser window A → Analytics page. Click **Run analysis**
immediately so the model runs while narrating.]*

> Element 5. I've just triggered a live analytical run against the portfolio —
> including the eighty grants ingested minutes ago — and while it executes,
> let me tell you exactly what it is, because we believe evaluators deserve
> the algorithm, not adjectives. This is unsupervised topic modeling over the
> full text of every grant title and abstract: TF-IDF vectorization, then
> non-negative matrix factorization, seeded and deterministic — the same
> corpus and parameters reproduce the same run, which is what makes an
> analytical result auditable. Alongside it, a statistical anomaly screen
> z-scores every award amount within its program area to flag outlier funding.
> This is our own documented implementation — transparent linear algebra, and
> the unit tests ship in the repository.

*[25:00 — Results render. Walk the topic list:]*

> Done — seconds, on live data. Eight discovered themes, each with its top
> terms, its weight, and — the part leadership actually uses — a fiscal-year
> trend. *[Open the trend chart for the top emerging topic.]* The trend is
> computed as each topic's **share within its fiscal year**, so growth is
> real concentration shift, not an artifact of the portfolio simply adding
> more grants each year. This topic's share has grown across the trailing two
> years — that is an emerging investment area, detected from raw abstracts
> with no manual tagging.

*[26:00 — Open the anomaly flags panel:]*

> The anomaly screen flagged these awards as funding outliers relative to
> their program area — each with its z-score, severity, and a plain-English
> reason. These flow into the workflow queue you'll see in Element 6, so a
> flag becomes a routed decision, not a forgotten chart.

*[26:40 — Show the recommendation panel:]*

> And the run ends in a sentence, not just a matrix: a recommendation derived
> from the numbers — which topic is emerging, how fast its share is growing,
> how many anomalies need review — stored with the run, alongside its
> parameters and metrics, in a model registry table. Every run is versioned
> and reproducible; that is the governance spine that MLOps re-training and
> drift monitoring bolt onto, per the Exhibit B model-sustainment workload.

**[CUT LINE — if behind schedule, jump to 27:45 now.]**

*[27:00 — One decision-support beat on the dashboard link:]*

> Strategic decision aid, concretely: a portfolio lead asking "where is the
> field moving, and are we funding it?" gets: this topic is accelerating,
> these codes hold the grants, these two awards are funding outliers worth a
> look. That's a resourcing conversation, prepped by the platform in seconds.

*[27:45 — Prompt (b). To camera:]*

> **Strategic Prompt (b) — financial and budgetary analytical integration.**
> Everything you just watched is domain-portable, and finance is where we'd
> point it first. The ingestion tier treats financial ERP extracts exactly
> like the legacy variant file in Element 3 — mapped, typed, quality-gated,
> so obligation and expenditure data arrives clean and auditable.
> For **execution tracking**: the same anomaly machinery that z-scored award
> amounts monitors obligation and burn rates against plan by appropriation,
> program, and fiscal year — the dashboard you'll see next already carries a
> budget-execution view over the mock portfolio. For **predictive** support:
> trend decomposition over execution history to project year-end positions
> and flag lines trending toward under- or over-execution while there is
> still time to act inside the fiscal year. For **prescriptive** support:
> recommendation outputs like the one on screen, ranking candidate
> reallocations against command resourcing priorities — the platform drafts
> the option space, and leadership decides. And the team behind it is on this
> recording: myself on models, the Data Architect on the financial data
> foundation, working inside the governance you've already seen — because a
> budget number nobody can trace is a number nobody will defend. That is
> cost optimization as an analytical practice: find it early, explain it,
> route it to a decision.

---

## 30:00 — Element 6: Unified Dashboard, Visualizations, and Process Automation

**Presenter: Web Software Developer** · *HARD STOP 36:00*
*(L 11.3 Element 6 — executive BI for a non-technical leader; automated
summaries, approval routing, anomaly flagging; weaves in Prompt (e).)*

*[30:00 — Screen: browser window A → Dashboard.]*

> Element 6: the view a leader actually opens. One page, one round trip —
> the API assembles every KPI and every chart series server-side, so this
> renders fast and reads as one coherent picture: portfolio value, award
> counts, funding by program area, awards by code, budget execution, the
> quality trend from the ingests you watched, and topic concentration from
> the run my colleague just executed. Everything a non-technical user does
> here is point and click: filter, hover for exact values, drill.

*[30:45 — Point at the executive summary block:]*

> The narrative summary at the top was generated by the platform — an
> automated summary over these same numbers, produced by an AI model running
> **inside the cloud boundary**, and it regenerates as the data changes.
> Which sets up the feature I want to spend a minute on.

*[31:15 — Ask Compass. Type the question live:]*

> Natural-language Q&A over the governed portfolio.

*[Type into Ask Compass: **"Which program area is growing fastest, and who are
the top awardees in it?"** — submit; read the key line of the answer aloud.]*

> Retrieval-augmented answering: the platform embeds the question, retrieves
> the most relevant grants by vector similarity **from the curated table,
> under this user's row-level security context**, and only then asks the
> model to answer, from those retrieved records. Two properties matter.
> In-boundary: both the embedding model and the chat model are AWS Bedrock
> services invoked inside the environment — no data leaves for any public AI
> API, which is the AI trust posture Exhibit B requires. And
> policy-inheriting: a Code-30 viewer asking this exact question gets an
> answer computed only from Code-30 rows, because retrieval runs under the
> same database policies as every other query. The AI cannot leak what the
> user cannot read.

*[32:45 — Process automation: open the anomaly workflow panel; click one
anomaly → Request review; switch briefly to the approvals view and approve it:]*

> Process automation, end to end: the funding outliers from Element 5 arrive
> here as a work queue. I take this flagged award, route it for review — and
> as the power user I approve it, with a note. Flag, route, decide, done —
> and every state change writes the audit trail. Repetitive workflow the
> platform runs itself; judgment stays human.

**[CUT LINE — if behind schedule, jump to 33:45 now.]**

*[33:30 — Navigate to the Licenses page:]*

> One more automation surface, and it answers a strategic prompt directly.

*[33:45 — Prompt (e). Over the Licenses page, pointing at rows:]*

> **Strategic Prompt (e) — data vendor and lifecycle management.** This is the
> platform's commercial data subscription registry: eight mock vendor
> licenses — bibliometric, patent, company-intelligence feeds — each with its
> entitlements, seat utilization, renewal date, and owning team. The platform
> watches the renewal horizon: these subscriptions *[point at the flagged
> rows]* renew within forty-five days and are flagged automatically — surfaced
> here and on the executive dashboard, so a renewal becomes a routed approval
> through the workflow you just watched, months before it becomes an outage.
> Critically, every license is linked to the **datasets** it feeds, and those
> datasets are catalog entries with lineage — so before anyone lets a
> subscription lapse, the platform answers "which pipelines and which
> dashboards go dark if this expires," by traversal, not by memory. That
> dependency mapping is how you manage renewals **without data gaps in
> critical dashboards**. Quality compliance rides the same rails as
> everything else: vendor feeds land through the Element 3 quality gate, so
> a degrading feed shows up as a falling score on its catalog entry — which
> is contract-management evidence at renewal time. Methodology in one line:
> subscriptions are governed data, in the same catalog, quality, lineage, and
> workflow machinery as the mission data they feed.

---

## 36:00 — Element 7: Interoperability, Data Portability, and Secure Export

**Presenter: Chief Enterprise Architect** · *HARD STOP 41:00*
*(L 11.3 Element 7 — secure bulk export in non-proprietary formats, open
schemas/APIs, no vendor lock-in; demonstrates the aggregation-guard
differentiator.)*

*[36:00 — Screen: browser window A (power user) → Export page.]*

> Element 7: getting data out — because a platform that hoards data is a
> platform you're locked into. Filtered export, live: fiscal years 2025 and
> 2026, CSV.

*[Set the filters; run the export; the file downloads via a presigned link.
Open the CSV briefly in a text editor — show the header row.]*

> Plain, non-proprietary CSV — column-headed, tool-agnostic; the same request
> serves JSON, and parquet for columnar consumers. *[Run the same filter as
> JSON; show the response metadata briefly.]* Notice the export carries its
> own provenance: generated-at, the applied filters, row counts, and its
> classification note. Every export also lands in the immutable audit log —
> we'll look at that in a moment.

*[Stage note — parquet: if pyarrow was enabled at deploy (preflight), run the
parquet export and say: "and parquet, natively." If it was NOT enabled, either
skip parquet entirely or show the honest response note — the API returns CSV
and states the parquet layer is not installed. Do not claim parquet bytes that
were not produced.]*

*[37:15 — The guard. Clear the filters; request the full portfolio:]*

> Now the control this platform is proudest of, and the second Exhibit B
> requirement I flagged at the top: defense against **mass extraction** — the
> aggregation risk. This system holds roughly five hundred curated grants,
> and for this recording the extraction threshold is set to two hundred fifty
> rows so you can watch the control fire on real data — that's a deploy-time
> parameter, five thousand by default. I'm now requesting the entire
> portfolio, unfiltered.

*[Submit. The 428 response renders. Read it:]*

> Refused — HTTP 428: the filter matched about four hundred eighty rows,
> over the threshold, so the platform demands an approval before this much
> data leaves in one pull. Three details make this a real control and not a
> speed bump. It counts the rows the **filter matched**, not the page size —
> you cannot page your way underneath it. The refusal names a **fingerprint
> of this exact query** — approving it authorizes this specific extraction,
> for this org, in this shape; it is not a standing license to bulk-export.
> And this refusal is already in the audit log.

*[38:15 — Clear it through the approval workflow: request approval for the
returned subject id; approve it as the power user; re-run with the token:]*

> So: I request approval for that fingerprint, the approving authority — me,
> wearing the approver hat, as recorded by the workflow — approves it, and I
> re-run the same export with the approval token attached. *[The full export
> succeeds.]* Delivered — and the guard block, the approval, and the release
> are now three linked entries in the audit trail. *[Open the audit trail
> panel; point at the sequence.]* Blocked, approved, released — with actor,
> timestamp, and the query fingerprint on each. The audit row is written
> before bytes leave; the trail can over-record but never under-record.

**[CUT LINE — if behind schedule, jump to 39:45 now.]**

*[39:00 — RLS/CLS proof in the export path. Switch to browser window B — the
still-signed-in viewer — Export page:]*

> And the promise from Element 1, kept in the riskiest path. Same export
> screen, viewer persona. The rows: only Code 30 — row-level security,
> enforced by the database inside the export query itself. The columns:
> watch what happens when the viewer asks for the dollar amount. *[Request an
> export including `amount_usd`.]* Refused, 403 — column-level security. Not
> silently dropped: refused, explicitly, because a column you quietly omit is
> a governance bug you'll never find. Filtering **on** the hidden column is
> refused for the same reason — otherwise you could binary-search a value you
> aren't entitled to read.

*[39:45 — Open `$API/openapi.json` in a tab (authenticated request):]*

> Finally, interoperability by contract. The platform serves its own OpenAPI
> 3.1 document — from the running API, not a wiki — so any enterprise
> platform, Advana or Cloud One included, integrates against a published,
> versioned contract: token-authenticated HTTPS, JSON in, JSON or bulk files
> out, non-proprietary formats end to end. And beneath the API: the store is
> standard PostgreSQL, schema versioned in this repository as plain SQL, and
> exports are CSV, JSON, and parquet. Interoperability posture in one
> sentence: portable data, standard contracts, replaceable adapters — leave
> the platform any day with your data, your schema, and your history. That is
> the opposite of lock-in.

---

## 41:00 — Strategic Prompt (d): Disaster Recovery, Resilience, and Failover

**Presenter: DevSecOps Engineer** · *HARD STOP 43:30*
*(Dedicated narrated address, as L 11.4 permits. On-screen evidence, no
slides.)*

*[41:00 — Screen: terminal — `template.yaml` open at the VPC/subnet block;
scroll slowly to the Aurora block, then `samconfig.toml` `[dev]` section,
while narrating:]*

> Strategic Prompt (d) — continuity, in three parts, with the evidence on
> screen.
>
> **Objectives.** For a platform of this class we commit to a Recovery Point
> Objective of **fifteen minutes or better** — Aurora's continuous backup with
> point-in-time recovery makes the achievable RPO minutes, not hours — and
> tiered Recovery Time Objectives: **one hour** for the critical read path —
> dashboards and reporting — and **four hours** for full platform
> functionality including ingest and analytics. Those targets are grounded in
> the architecture you're looking at, and we validate them by drill, not by
> assertion.
>
> **Availability patterns.** What's on screen: every tier is either stateless
> or managed-multi-AZ. Two availability zones across public and private
> subnets; Aurora with a multi-AZ topology and automated failover under a
> stable endpoint; compute is serverless functions with no state to lose;
> the UI is served from edge-replicated storage; and the data plane is
> encrypted and continuously backed up. And the deepest pattern is Element 2
> itself: because the entire environment is one declarative template plus
> versioned migrations plus seedable data, **region-loss recovery is a
> redeploy** — the same two commands you watched, pointed at a recovery
> region, then restore the database from backup. One honest note, in the
> spirit of this whole demonstration: this demo stack carries two
> cost-conscious settings a production deployment changes — one NAT gateway
> instead of one per AZ, and short backup retention; both are one-line
> parameter changes in the template, and the production baseline sets
> per-AZ egress and thirty-five-day point-in-time retention.
>
> **Non-disruptive annual exercises.** *[Point at `[dev]` in samconfig.]*
> The deploy configuration you're looking at already defines a second,
> fully isolated stack of this same template. Our annual DR exercise deploys
> exactly that: a parallel environment in the recovery region, database
> restored from production backups to a point in time, the full seven-element
> workflow you watched today executed against it as the validation script,
> RTO and RPO measured against the commitments I just stated, results
> written into the continuity plan, exercise stack torn down. Production is
> never touched — zero disruption, by construction, and the exercise is
> cheap enough to run more than annually.

---

## 43:30 — Close

**Presenter: Chief Enterprise Architect** · *HARD STOP 44:30*

*[43:30 — Screen: browser window A → Dashboard.]*

> Let's land it. In one unedited take, on a live cloud environment, you
> watched all seven scenario elements in order: MFA'd Zero Trust access with
> database-enforced row and column security; the environment provisioned from
> one version-controlled template, generating its own RMF evidence; live
> ingestion that curated clean data, normalized a legacy format, and
> quarantined bad rows; a catalog with explainable quality scores and
> machine-generated lineage; a deterministic, documented analytical model
> turning raw abstracts into decisions; an executive surface with in-boundary
> AI, automated summaries, and routed approvals; and governed bulk export in
> open formats — including watching the platform refuse a mass extraction,
> then release it under audited approval. And all five strategic prompts,
> answered by name by the Key Personnel who will do this work.
>
> On agility, one closing thought: everything that made this demonstration
> possible on synthetic data — declarative infrastructure, adapters at the
> edges, portable data, contracts published by the running system — is the
> same property that lets this platform absorb a new data source, a new
> mission workload, or a new hosting environment without a rebuild. That is
> the platform, and the team, we're proposing to bring to ONR. Thank you.

*[STOP RECORDING. Target elapsed: 44:30. Ceiling: 50:00.]*

---

## After the recording

1. Watch the take end to end. Verify: all 7 elements sequential and complete,
   all 5 prompts explicitly named, no dead air over 10 seconds, every claim
   matches what happened on screen.
2. Fill in the actual timestamps in `volume_iv/TIMESTAMP_INDEX.md`.
3. Upload per `volume_iv/SUBMISSION_LINKS.md` (private, password-protected
   link; test from a clean browser and a phone).
4. Complete `volume_iv/PRESENTER_MAPPING.md` with the recorded
   presenter-to-segment mapping.
5. Reset `ExportMaxRows` if the stack stays up for a live follow-on session
   (the Government reserves a 90-minute live validation session).
