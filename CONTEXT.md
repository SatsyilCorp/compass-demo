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
- **Document Intake Run**: One event-driven processing attempt for a browser-dropped unstructured or semi-structured document, from inspection through bronze, quality, silver, gold, or quarantine.
- **Document Quality Receipt**: The immutable rules, score, gate decision, sensitive-pattern counts, and content hash for one Document Intake Run.
- **Document Taxonomy**: The shared six-class contract: `grant_abstract`, `technical_report`, `publication_summary`, `patent_summary`, `investment_brief`, and `financial_execution`.
- **Model Run**: One deterministic training and evaluation execution with a dataset digest, split seed, algorithm, metrics, and adapter disclosure.
- **Model Version**: A portable, immutable classifier artifact registered from one Model Run.
- **Deployment Receipt**: The actor, Model Version, target, alias, time, and truthful online-endpoint state for one promotion.
- **Drift Receipt**: The observed class distribution, population stability, out-of-vocabulary rate, threshold, verdict, and recommended action for a deployed Model Version.
- **MLOps Adapter**: The seam between the deterministic demo implementation and an explicitly configured SageMaker training implementation.
- **Rehearsal Adapter**: The existing small deterministic fixture path used for predictable demonstrations. It does not claim heavy-scale processing.
- **Scale Adapter**: The distributed path used for measured workload evidence.
- **Demonstration Run**: The presenter-led, sequential execution of the seven scored scenario elements and five strategic prompts, with one evidence locator and one honest boundary per element.
- **Document Intake**: A governed file submission that accepts sanitized structured, semi-structured, or unstructured content and produces inspection, quality, classification, lineage, and terminal receipts.
- **Document Receipt**: The hash-bound evidence for one Document Intake, including media type, size, source digest, inferred schema, quality disposition, Bronze, Silver, and Gold locators, classification, and model version.
- **Model Run**: One bounded training or evaluation execution over an approved synthetic corpus with dataset digest, algorithm, parameters, metrics, artifacts, and cost evidence.
- **Model Version**: An immutable registered candidate produced by a Model Run and governed through validation, approval, deployment, and retirement states.
- **Drift Receipt**: A deterministic comparison between a deployed Model Version baseline and an observed document window, including feature drift, prediction drift, threshold, disposition, and retraining recommendation.
- **Delivery Receipt**: Commit-bound evidence that source, tests, security checks, infrastructure plans, deployment gates, and environment promotion completed or failed without hiding any stage.
- **Public Evidence Snapshot**: One immutable, provenance-bound collection from public award, opportunity, research, budget, patent, or dataset sources, with a declared retrieval cutoff and PII-minimization receipt.
- **Evidence Class**: One of `observed`, `derived`, or `predicted`, displayed with every public portfolio claim.
- **Entity Link Receipt**: The source records, normalized comparison keys, match tier, confidence, cutoff, and reviewer state for one cross-source relationship.
- **Outcome Proxy**: A public, measurable indicator such as Phase II transition, follow-on obligation, or award-linked publication that must never be described as confirmed internal project success.

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
15. Every document stage references the same source SHA-256 and Document Intake Run identifier.
16. A document with a blocking extraction or quality failure cannot publish silver or gold data.
17. Document classification uses only the six labels in the Document Taxonomy.
18. Demo-adapter evidence never claims that a SageMaker job, registry package, or online endpoint exists.
19. A Model Version cannot become the champion without an explicit Deployment Receipt.
20. Public evidence and synthetic scale records remain separate Evidence Sets.
21. Every public intelligence value is labeled observed, derived, or predicted.
22. A similarity-only entity match cannot publish without analyst review.
23. Missing future outcome evidence is censored or unknown, never automatically negative.
24. An Outcome Proxy cannot be presented as ONR internal mission success.

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
