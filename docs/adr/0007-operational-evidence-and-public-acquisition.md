# ADR 0007: Project operational evidence through one contract

Status: accepted for the proving prototype

Date: 2026-08-12

## Context

Compass already retained authoritative domain evidence in Aurora, S3, DynamoDB,
Step Functions, SageMaker, and CloudWatch. The demonstration could not follow
one run across those boundaries without switching between several screens and
inferring progress from browser timers. Scheduled public-data refresh and
operator notification also lacked a shared, inspectable contract.

## Decision

Create one compact Operational Evidence Module with two append-oriented record
types:

- a stage receipt keyed by run, sequence, and stage
- an operational signal keyed by a stable event identifier

Domain services write their authoritative result first. They then project safe
logical locators, counts, model versions, timestamps, and SHA-256 digests into
the operations table. Raw source records, physical bucket names, account IDs,
tokens, presigned URLs, stack traces, and exception messages are excluded. A
projection failure is logged and repairable, but it never rolls back a valid
domain transaction.

The same interface is used by structured intake, document intake, quality and
quarantine, SageMaker model execution, model monitoring, and public-source
acquisition. The protected operations API exposes summary, signal,
acknowledgement, and run-lineage projections only to the corporate poweruser.

USAspending is acquired through a five-minute bounded micro-batch because its
public API is request based. Each accepted response is versioned, hashed,
PII-minimized, compared to the previous accepted snapshot, and then represented
as change events on Kinesis. Compass does not describe this polling interface
as a source push stream and does not treat a record outside the bounded result
page as a deletion.

## Consequences

- One screen can follow a source through quality, transformation, model use,
  publication, and consumption using execution receipts.
- Alerts can be acknowledged in the application and published to an encrypted
  SNS topic without exposing raw content.
- Email remains an explicit subscription that must be confirmed by its owner.
- Existing domain stores remain authoritative. The operations table is not a
  replacement data system.
- Cross-platform lineage can later ingest Databricks, Advana, or enterprise
  catalog events through the same projection without coupling the frontend to
  those products.
- The commercial AWS deployment remains a public and synthetic proving
  environment. IL4 or IL5 authorization requires the separate target boundary
  and Government dependencies documented in
  `docs/IL4_IL5_TARGET_ARCHITECTURE.md`.
