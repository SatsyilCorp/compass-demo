# Volume IV: Read-only repository access

**Solicitation:** N0001426R4002, Factor 3
**System:** Compass S&T Portfolio Intelligence

This page provides evaluator access to the exact repository revision deployed
and shown in the technical demonstration. Replace each `EXTERNAL INPUT` value
with an approved final value before submission.

## Access details

| Field | Submission value |
|---|---|
| Hosting platform | `[EXTERNAL INPUT: approved Git hosting platform]` |
| Repository URL | `[EXTERNAL INPUT: private repository URL]` |
| Read-only access method | `[EXTERNAL INPUT: invited evaluator accounts or approved read-only credential process]` |
| Access instructions | `[EXTERNAL INPUT: exact steps, required account, and support path]` |
| Recording tag | `[EXTERNAL INPUT: immutable tag for the demonstrated revision]` |
| Full commit SHA | `[EXTERNAL INPUT: 40-character SHA matching the recording]` |
| Access start and end | `[EXTERNAL INPUT: approved availability period]` |
| Technical support POC | `[EXTERNAL INPUT: name, email, and phone]` |

The recording shows the short deployed revision in System Inspector and the
same revision from `git rev-parse --short=12 HEAD`. The full SHA above must be
the commit referenced by the immutable recording tag.

Evaluator access is read-only. It must allow browsing and cloning without
allowing push, merge, workflow dispatch, environment access, secret access, or
AWS role assumption.

## Evaluator orientation

| Path | Evidence |
|---|---|
| `README.md` | Product scope, live and replay distinction, quickstart, and release gates |
| `docs/DEMO_SCRIPT.md` | The 39-minute evidence-first sequence used for the recording |
| `docs/CONTRACTS.md` | Database, identity, 17 protected API operations, replay, and evidence contracts |
| `docs/ARCHITECTURE.md` | Components, data flow, portability seams, and resilience truth |
| `docs/SECURITY.md` | Enforced controls, disclosure boundary, and production limitations |
| `.github/workflows/quality.yml` | Clean-checkout quality and browser gates |
| `.github/workflows/deploy.yml` | Protected-environment AWS OIDC deployment workflow |
| `template.yaml` | Complete demonstration infrastructure, evidence route, observability, and resilience modes |
| `db/migrations/003_security_hardening.sql` | Explicit grants, corporate GUC gate, append-only audit, approval expiry, and consumption fields |
| `db/migrations/004_opaque_approval_capability.sql` | Opaque approval capability verifier and its narrow update grant |
| `src/common/python/compass_common/http.py` | Centralized identity normalization and allowlisted CORS |
| `src/functions/evidence/app.py` | Sanitized System Inspector backend projection |
| `src/functions/export/app.py` | Exact-fingerprint aggregation guard and one-time approval consumption |
| `scripts/prepare_demo.py` and `src/functions/migrator/demo_prep.py` | Bounded synthetic preparation, redacted preflight, and one-shot live drop contract |
| `src/functions/rmf_artifact/app.py` | Deterministic RMF evidence generator |
| `frontend/lib/mock/scenario-store.ts` | Persistent deterministic replay state |
| `frontend/tests/` | Responsive and accessibility smoke coverage |
| `seed/SYNTHETIC-DATA-MANIFEST.md` | Per-file synthetic-data statement |

## Reproduction without AWS

```bash
cd frontend
pnpm install --frozen-lockfile
NEXT_PUBLIC_USE_MOCK=true NEXT_PUBLIC_AUTH_DISABLED=true pnpm dev
```

The local UI labels this mode Replay fixture. It supports deterministic clean,
legacy, and defective scenarios and can be reset to a known baseline. Replay
is suitable for evaluator exploration of interaction and business rules. It is
not evidence that AWS, Cognito, Aurora, Step Functions, Kinesis, or Bedrock ran.

The RMF artifact can also be generated offline:

```bash
python3 src/functions/rmf_artifact/app.py -o /tmp/compass-rmf.md
```

## Repository content statement

The submitted recording revision must contain no committed credentials or
secret values. Database credentials are created and held by AWS Secrets
Manager. All demonstrated portfolio and license records are synthetic. No CUI,
PII, classified data, or real award data may be included.

## Pre-submission access test

- Confirm the repository URL opens from an account outside the offeror
  organization.
- Confirm the evaluator can clone the recording tag.
- Confirm the evaluator cannot push or dispatch a deployment.
- Confirm the tag resolves to the full SHA above.
- Confirm the SHA matches the deployed revision in the final recording.
- Complete the approved secret and sensitive-data scan on the recording tag.
- Confirm access stays active for the approved period.
- Remove this checklist from the final submitted page after verification.
