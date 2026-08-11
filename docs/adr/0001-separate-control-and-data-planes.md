# ADR 0001: Separate control and data planes

- Status: accepted
- Date: 2026-08-11

## Context

The rehearsal path stores raw, curated, workflow, intelligence, and serving data in Aurora and processes a whole object inside bounded Lambda invocations. That Implementation is useful for a small deterministic demonstration, but its Interface cannot truthfully represent partition recovery, backpressure, or large lake processing.

## Decision

Compass has two explicit planes:

- The control plane owns identity, Scale Plans, the Run Gate, the durable run ledger, approvals, audit, and serving projections.
- The data plane owns immutable synthetic parts, queued partition work, validation, curation, lake formats, aggregate partials, and exports.

The Scale Run Module is the Interface between the planes. Its Run Manifest and receipts contain logical locators, never physical resource identifiers exposed to the browser.

Aurora remains the control and decision-serving store. S3 is the durable system of record for scale data. DynamoDB is the idempotent run and partition ledger. SQS provides backpressure. Step Functions Standard coordinates the run lifecycle. Athena and Glue Catalog provide pay-per-use columnar conversion and query metadata.

## Consequences

- A scale workload no longer competes with product serving queries for Aurora row and I/O capacity.
- The same Scale Run Interface supports a local Adapter and an AWS Adapter.
- The rehearsal Adapter remains available, but its receipts are labeled separately.
- Cross-store reconciliation becomes a required Implementation concern inside the Scale Run Module.
