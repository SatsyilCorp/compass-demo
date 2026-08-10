# Compass — Build & Integration Report

**Written by the integration review pass, 2026-08-10.** Audience: the person
who has to deploy this stack and record the demo. Brutally honest by design:
every claim below states whether it was *verified offline*, *fixed during this
review*, or *cannot be verified without a live AWS deploy*.

---

## 1. What was verified offline (all passing)

| Check | Result |
|---|---|
| `pnpm i && pnpm build` (Next.js 15 static export, strict TS) | **PASS** — 25 pages generated to `frontend/out/`, type-check clean |
| `python3 -m py_compile` over every `src/**/*.py` + `scripts/` | **PASS** |
| `sam validate --lint` on `template.yaml` | **PASS** ("valid SAM Template") |
| `ruff check src scripts` | **PASS** after fixing 2 unused imports; 9 cosmetic E741 warnings remain (`l` loop vars in `license/app.py`, `rmf_artifact/app.py`, `seed_data.py`) — style only, no behavior |
| `src/common/tests/smoke.py` (compass_common offline smoke) | **PASS** — "9 tests, fully offline" |
| `src/functions/analytics/tests/test_topic_model.py` | **NOT RUN here** — needs `numpy` + `pytest`, not installed on this machine. Pure-offline test; run `pip install numpy pytest` and `PYTHONPATH=src/functions/analytics pytest src/functions/analytics/tests/` to verify |
| Contract audit: all 16 CONTRACTS.md routes present in `template.yaml` AND implemented by a Lambda | **PASS** (after fix #1 below) |
| OpenAPI document (`export/openapi.py`) covers all 16 routes | **PASS** |
| State machine ↔ Lambda action contract (`fetch`/`validate`/`quarantine`/`persist`, `$.gate`, manifest fields) | **PASS** — field names line up end to end |
| Repo hygiene: hardcoded account IDs, secrets/keys, real emails/PII in seed data, localhost leaks | **CLEAN** — none found. Only `example.com` demo emails in RUNBOOK; `localhost:3000` appears only as documented dev defaults |

## 2. Integration defects found and fixed in this pass

These were real live-mode breakages (mock mode masked all of them, because the
mock fixtures are typed against `frontend/lib/types.ts` but the Lambdas were
not):

1. **`GET /dashboard` was wired to the wrong Lambda.** `template.yaml` routed
   it to `SummarizeFunction`, whose response shape (`as_of/org_unit/series{...}`)
   does not match the locked `DashboardResponse` contract the frontend renders.
   The purpose-built `src/functions/dashboard/` (which matches the contract
   exactly) was never referenced by the template — the phase-2 flag was
   correct. **Fixed:** added `DashboardFunction` (VPC, secret+KMS policies) and
   moved the `GET /dashboard` event to it; `SummarizeFunction` keeps
   `GET /anomalies` and the weekly-summary direct invoke.
   *Side effect to know:* the `?refresh=true` corporate summary-regeneration
   branch in summarize is no longer HTTP-reachable; the weekly summary is
   still generated via direct invoke `{"action":"weekly_summary"}`.
2. **`POST /chat` request/response field mismatch.** Frontend sends
   `{message}` and renders `res.model`; the Lambda required `question` and
   returned `model_id`. Every live chat call would have been a 400, and the
   model line would render `undefined`. **Fixed** in `rag_chat/app.py`:
   accepts `message` (with `question` as alias), returns both `model` and
   `model_id`.
3. **`GET /analytics/{run_id}` shape did not match `AnalyticsRunDetail`.**
   The stored `trend_jsonb` is a rich object (`{by_fy, window, growth_pct}`)
   but the contract's `Topic.trend` is `[{period, value}]` — the live
   analytics page would have crashed on `topics[0].trend.map`. Topics also
   lacked `grant_count` / `total_funding_usd`, and the run lacked `status`.
   **Fixed** in `analytics/app.py`: topics are reshaped to the contract
   (`trend` = per-FY dominant-grant counts, full model output preserved as
   `trend_detail`), `grant_count` computed, `total_funding_usd` summed via the
   CLS-guarded `grants_curated_corp` view for the corporate persona only
   (null/masked otherwise, inside a SAVEPOINT so a missing grant fails closed),
   `status: "completed"` added, `metrics.grants_scored` aliased from `n_docs`
   for the RecommendationPanel. POST now returns `status: "completed"`
   (was non-contract `"complete"`).
4. **Cognito callback URL mismatch.** The SPA's OIDC `redirect_uri` is
   `/login/` (react-oidc-context + `trailingSlash: true` static export) but
   the template registered `http://localhost:3000/callback` — live sign-in
   would fail with `redirect_mismatch` (there is no `/callback` page at all).
   **Fixed:** template registers `/login/` for callback and logout;
   RUNBOOK §3/§7 URLs corrected to `https://<CloudFrontDomain>/login/`.
5. **Hygiene scrub:** removed internal project names (`GovSentry`,
   `exim-eol-poc`) and `~/Documents/...` home-directory paths from
   code comments across template.yaml, frontend components, and Lambda
   docstrings (replaced with generic provenance wording). "Satsyil Corp"
   UI branding is intentional and retained. Re-verified with grep: clean.
6. Removed 2 unused imports (ruff F401) in `rag_chat/rag.py`,
   `rag_chat/retrieval.py`.

All fixes re-verified: `py_compile`, `sam validate --lint`, and a full
`pnpm build` pass after the changes.

## 3. Response-shape audit (live Lambda vs. frontend contract)

Verified by reading both sides, route by route:

| Route | Verdict |
|---|---|
| `GET /me` | Match (`sub/email/display_name/role/org_unit/groups`) |
| `GET /catalog` | Match + extras (formula/masking metadata — additive, safe). Note: `quality_score` can be **null** for a batch with no recorded gate run; the TS type says `number`. UI renders it through a score chip — cosmetic risk only |
| `GET /catalog/{id}/lineage` | Match (`run_id/nodes/edges`, honest empty graph + `note` when none recorded) |
| `POST /ingest/simulate` | Match; returns 202 (fetch wrapper accepts any 2xx) |
| `GET /ingest/status` | Match (`batches[]` with quality rules, overall_score, origin) |
| `GET /stream/recent` | Match (`records[]` + `source: kinesis|database`) |
| `POST /analytics/run`, `GET /analytics/{run_id}` | Match **after fix #3** |
| `GET /dashboard` | Match **after fix #1** (dashboard/app.py mirrors `DashboardResponse` field-for-field, Decimal→float coercion included) |
| `POST /chat` | Match **after fix #2** |
| `GET /anomalies` | Match + extras (`summary/filters`); served by SummarizeFunction per template (approvals/app.py contains a second, richer implementation — unrouted, documented as such in its docstring) |
| `POST /approvals` | Match (`{approval: {...}}` + `approval_token` — the token feeds /export guard clearing) |
| `GET /licenses` | Match + extras (`alerts/summary/thresholds` — additive) |
| `POST /export` | Match (`export_id/row_count/format/download_url/audited`); 428 body matches `ExportApprovalRequiredBody` exactly |
| `GET /openapi.json` | Served OpenAPI 3.1 with all routes |

Mock fixtures are typed against the same `lib/types.ts` and compile under
strict TS, so mock ⇄ live shape parity holds wherever the table above says
Match.

Known cosmetic seam (not fixed, low risk): several Lambdas serialize
timestamps via `json.dumps(default=str)`, which renders Python datetimes as
`"2026-08-10 19:56:47+00:00"` (space, not ISO-8601 `T`). Fields the UI parses
with `new Date()` may misparse in stricter engines (Safari). Where the code
explicitly calls `.isoformat()` (catalog, approvals, licenses, stream ticks)
this is a non-issue; dashboard/analytics/summarize rows rely on `default=str`.
If a date renders "Invalid Date" during rehearsal, this is why.

## 4. What still needs a live AWS deploy to verify

Nothing below can be validated offline; all of it is exercised only by a real
deploy + the RUNBOOK smoke checks:

- Aurora provisioning, the migrator run (`001_schema` + `002_rls`), the
  `GRANT compass_app TO CURRENT_USER` role bootstrap, and that
  RLS/CLS actually behave as designed under the two personas (the biggest
  demo claim — rehearse the persona switch explicitly).
- pgvector extension availability on Aurora PG 16.4 (`CREATE EXTENSION vector`).
- The intake state machine end-to-end (S3 → EventBridge → Express SFN →
  fetch/validate/persist), including the quarantine path with
  `drop_incompatible_bad.json`.
- Bedrock model access (`amazon.nova-lite-v1:0`, `amazon.titan-embed-text-v2:0`)
  — account-level opt-in required (RUNBOOK §0); chat/summary/embeddings all
  fail without it.
- Cognito Hosted UI + TOTP enrollment + the JWT authorizer round trip.
- CloudFront/OAC/KMS/WAF serving path and the path-rewrite function.
- Kinesis ticker (schedule → put_records → `GET /stream/recent` read path).
- `sam build --use-container` producing working arm64 layers
  (psycopg2-binary, numpy, PyJWT+cryptography) — a macOS-native build WILL
  produce broken layers (RUNBOOK troubleshooting covers it).
- Analytics runtime at real corpus size (offline unit tests exist but were
  not run here — no numpy on this machine).
- `/catalog/[id]` static params: the exported site pre-renders lineage pages
  for the **fixture** batch ids (or live ids if the API is reachable at build
  time). A live batch created *after* the frontend build (e.g. the three demo
  drops) has **no static page** → CloudFront 404 on `/catalog/<new-batch>/`.
  For the recording either (a) rebuild+resync the frontend after the demo
  drops are ingested, or (b) demo lineage from a pre-seeded batch. This is a
  real recording-day tripwire — plan for it.

## 5. Day-0 human steps to deploy (condensed; full detail in docs/RUNBOOK.md)

1. **Prereqs:** AWS admin creds (us-east-1 only — WAF is CLOUDFRONT scope),
   AWS CLI v2, SAM CLI, **Docker**, Python 3.11+, Node 20+, pnpm. Enable
   Bedrock model access for Nova Lite + Titan Embed v2 in the console.
2. `cp samconfig.toml.template samconfig.toml` (leave `Web*` empty).
3. `./src/functions/migrator/prepare_migrations.sh && sam build --use-container && sam deploy`
   (~20–30 min; capture stack outputs).
4. **Second deploy:** fill `WebCallbackUrl=https://<CloudFrontDomain>/login/`,
   `WebLogoutUrl=https://<CloudFrontDomain>/login/`,
   `WebOrigin=https://<CloudFrontDomain>` in samconfig; `sam deploy` again.
5. Migrate: `aws lambda invoke --function-name compass-demo-migrator
   --payload '{"migrate":"all"}' ...` — expect `001_schema`, `002_rls` applied.
6. Seed: upload `seed/grants_portfolio.json` to `s3://<RawBucket>/drops/`
   (pipeline curates it); load `seed/licenses.json` via the RUNBOOK §5 inline
   SQL snippet. **Do not** upload the three demo drops before recording.
7. Enroll `demo-poweruser@` / `demo-viewer@` (admin-create, set password, add
   to `compass-poweruser` / `compass-viewer` groups), then complete each
   account's **TOTP enrollment in the Hosted UI well before recording day**.
8. Frontend: `.env.local` with `USE_MOCK=false`, `AUTH_DISABLED=false`, the
   stack outputs, and both redirect URIs `= https://<CloudFrontDomain>/login/`;
   `pnpm build`; `aws s3 sync out/ s3://<WebBucket>/ --delete`; CloudFront
   invalidation.
9. Run `POST /analytics/run` once as poweruser so dashboard/analytics are
   populated; redeploy with `ExportMaxRows=250` so the 428 guard trips on
   camera; rehearse per `docs/DEMO_SCRIPT.md`.

## 6. Gaps & risks vs. the 7 elements / 5 prompts / Volume IV

**Coverage is genuinely complete on paper**: every L 11.3 element and L 11.4
prompt has running code, a route, a page, and a scripted segment
(`docs/ARCHITECTURE.md` §3 mapping, `docs/DEMO_SCRIPT.md`). Honest residuals:

- **Element 2 (IaC):** RMF artifact + migrator are direct-invoke only (per
  contract). The demo depends on the presenter driving them from a terminal —
  rehearse those two invokes; they have no UI fallback.
- **Element 3:** the "streaming" story is a 1-minute-scheduled Kinesis
  producer with an honest DB fallback labeled in the response (`source`).
  Fine, but don't narrate it as high-throughput streaming.
- **Element 5:** the topic model is transparent TF-IDF+NMF (deliberate,
  documented). `metrics.coherence` is not computed — the UI renders "—".
- **Element 6:** the exec summary on the dashboard page is computed
  client-side + `POST /chat` narrative; the richer Bedrock weekly summary in
  `summarize/` is direct-invoke only after fix #1. If the script promises "a
  stored Bedrock weekly brief on the dashboard", adjust either the script or
  re-route (`GET /dashboard/summary`) — currently it is NOT on the page.
- **Element 7:** parquet requires uncommenting pyarrow in
  `export/requirements.txt` + container rebuild (RUNBOOK §8). Without it the
  API honestly downgrades to CSV with a note — the script has a branch, but
  decide before recording which branch you're on.
- **Volume IV shells** (`volume_iv/*.md`) are templates with `[FILL]` fields —
  timestamps, presenter names, and links must be filled after recording; Key
  Personnel names must match Attachment 7 exactly.
- **Unrouted duplicate:** `approvals/app.py` also implements `GET /anomalies`
  (summarize's is the routed one). Both are real code; the docstring
  discloses the tie-breaker. Acceptable, but an evaluator reading the repo
  may ask — the answer is in the approvals docstring.
- **Not load-tested.** Nothing here has seen concurrency; Aurora min 0.5 ACU
  cold-resume may add seconds to the first query after idle. Warm the stack
  (load the dashboard, run one chat) minutes before recording.

## 7. Bottom line

The codebase is coherent, contract-conformant (after the four seam fixes
above), compiles/builds clean on all three toolchains that run offline, and
has no secrets/PII/hardcoded-account leakage. The four fixes in §2 were the
kind that only bite in live mode — which is exactly where the recording runs
— so a full live rehearsal (personas, ingest drops, analytics run, export
guard, chat) is **mandatory** before recording day. Budget one working day
for the first deploy + rehearsal loop.
