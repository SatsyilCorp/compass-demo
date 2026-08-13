# ADR 0009: Operator-controlled continuous ingestion

## Status

Accepted

## Context

The demonstration needs visible production-shaped changes across ingestion,
quality, lineage, catalog, notifications, and decision projections. A fixed
number of fast events stops too soon and makes the system appear scripted.
Official USAspending updates do not arrive every second, so the rapid feed must
remain clearly identified as synthetic.

## Decision

Compass provides one operator-controlled continuous synthetic session. The
operator selects a one-second or two-second cadence and the session runs until
Stop is selected.

Each pulse writes an immutable synthetic envelope to the deployed S3 landing
prefix. S3 EventBridge delivery starts the existing intake workflow, which
applies normalization, quality, row lineage, catalog publication, and decision
projection. The UI polls the durable control receipt and broadcasts each new
receipt to screens that refresh live evidence.

The visible session is not bounded by event count. Its Standard Step Functions
execution rotates every 250 pulses so execution history does not grow without
limit. The current execution ARN is updated atomically in DynamoDB, and Stop is
authoritative even during rotation. Deterministic object keys and conditional
writes make retries safe. Raw continuous-stream objects expire after seven days.
Routine per-pulse notifications are suppressed. Start, Stop, quarantine, and
failure signals remain visible, which avoids notification and SNS floods while
preserving operational evidence.

The API retains a bounded mode only for automated smoke and recovery tests. The
product control always starts continuous mode.

## Consequences

- Dashboard, ingestion, catalog, lineage, and notification views can change for
  as long as an operator keeps the session running.
- At one second the generator requests about 3,600 pulses per hour. At two
  seconds it requests about 1,800 pulses per hour.
- The rapid feed proves the deployed path with synthetic records. It does not
  claim that USAspending publishes source changes at that speed.
- Operators must stop unused sessions. Seven-day raw retention and workflow
  rotation limit two major sources of unbounded operational growth.
