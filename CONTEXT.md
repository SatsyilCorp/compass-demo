# Compass product context

Compass is a governed science and technology portfolio intelligence product. It turns synthetic or authorized source data into traceable decisions, with identity, quality, lineage, intelligence, release controls, and evidence visible in one mission workspace.

## Product language

- **Mission Workspace**: The authenticated product surface used to ingest, govern, analyze, decide, and release portfolio data.
- **Synthetic Workload**: One deterministic, synthetic-only collection of related portfolio records used to prove capacity and correctness without customer data.
- **Workload Profile**: An immutable definition of counts, dataset mix, defect mix, partition size, concurrency, retention, and safety limits.
- **Scale Plan**: A short-lived, server-calculated preview of a Workload Profile, its required capacity, expected duration, and Cost Envelope.
- **Scale Run**: One cost-bounded execution of a Scale Plan.
- **Run Gate**: The server-side decision that checks profile limits, active runs, capacity prerequisites, price freshness, and the Cost Envelope before launch.
- **Run Manifest**: The hash-bound truth for a Scale Run, including generator version, seed, parts, counts, checksums, and final disposition.
- **Partition Receipt**: The idempotent result of processing one bounded partition, including checksums, counts, quality, bytes, duration, retry evidence, and aggregate partials.
- **Quality Receipt**: Expected versus observed validation, curation, quarantine, duplicate, and relationship counts.
- **Intelligence Receipt**: The scope, algorithm version, corpus coverage, topics, anomalies, and result digest for one Scale Run.
- **Performance Receipt**: Observed throughput, duration, queue pressure, retries, failures, and partition completion for one Scale Run.
- **Cost Envelope**: The maximum estimated incremental AWS cost that the Run Gate will allow for one Scale Run.
- **Cost Estimate**: A pre-run calculation from an official AWS Price List snapshot and explicit workload quantities.
- **Cost Receipt**: The observed service quantities, immediate metered estimate, and later billing reconciliation status for one Scale Run.
- **Export Job**: An asynchronous, governed release of a completed Scale Run with format, row count, bytes, checksum, expiration, and audit evidence.
- **Serving Projection**: A bounded, policy-aware view of lake data and aggregates optimized for product queries.
- **Rehearsal Adapter**: The existing small deterministic fixture path used for predictable demonstrations. It does not claim heavy-scale processing.
- **Scale Adapter**: The distributed path used for measured workload evidence.

## Users and decisions

- A **portfolio poweruser** launches governed ingestion and Scale Runs, reviews data quality, runs intelligence, analyzes funding and delivery risk, and requests exports.
- A **scoped viewer** examines authorized portfolio data and decision briefs without corporate funding columns or cross-organization rows.
- A **reviewer** makes four-eyes release decisions separately from the requesting actor.
- A **platform operator** deploys, monitors, rehearses, and reconciles performance and cost evidence.

## Non-negotiable invariants

1. Synthetic records are labeled `synthetic_only=true` and never presented as customer data.
2. Every Scale Run is deterministic from profile, generator version, seed, and fixed as-of time.
3. The browser cannot choose an unbounded record count, partition count, concurrency, retention, or model spend.
4. A Scale Plan must pass the Run Gate before execution, and one plan can launch at most one run.
5. One active Scale Run is allowed by default.
6. A partition retry cannot increment curated counts twice or create a second logical output.
7. Generated equals curated plus quarantined at terminal state, subject to explicitly reported batch-held rows.
8. Every persisted part and terminal receipt has a SHA-256 checksum.
9. Intelligence states whether it covers the full corpus or a bounded sample.
10. Performance values are observed. Cost values are labeled estimated, metered, or billed.
11. The Scale Run identifier appears in structured receipts and logs, not as a high-cardinality CloudWatch metric dimension.
12. Data-plane test objects expire automatically, while compact evidence receipts remain long enough for evaluation.
13. Cancellation is cooperative, durable, and safe to retry.
14. A completed export reports exact rows, bytes, format, checksum, expiration, and audit receipt.

## Architecture language

Architecture proposals use these terms precisely:

- A **Module** owns a complete area of knowledge.
- An **Interface** is the smallest contract callers need.
- An **Implementation** hides the decisions behind that Interface.
- **Depth** means a small Interface hides substantial Implementation knowledge.
- A **Seam** is where alternative Implementations can vary.
- An **Adapter** connects one concrete technology to a Seam.
- **Leverage** is how many callers gain from one Module.
- **Locality** keeps related decisions and invariants together.
