# ADR 0004: Use pay-per-use lake intelligence and export

- Status: accepted
- Date: 2026-08-11

## Context

Always-on search or Spark infrastructure would dominate the cost of an intermittent demonstration. The current synchronous analytics and export Lambdas cannot claim million-row capacity.

## Decision

Workers write deterministic gzip JSON Lines for immutable landing and curated partitions. Glue Catalog describes injected run partitions. Athena workgroups enforce a 10 GB per-query scan cutoff and convert completed curated partitions to compressed Parquet.

The Intelligence Receipt merges full-corpus aggregate partials from every Partition Receipt. Optional embedding coverage is capped and reported separately. The first scale slice does not provision OpenSearch or an always-on Spark cluster.

An Export Job is asynchronous. It produces an encrypted manifest over immutable JSON Lines or Parquet objects, exact row and byte counts, checksums, expiration, and audit evidence. A small Aurora export Adapter remains available for product-sized releases. The lake export Adapter is used for Scale Runs.

## Consequences

- Idle scale cost stays close to storage and metadata cost.
- Columnar output is real and queryable without packaging a large native Parquet runtime into Lambda.
- Intelligence claims can cover the full corpus for deterministic statistics while separately disclosing any semantic sample.
- The lake format Seam has two real Adapters: JSON Lines and Parquet.
