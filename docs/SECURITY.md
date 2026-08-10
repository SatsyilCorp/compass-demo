# Compass — Security Design

This document states what the demo stack enforces, **where each control lives
in code**, and — explicitly — what is a production-approach statement rather
than a demonstrated control. Companion: `docs/ARCHITECTURE.md` §10 (honest
deltas) and the generated RMF artifact (`src/functions/rmf_artifact/app.py`).

Threat framing (from Exhibit B): a platform aggregating command S&T,
financial, and operational data is a **high-value target**; the required
posture is a data-centric Zero Trust strategy at the application layer, with
aggregation-risk controls and immutable auditing. Compass is built to that
framing on synthetic data.

## 1. Zero Trust, mapped to mechanisms

| ZT principle | Mechanism in Compass | Where |
|---|---|---|
| Verify explicitly, every request | Cognito JWT authorizer is the **default** authorizer on the HTTP API — no route exists without it; 401 before any handler runs | `template.yaml` → `HttpApi.Auth` |
| Strong authentication | MFA **ON** (not optional), TOTP software tokens only; 16-char password policy; self-signup disabled (admin-create-only) | `template.yaml` → `UserPool` |
| Least privilege — compute | Per-function IAM statements scoped to named ARNs (secret, key, bucket prefixes, specific model IDs); no wildcard data access | `template.yaml` → each function's `Policies` |
| Least privilege — data | App runs as `compass_app`, a NOLOGIN, **non-owner** role; `SET ROLE` at connect; the role cannot create objects and cannot read `amount_usd` | `002_rls.sql`, `compass_common/db.py` |
| Continuous authorization | 1-hour access/ID tokens; JWT re-verified per request; org context re-bound **per transaction** via `SET LOCAL` (cannot leak across warm-connection reuse) | `template.yaml` → `WebClient`; `db.set_org()` |
| Micro-segmentation | All data-touching Lambdas in private subnets; DB security group admits 5432 **only** from the Lambda security group; DB not publicly accessible; egress only via NAT | `template.yaml` → SGs, subnets, `DbInstance` |
| Policy at the data layer | RLS + FORCE on `grants_curated`; the database refuses out-of-org rows regardless of application code | `002_rls.sql` |
| Assume breach / audit | Append-only `audit_log`; export allow-decisions written in the same transaction as the read; API access logs; X-Ray on all functions; state-machine logging ALL | `compass_common/audit.py`, `export/app.py`, `template.yaml` |

## 2. Row-Level Security — done so it is real

The three failure modes that make most RLS demos decorative are each closed:

1. **Owner bypass.** Postgres table owners bypass RLS *unless FORCE*. Compass:
   `ALTER TABLE grants_curated FORCE ROW LEVEL SECURITY` (`002_rls.sql`), and
   the runtime role is not the owner anyway — the migrator owns, the app runs
   as `compass_app`.
2. **Context leakage.** The org context is a per-**transaction** GUC
   (`SET LOCAL compass.org_unit`), set inside `db.set_org()` which opens a
   real transaction and discards the GUC on commit/rollback — it cannot bleed
   into the next request on a warm pooled connection.
3. **App-layer filtering.** There is no `WHERE org_unit = …` in application
   read paths; the policy
   (`org_unit = current_setting('compass.org_unit', true)` with an
   `ONR-Corporate` read-all branch) is the only row filter. A compromised or
   buggy handler still cannot read out-of-org rows.

Personas: `compass-poweruser` → `ONR-Corporate` (corporate branch, all rows);
`compass-viewer` → `Code-30` (own rows only). Group claims come from the
verified JWT; handlers map groups → role → org_unit.

## 3. Column-Level Security

`SELECT (amount_usd)` is REVOKEd from `compass_app`; the remaining columns are
granted explicitly (`002_rls.sql`). Powerusers read the dollar column through
the owner-owned `grants_curated_corp` view — FORCE RLS keeps the same row
policy in force through the view. Two deliberate behaviors in the export path
(`src/functions/export/app.py`):

- A viewer requesting `columns: ["amount_usd"]` gets **403**, not a silently
  dropped column — a filter/column the caller believes was applied but wasn't
  is treated as a governance bug.
- A viewer filtering `min_amount_usd`/`max_amount_usd` is also refused —
  filtering on a hidden column is reading it by binary search.
- Entitlement is **probed against the database** (SAVEPOINT-wrapped
  `SELECT amount_usd … LIMIT 1`), not assumed from the role name — if the
  grant is missing, the poweruser is masked rather than failed open.

## 4. Aggregation guard (mass-extraction control)

Exhibit B requires automated thresholds/alerting against mass extraction of
discrete datasets. Implementation (`src/functions/export/app.py`):

- `POST /export` counts the rows the **filter matched** (not the requested
  page — lowering `limit` cannot page under the control). Above
  `EXPORT_MAX_ROWS` (deploy parameter, default 5000) → **HTTP 428** naming
  the row count, the cap, and `subject_id` — a SHA-256 fingerprint of
  `{org_unit, format, columns, filters}` for *this exact query*.
- Clearing it requires an `approval_token` from `POST /approvals` whose
  approval is `approved`, of `subject_type: export`, and — when the subject
  was issued by this endpoint — **bound to the same fingerprint**. An
  approval for one query does not clear a different one; an approval issued
  to one org cannot be replayed by another (org_unit is inside the hash).
- Every outcome writes `audit_log`: `export_blocked`, `export_denied`,
  `export` (allowed — written in the same transaction as the read, before
  bytes leave the boundary), `export_delivered` / `export_delivery_failed`.
  The trail can over-record, never under-record.
- A separate `HARD_MAX_ROWS` materialization cap (413) bounds worst-case
  memory regardless of approvals.

## 5. Boundary, edge, and encryption

- **Edges (only three, all TLS):** CloudFront (viewer TLS, private S3 origin
  via OAC — the bucket blocks all public access) fronted by a
  CLOUDFRONT-scope WAF (AWS managed common rule set + per-IP rate rule,
  `WafRateLimit` default 2000/5min); the HTTP API (JWT default authorizer);
  the Cognito hosted UI.
- **Encryption at rest:** one customer-managed KMS key, rotation enabled,
  over the Aurora cluster **and its RDS-managed master secret**, both S3
  buckets (SSE-KMS + bucket key), and the Kinesis stream.
- **Encryption in transit:** TLS at every edge; database sessions
  `sslmode=require` (`compass_common/db.py`); AWS SDK calls TLS 1.2+.
- **Secrets:** none in the repository or in `samconfig`. The DB credential is
  created and rotated by RDS (`ManageMasterUserPassword: true`); functions
  read it at runtime with a `secretsmanager:GetSecretValue` grant scoped to
  that one ARN.
- **Optional detectors:** GuardDuty, Security Hub, and Macie are in-template
  behind `DeploySecurityBaseline` (default false — they are account
  singletons; enable with one flag on the stack that owns them).

## 6. In-boundary AI (IL5 story + AI TRiSM)

All inference goes through `compass_common/llm.py`, a Bedrock-only gateway:
`amazon.nova-lite-v1:0` (chat/summary) and `amazon.titan-embed-text-v2:0`
(embeddings). **No public AI API appears in any narrated/recorded path.**
IAM grants name those two model ARNs only. RAG (`src/functions/rag_chat/`)
retrieves from `grants_curated` **inside the caller's RLS transaction**, so
generated answers inherit row policy — the model cannot surface rows the user
cannot read. The RMF generator uses no LLM at all: ATO evidence must be
deterministic and byte-reproducible.

## 7. RMF-as-code

`src/functions/rmf_artifact/app.py` parses `template.yaml` and emits: PPS
registration tables (boundary-crossing inbound, internal, and outbound flows
derived from the IAM actions actually granted), a resource-derived topology
(Mermaid), data-protection/identity/audit inventories, and a candidate NIST
SP 800-53 Rev 5 mapping in which **every row cites the template property that
evidences it**. The artifact stamps the template SHA-256 and closes with
"what this artifact cannot assert" (runtime drift, transform-time expansion,
conditional resources, non-technical controls, categorization). Because it
regenerates from the same file that provisions the environment, security
documentation cannot drift from the infrastructure — the Exhibit B
"eMASS reflects the true state" requirement as a build property.

## 8. Audit and monitoring

- `compass.audit_log` — append-only application trail (exports, approvals,
  RMF generation). No update/delete path exists in application code.
- API Gateway access logs (JSON, includes authorizer errors), 14-day demo
  retention; Step Functions logging `ALL` with execution data; X-Ray tracing
  on every function (`Globals.Function.Tracing: Active`).
- Production statement (not demonstrated here): log/audit forwarding to the
  Government SIEM, IAVA patch automation, and SAST/DAST + container +
  IaC scanning in the delivery pipeline are production-pipeline items per
  Exhibit B; the demo's equivalent hooks are the lint/validate stages and
  the deterministic RMF evidence.

## 9. What this demo does NOT claim

Stated plainly so the security story stays honest:

- It runs in **commercial us-east-1**, configured to security-baseline
  *equivalents* (L 11.2(c)) — it is not an IL4/IL5 accredited environment,
  and no ATO is implied. The IL5 approach is: same template, deployed into
  the Government-furnished NRE/NRDE landing zone under the shared
  responsibility model.
- FIPS-validated endpoints, eMASS/A&A integration, STIG application via
  Compliance-as-Code, and SIEM forwarding are **approach statements**
  narrated in the demo, not features of this stack.
- Demo-cost deltas a production baseline changes: single NAT gateway, 1-day
  backup retention, `DeletionProtection: false`, 14-day log retention,
  detectors off by default.
- All data is synthetic (`seed/SYNTHETIC-DATA-MANIFEST.md`); the
  `CUI-Mock`/`Public-Mock` classification bands are deliberately fake labels
  for demonstrating classification-aware behavior, not real markings.

## 10. Verifying the claims (evaluator crib sheet)

```bash
# RLS is forced, and the app role is a non-owner with a column REVOKE:
grep -n "FORCE ROW LEVEL SECURITY\|REVOKE SELECT (amount_usd)" db/migrations/002_rls.sql
# The app assumes the least-privilege role and binds org per transaction:
grep -n "SET ROLE\|SET LOCAL compass.org_unit" src/common/python/compass_common/db.py
# Every route defaults to the JWT authorizer:
grep -n "DefaultAuthorizer" template.yaml
# MFA is ON, TOTP only:
grep -n "MfaConfiguration\|SOFTWARE_TOKEN_MFA" template.yaml
# The aggregation guard and its audit calls:
grep -n "428\|EXPORT_MAX_ROWS\|write_audit" src/functions/export/app.py | head
# Bedrock-only model access (the only model ARNs any function may invoke):
grep -n "foundation-model" template.yaml
# Regenerate the RMF evidence yourself:
python3 src/functions/rmf_artifact/app.py | head -60
```
