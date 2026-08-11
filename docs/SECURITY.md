# Compass security design

This document distinguishes implemented demonstration controls from production
targets. Compass processes synthetic data only. It does not claim an ATO or an
IL4 or IL5 accreditation.

## 1. Request authorization

Every HTTP route uses the Cognito JWT authorizer as the default API authorizer.
The gateway verifies issuer and audience before a handler runs. The shared
identity module then handles both supported API Gateway event shapes:

- native `requestContext.authorizer.jwt.claims`
- optional request-authorizer context

`cognito:groups` is authoritative. `compass-poweruser` maps to the poweruser
role and `ONR-Corporate`; `compass-viewer` maps to the viewer role and
`Code-30`. A token with no recognized Compass group is denied. A forwarded
role cannot override a verified group. If a supplied organization conflicts
with the resolved role, resolution fails closed.

Cognito uses optional per-user TOTP, 16-character passwords, and
administrator-created users. The three collaboration identities explicitly
remain password-only. A separate `presenter@compass.demo` identity enables and
prefers TOTP for the formal Element 1 demonstration. Tokens expire after one
hour. Optional pool configuration is a demo usability posture, not the
production target.

The activity endpoint applies the same persona boundary to transport metadata.
Its database projection is authoritative. Recent Kinesis receipts merge by
stable event identifier, and any receipt missing organization scope is
corporate-only rather than visible to the scoped viewer.

## 2. Cross-origin policy

The API does not return `Access-Control-Allow-Origin: *`. API Gateway lists the
local development origin and, after deployment, the exact CloudFront origin.
Lambda response helpers use the same allowlist through
`CORS_ALLOW_ORIGINS`. An unrecognized or missing origin is not reflected.

This is browser-origin protection, not authentication. JWT authorization still
applies to every route.

The 2026-08-11 live CORS verification passed all 25 operations in the earlier
revision. A separate authenticated browser pass used its exact deployed origin.
The eight document and model operations now deployed in `local-fe56c61` require
their own exact-origin acceptance check.

## 3. Network and encryption boundary

- The web bucket is private and served through CloudFront OAC.
- WAF applies the AWS managed common rule set and an IP rate rule.
- Data-touching functions and Aurora run in private subnets.
- The database security group accepts PostgreSQL traffic only from the Lambda
  security group.
- Database sessions require TLS.
- A customer-managed KMS key encrypts Aurora, its managed secret, the raw and
  web buckets, and Kinesis. Key rotation is enabled.
- RDS creates and stores the master credential. No database secret is committed
  to the repository.

The single NAT gateway in demonstration mode is an availability and cost
tradeoff. A production design uses approved per-AZ egress or private service
endpoints as required by the landing zone.

## 4. Real row-level security

Three mechanisms prevent RLS from being a UI-only filter:

1. `grants_curated` has RLS enabled and forced.
2. The migrator owns the table; application functions assume the non-owner
   `compass_app` role.
3. Organization context is set with `SET LOCAL` inside each transaction, so it
   is discarded on commit or rollback and cannot leak through a warm
   connection.

Application reads do not rely on a caller-supplied organization filter. The
database policy determines visible rows.

## 5. Column-level funding control

Migration `003_security_hardening.sql` revokes broad runtime grants and then
grants only the columns and operations each relation needs. The base curated
table does not grant the funding column to `compass_app`.

Corporate funding reads use a security-barrier view that also requires
`current_setting('compass.org_unit', true) = 'ONR-Corporate'`. Because both
personas share the runtime role, this GUC gate is necessary. A viewer receives
no corporate view rows and cannot read the funding column from the base table.

The export service refuses viewer requests that select or filter on
`amount_usd`. It does not silently drop the restricted field. Corporate
entitlement is probed against the database inside a savepoint and fails closed.

## 6. Explicit runtime grants

The forward migration removes inherited table-wide `SELECT`, `INSERT`,
`UPDATE`, and `DELETE` rights. It then grants the required operations per
relation and, where needed, per column. Future tables do not automatically
inherit broad runtime access.

This keeps the shared application role usable while making its database
permissions auditable in the versioned migration set.

Migration `004_opaque_approval_capability.sql` is deliberately separate from
the already-deployable hardening migration. It adds the approval verifier with
`ADD COLUMN IF NOT EXISTS` and grants `compass_app` update access to that column
only. A stack that has already recorded migration 003 therefore still applies
the opaque capability upgrade.

## 7. Append-only audit

The application role has `SELECT` and `INSERT` on `audit_log`, but no update or
delete permission. A database trigger rejects update and delete attempts even
if an operational session accidentally receives a broader grant later.

Approval and export writes occur in the same transaction as their decision.
The export allow receipt is committed before the delivery step returns a
download reference.

## 8. Aggregation guard and approval capability

`POST /export` counts all rows matched by the normalized request, independent
of a client limit. When the count exceeds `EXPORT_MAX_ROWS`, it returns HTTP
428 with a subject identifier based on the exact organization, format,
columns, and filters.

A clearing approval must be:

- type `export`
- bound to the exact `exp-` query fingerprint
- approved by an authorized persona other than the requester
- unexpired
- unused

The reviewer receives a short-lived opaque one-time token. Only its SHA-256
verifier is stored. The export transaction locks the approval row, verifies
the presented capability, and conditionally writes `consumed_at` and
`consumed_by`. Two concurrent requests cannot spend the same capability, and
a later retry is denied. A separate hard materialization cap cannot be
overridden by approval.

The demonstration stack enforces the separate-persona decision through
`APPROVAL_REQUIRE_FOUR_EYES=true`. Production would map request and decision
rights to approved organizational roles and retain the same evidence fields.

## 9. AI boundary

All model calls use the shared Bedrock gateway. The only declared models are
Nova Lite for text generation and Titan Embed Text v2 for embeddings. No
public AI API is used in the recorded path.

RAG retrieves curated rows inside the caller's database policy context. A
generated answer cannot cite a row that retrieval was not allowed to return.
The RMF generator is deterministic and does not use an LLM.

The commercial demonstration deployment does not make Bedrock or the stack an
IL5 service. The production approach is to deploy the template and approved
model services inside the Government landing zone, apply enclave controls,
and complete the required authorization process.

## 10. Protected System Inspector

`GET /system/evidence` is poweruser-only and read-only. It projects only
allowlisted application evidence. The UI shows its live or replay mode,
generation time, revision, correlation ID, request latency, identity decision,
quality and workflow receipts, model metadata, portfolio counts, and sanitized
audit fields.

The projection excludes:

- AWS account IDs, ARNs, resource names, and bucket keys
- database hosts, secret identifiers, secret values, and credentials
- bearer tokens, raw claims, email addresses, usernames, and source IPs
- SQL, prompts, abstracts, raw portfolio rows, and presigned URLs
- exception text, stack traces, and internal infrastructure errors

Server failures return a generic unavailable response while structured logs
record only the correlation ID and exception class.

## 11. Delivery security

The quality workflow checks source policy, Python lint, Python and frontend
production dependencies, offline contracts, migration synchronization, SAM
validation and build, frontend type safety, deterministic scenario invariants,
static build, and responsive browser accessibility.

The deployment workflow is manually dispatched into a protected GitHub
environment. It receives short-lived AWS credentials through GitHub OIDC,
stamps the source revision into the deployment, applies additive migrations
before code when updating an existing stack, deploys the reviewed revision,
and reruns the bundled migration set. Each applicable migration pass requires
an `ok` result and a `granted` runtime-role bootstrap. The workflow fails when
the protected export threshold or database-resilience mode is missing or
invalid, and passes both values into the reviewed change set. It then publishes
the live frontend and verifies expected public security headers and that the
System Inspector endpoint returns 401 without a token. The exact CloudFront
origin and Cognito callback values come from stack outputs. A fresh stack uses
an automatic second deployment pass for that binding, so public web URLs are
not operator-supplied environment inputs. No long-lived AWS key is required in
the repository.

Environment approval rules, the OIDC trust policy, branch protections, and
repository evaluator access are deployment-owner responsibilities and must be
verified before recording.

The 2026-08-11 Satsyil pass verified CSP, Permissions Policy, HSTS, WAF, a real
Cognito password and TOTP session, all nine product screens, and the Scale
controls. It observed no `Failed to fetch` result and no browser command error.
This live check does not replace an exact-commit protected-environment workflow
record.

Demo preparation is an operator-only direct-invoke path. It requires an exact
synthetic-reset confirmation, validates fixed fixture content and hashes, and
stages non-ingestible `.fixture` objects outside the EventBridge `drops/`
prefix. Before a reset, the private migrator checks every UI-driving data scope
and refuses the transaction if unexpected state is present. Deletes are
limited to source-controlled batch, run, license, and demo-actor scopes. Audit
history is preserved. Baseline analytics uses the fixed service actor
`compass-demo-preparer`. Live fixture release revalidates bytes against the
latest immutable preparation hash receipt, and EventBridge alone starts the
workflow. The receipt exposes logical locators and hashes, not a physical
bucket name.

The bounded identity utility creates or updates only the three fixed synthetic
team users plus the formal presenter, assigns only their expected Compass
group, disables MFA preference on the team users, and completes one presenter
software-token factor. It uses a temporary no-secret password-auth client and
always deletes that client. It does not print credentials, sessions, AWS
identifiers, or TOTP values. Ignored private credential artifacts and their
directory use restrictive local permissions. The separate demo preparation
tool is verification-only for identity state and cannot change users, groups,
passwords, or MFA.

Scale acceptance uses AWS IAM to invoke the deployed Scale Control Lambda with
a staged API Gateway event. It exercises the live route handler and data plane
but bypasses Cognito, API Gateway transport, WAF, and the browser. Saved
receipts disclose this transport and omit the export download URL. The real
Cognito and browser boundaries are verified separately.

## 12. Monitoring and retention

Implemented demonstration observability includes:

- JSON API access logging with 14-day retention
- One explicit stack-owned 14-day application log group with function-specific streams
- Step Functions logging at `ALL`
- Active X-Ray tracing for Lambda functions
- Eleven alarms covering API, functions, queues, workflow, and database signals
- Two source-controlled CloudWatch dashboards for operations and Scale Run evidence

No alarm notification target is configured in the demonstration template.
Production would route alarms and audit logs to approved operations and SIEM
services with retention based on policy.

## 13. Resilience truth

The default database mode has one writer, seven-day backups, and deletion
protection disabled. It does not demonstrate database instance failover.

The optional `ha` mode adds a cluster reader, uses 14-day backups, and enables
deletion protection. It demonstrates a stronger single-region database
posture. It does not provide cross-region disaster recovery or validate a
production RTO or RPO.

The Satsyil stack was deployed in `ha` mode on 2026-08-11. Its writer and
reader were available, private, and encrypted; 14-day backups and deletion
protection were enabled. This is a deployed configuration check, not a
failover, restore, RTO, or RPO exercise.

The production target requires approved recovery objectives, cross-region
backup copy or replication, tested restore and promotion procedures, service
quota and capacity validation, per-AZ egress, traffic failover, and recurring
exercises. Those are design and operational commitments, not controls proven
by this single-region demonstration.

## 14. Claims not made

Compass does not claim:

- an ATO
- IL4 or IL5 accreditation
- validated FIPS endpoint coverage
- eMASS integration
- STIG application to a Government enclave
- Government SIEM forwarding
- tested production RTO or RPO
- authoritative appropriation or budget-authority ingestion
- scheduled license-renewal notification
- unlimited-load or sustained-concurrency capacity certification
- multi-terabyte validation
- Government-data processing evidence
- Exhibit B capacity certification

## 15. Verification pointers

```bash
rg -n "DefaultAuthorizer|MfaConfiguration|SOFTWARE_TOKEN_MFA" template.yaml
rg -n "CORS_ALLOW_ORIGINS|cors_allow_origins" src/common/python/compass_common/http.py template.yaml
rg -n "FORCE ROW LEVEL SECURITY" db/migrations/002_rls.sql
rg -n "REVOKE SELECT|grants_curated_corp|audit_log_append_only" db/migrations/003_security_hardening.sql
rg -n "capability_hash|GRANT UPDATE" db/migrations/004_opaque_approval_capability.sql
rg -n "expires_at|consumed_at|FOR UPDATE|exact export fingerprint" src/functions/export/app.py
rg -n "system/evidence|SAFE_DETAIL_KEYS" src/functions/evidence/app.py
rg -n "AWS::CloudWatch::Alarm|AWS::CloudWatch::Dashboard|RetentionInDays" template.yaml
python3 src/functions/rmf_artifact/app.py | head -60
```
