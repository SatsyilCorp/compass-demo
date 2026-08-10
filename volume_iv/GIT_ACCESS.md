# Volume IV — Read-Only Repository Access

**Solicitation:** N0001426R4002 · Factor 3
**Repository:** Compass — the live code repository shown in the demonstration
video (Elements 2, and referenced throughout).

> Shell: the demonstration must showcase live code repositories (L 11.2(c)).
> This page gives evaluators read-only access to the exact code that built
> and ran the recorded environment. Fill every `[FILL]` field and verify
> access from an account outside the Offeror's organization before
> submission.

## Access details

| Field | Value |
|---|---|
| Hosting platform | `[FILL: e.g., GitHub / GitLab private repository]` |
| Repository URL | `[FILL: https://…/compass-demo]` |
| Access method | `[FILL: e.g., invited read-only collaborator accounts / group access token — read_repository scope only]` |
| Evaluator credentials or invite process | `[FILL: e.g., "send evaluator account names to <email>; invites issued within one business day" — or embed a read-only token here if the CO prefers self-service]` |
| Tag/commit matching the recording | `[FILL: tag, e.g. volume-iv-recording, and the full commit SHA]` |
| Access duration | Active through award; contact below for restoration if access fails |
| POC | `[FILL: name, email, phone]` |

**The tag above is the exact state demonstrated on video.** The recording
shows `git log` on camera; the top commit visible there matches the tagged
SHA. Access is read-only: evaluators can browse, clone, and diff, but not
push.

## What to look at (evaluator orientation)

| Path | What it shows |
|---|---|
| `README.md` | Platform overview, open-architecture posture, quickstart |
| `docs/CONTRACTS.md` | The locked interface contracts (DB, API, shapes) the build follows |
| `docs/ARCHITECTURE.md` | Components, data flow, element mapping, portability seams |
| `docs/SECURITY.md` | Zero Trust / RLS / CLS / aggregation-guard design, with a claim-verification crib sheet |
| `template.yaml` | The single IaC template that provisioned the recorded environment |
| `db/migrations/002_rls.sql` | FORCE row-level security + column-level security, as demonstrated |
| `src/functions/export/app.py` | Aggregation guard (HTTP 428) + audited export path, as demonstrated |
| `src/functions/rmf_artifact/app.py` | RMF artifact generator run live in the video — runnable offline: `python3 src/functions/rmf_artifact/app.py` |
| `seed/SYNTHETIC-DATA-MANIFEST.md` | Per-file proof that all demonstrated data is synthetic |

## Reproducing without AWS

The full UI runs locally on fixture data with no cloud resources and no
credentials (`README.md` → "Quickstart — mock mode"): `cd frontend &&
pnpm install && pnpm dev`. The analytics model and the RMF generator also run
offline (`src/functions/analytics/tests/`,
`python3 src/functions/rmf_artifact/app.py`).

## Contents statement

The repository contains no credentials or secrets (database credentials are
generated and held by AWS Secrets Manager at deploy time), and no CUI or PII
— all data files are machine-generated synthetic fixtures.
