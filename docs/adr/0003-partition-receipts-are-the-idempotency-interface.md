# ADR 0003: Partition receipts are the idempotency Interface

- Status: accepted
- Date: 2026-08-11

## Context

SQS and Lambda provide at-least-once delivery. Retries are normal. Exactly-once processing cannot be assumed from the transport.

## Decision

Each partition has a deterministic identifier, input range, object keys, and expected checksum set. A worker writes deterministic lake objects first, then commits a DynamoDB transaction that:

1. Changes the partition ledger item from non-terminal to terminal.
2. Adds its counts, bytes, and duration to the run ledger once.
3. Records the Partition Receipt checksum.

A repeated delivery recomputes or verifies the same deterministic outputs, observes the terminal ledger item, increments duplicate replay evidence, and does not add counts again.

The Partition Receipt is the only worker result consumed by finalization. This creates a deep Module: the Interface is one receipt, while retry, object layout, validation, curation, and aggregate partials remain inside the Implementation.

## Consequences

- Transport duplication does not become logical duplication.
- Failed parts can be redriven independently.
- Finalization can prove exact partition and record invariants.
- Versioned S3 outputs may contain overwritten physical versions, but one logical output is authoritative.
