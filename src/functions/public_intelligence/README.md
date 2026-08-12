# Public intelligence Lambda

This function exposes two Cognito-protected routes without touching the
synthetic Compass database:

- `GET /public-intelligence/snapshot`
- `POST /public-intelligence/explain`

The function loads a small current manifest from the configured S3 bucket. The
manifest must point to an immutable, versioned evidence index under
`public-intelligence/snapshots/<snapshot-id>/`. Before any record is served, the
function checks the index SHA-256 digest, public-data boundary declaration,
PII-minimization declaration, record evidence class, and HTTPS source URL.

The explanation route uses bounded lexical retrieval over that verified index.
It makes at most one Amazon Bedrock call with a fixed 500-token output cap. A
Bedrock failure produces a deterministic cited explanation. No relevant source
record produces an explicit `INSUFFICIENT_CITABLE_EVIDENCE` refusal and no model
call.

## Manifest contract

```json
{
  "contract": "compass.public-intelligence.provenance-manifest.v1",
  "version": 1,
  "snapshot_id": "onr-public-2026-08-11",
  "generated_at": "2026-08-11T22:00:00Z",
  "as_of_at": "2026-08-11T22:00:00Z",
  "evidence_class": "public_evidence",
  "data_boundary": {
    "classification": "public",
    "contains_cui": false,
    "pii_minimized": true
  },
  "evidence_index": {
    "key": "public-intelligence/snapshots/onr-public-2026-08-11/evidence-index.json",
    "sha256": "<sha256-of-exact-index-object-bytes>"
  },
  "sources": [],
  "models": []
}
```

## Evidence index contract

```json
{
  "contract": "compass.public-intelligence.evidence-index.v1",
  "version": 1,
  "snapshot_id": "onr-public-2026-08-11",
  "snapshot": {},
  "records": [
    {
      "record_id": "award-N00014-example",
      "source_id": "usaspending",
      "title": "Public award title",
      "summary": "Compact, PII-minimized evidence text.",
      "source_url": "https://www.usaspending.gov/award/example",
      "evidence_class": "observed",
      "model_run_id": null,
      "uncertainty": null,
      "record_sha256": "<canonical-record-digest>"
    }
  ]
}
```

Raw payloads, CUI, non-public records, non-HTTPS citations, and unbounded source
documents are rejected at the read boundary.
