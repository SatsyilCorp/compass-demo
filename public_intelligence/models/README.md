# Compass public intelligence model suite

This package trains six classical models from one strict JSONL contract. It is
separate from source ingestion. A source record is not training-ready until it
has an evidence-set snapshot, public rights, training authorization, authentic
label evidence, feature availability timestamps, and a reviewed feature
schema.

## Models

- `funding_forecast`: chronological backtests plus held-out conformal intervals
- `sbir_transition`: grouped temporal fit, calibration, and test partitions
- `technology_classifier`: reviewed taxonomy labels with duplicate-safe text splits
- `research_impact_quantiles`: 10th, 50th, and 90th percentiles after temporal censoring
- `anomaly_detection`: reviewed rules plus Isolation Forest review signals
- `observed_signal_proxy`: external public-signal likelihood, never internal ONR success

## Canonical JSONL

The first line is a `compass.public-intelligence.dataset.v1` manifest. Remaining
lines are `compass.public-intelligence.training-row.v1` records. Each row must
provide:

- a unique record ID, timezone-aware event time, and optional split group
- only reviewed numeric, categorical, or text features
- lineage for each present feature, including `max_available_at`
- an observed authentic target, or an explicit censored research-impact target
- public label source evidence and observation time
- public rights, PII-minimization evidence, training authorization, and SHA-256
- evidence-set identity matching the manifest

Feature availability after prediction time is rejected. Duplicate sources
cannot cross splits. Grouped models keep every group in one strictly ordered
time partition. Synthetic test fixtures require an internal test-only loader
flag that the CLI never enables.

## Train

Build a canonical funding dataset from the checked-in, reviewed USAspending
aggregate. The builder excludes every quarter that had not closed by the
snapshot `as_of_date`. It also excludes four warmup quarters so each row has
lag 1, lag 4, and trailing four-quarter features. The trailing standard
deviation is the population standard deviation. Every feature points to public
source records available before the forecast quarter begins.

```bash
python -m public_intelligence.models build-funding \
  --input artifacts/private/public-intelligence/usaspending-quarterly-obligations.json \
  --output /tmp/usaspending-funding-approved.jsonl
```

For the current reviewed snapshot, the 76 received periods contain 75 complete
quarters. FY2026 Q4 is partial as of 2026-08-11 and is excluded. Four complete
quarters are used only as lag warmup, leaving 71 authentic training rows.

Then train the candidate model:

```bash
python -m public_intelligence.models train \
  --input /tmp/usaspending-funding-approved.jsonl \
  --output /tmp/compass-funding-candidate
```

The output directory receives `model.joblib`, `model-card.json`,
`training-receipt.json`, and `artifact-manifest.json`. Serialization creates a
candidate only. It does not claim registry approval or deployment.
