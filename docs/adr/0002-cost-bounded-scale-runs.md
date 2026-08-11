# ADR 0002: Enforce cost before every Scale Run

- Status: accepted
- Date: 2026-08-11

## Context

AWS Budgets and billing reports are delayed. A browser action that starts an unbounded workload would be unsafe even when the account has a monthly budget.

## Decision

Every run starts from a short-lived Scale Plan. The Cost Evidence Module calculates an incremental estimate from an official AWS Price List snapshot, records every quantity and rate, applies a conservative contingency, and produces a Cost Envelope.

The Run Gate denies launch when any of these conditions is true:

- The plan is expired, already consumed, or does not match the request.
- Another Scale Run is active.
- The profile exceeds deployed record, partition, concurrency, retention, or enrichment limits.
- The estimate exceeds either the profile envelope or the deployed hard cap.
- The price snapshot is missing or too old for a required service dimension.
- The 1m profile lacks a successful 100k prerequisite receipt.

The product can show budget and billing data as evidence, but neither is the hard control.

## Consequences

- Plans are server-owned and idempotent.
- Cost claims distinguish monthly idle, incremental run, retained storage, immediate metered estimate, and delayed billed reconciliation.
- A pricing snapshot and its publication dates become versioned evidence.
