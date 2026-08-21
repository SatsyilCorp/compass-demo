# ADR 0006: Separate public evidence intelligence from synthetic scale

- Status: accepted
- Date: 2026-08-11

## Context

Compass needs real public ONR and Navy evidence for credible portfolio analysis.
It also needs deterministic synthetic workloads to prove scale, retries, data
quality, and failure recovery. Combining these corpora would make source truth,
record counts, model metrics, and demonstration claims ambiguous.

## Decision

Create a Public Evidence Intelligence Module beside the Synthetic Scale Module.
The public module owns source snapshots, PII minimization, canonical records,
entity links, temporal labels, predictive artifacts, public-data lineage, and
citation evidence. The synthetic module continues to own deterministic workload
profiles and resilience receipts.

Compass joins the modules only through a selected Evidence Set. Every screen and
receipt states the Evidence Set and evidence class. A public snapshot cannot
claim ONR internal outcomes. A synthetic Scale Run cannot appear as a public
award corpus.

The public module exposes portable JSONL and Parquet contracts. AWS and
Databricks implement the same contracts through separate adapters.

## Consequences

* Real public records can support defensible intelligence without weakening the
  deterministic scale proof.
* Model targets and evaluation cutoff dates remain inspectable.
* The application must project aggregate public intelligence independently from
  the existing curated synthetic portfolio until the new APIs are deployed.
* Cross-source entity resolution and rights review become explicit governance
  responsibilities.
