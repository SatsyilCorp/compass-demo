# ADR 0008: Bounded accelerated demo stream

## Status

Accepted

## Context

The official USAspending source is acquired as a bounded five-minute micro-batch. It is not a two-second streaming source. A live presentation still needs visible product changes quickly enough for an audience to follow the result across ingestion, catalog, lineage, operations, and the decision workspace.

Running a permanent two-second source poll would misrepresent the upstream source, create avoidable cost, and couple presentation timing to an external service.

## Decision

Compass provides an explicit accelerated synthetic stream with these constraints:

- The presenter starts it from an authenticated global control.
- The default run emits 15 records at a two-second cadence. One-second cadence is available for short rehearsals.
- The backend accepts at most 60 events per session and stops automatically.
- A Standard Step Functions workflow owns the wait loop and invokes the intake Lambda once per event.
- Each tick writes one canonical synthetic envelope under the existing S3 `drops/` event boundary.
- The existing S3 EventBridge rule starts the real Express intake workflow for normalization, quality, persistence, catalog, and lineage.
- An immediate Kinesis receipt gives the browser a visible transport signal while the authoritative database projection catches up.
- DynamoDB stores only the current session control receipt and latest event summary.
- New receipt sequences trigger refreshes on the dashboard, ingest status, ticker, catalog, operational lineage, and notifications.
- The dashboard projection cache is one second so it cannot hide a new accepted record during the bounded run.

The interface labels the path as accelerated and synthetic. It also states that official USAspending acquisition keeps its independent bounded cadence.

## Consequences

The presentation shows real deployed AWS service activity every one or two seconds without claiming that the public source changes at that rate. Each run has bounded transitions, Lambda invocations, S3 objects, Kinesis records, and database writes. Idle cost does not increase beyond the existing deployed resources.

The accelerated path is evidence of integration behavior and UI coherence. It is not a sustained throughput benchmark. Scale Run remains the workload proving path for large synthetic volumes.
