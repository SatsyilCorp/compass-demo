# Opportunity requirements and evidence boundary

Status: authoritative requirement interpretation with prototype truth labels

This note records the opportunity facts that size the target platform and
separates them from what the Compass AWS prototype has actually demonstrated.
It does not copy proposal data, personal data, Government-only material, or
proprietary content into the repository.

## Authoritative references

| Reference | Stable locator | Permitted use in this repository |
|---|---|---|
| Exhibit B | Google Drive file ID `1Gb5Kvt-B9TrJj8h6QpFkJu_4OhGyYQXm` | Record the workload and operating targets listed below. |
| QASP | Google Drive file ID `18k-L24gQBBVpa0zhGPeoCOkyzx5CYTdi` | Record the service-quality and review targets listed below. |
| PWS | Solicitation `N0001426R4002` | Map required data, analytics, security, delivery, and integration capabilities. |
| CDRL | Google Drive file ID `1ONxTKw-4HLPiVLbwJD_7WOt4lHS57JX5` | Record only the distribution boundary. The file is Government-only or proprietary and remains outside the public corpus. |

## Production workload and service targets

These are target requirements, not measured prototype results.

| Requirement source | Target | Compass AWS evidence today | Remaining production proof |
|---|---|---|---|
| Exhibit B | 500 to 1,000 total users | Cognito personas and role-scoped application paths are implemented. | Government identity integration plus representative concurrency and endurance testing. |
| Exhibit B | 200 to 300 power users | A power-user workflow is implemented and browser tested. | Target-volume power-user concurrency, query isolation, and workload-mix testing. |
| Exhibit B | 10 to 20 source systems | 12 public source families and separate synthetic workload adapters are represented. | Authorized Government and licensed commercial connectors, refresh ownership, and source-specific acceptance. |
| Exhibit B | 1 to 20 TB managed data | S3, Parquet, Glue, Athena, bounded partitions, and lifecycle controls are implemented. | Multi-terabyte loading, query, recovery, and cost evidence in the target landing zone. |
| Exhibit B | At least 1 TB of annual growth | Lifecycle and partitioning controls are designed. | A year-over-year growth, retention, compaction, and recovery test at target volume. |
| Exhibit B | Daily incremental and full refresh patterns | Event-driven intake, replay, idempotency, quality, and quarantine are demonstrated on bounded data. | Production schedules, full-refresh windows, source deltas, and service-level evidence. |
| Exhibit B | Modular, parameterized infrastructure-as-code pipelines | SAM and CloudFormation define parameterized AWS resources, with source-controlled CI and deployment workflows. | Customer environment parameters, protected approvals, exact-commit receipts, and target-zone promotion evidence. |
| Exhibit B | 50 to 75 Tier 1 and Tier 2 tickets per month | Logs, alarms, dashboards, correlation identifiers, and runbooks are implemented. | Service desk integration, staffing model, ticket taxonomy, monthly volume evidence, and trend reporting. |
| QASP | 99 percent uptime during core hours | Highly available application components, health checks, alarms, and an Aurora reader are deployed. | Contract-defined core hours, measurement method, exclusion policy, observation window, and accepted service report. |
| QASP | 95 percent ticket service-level attainment | Runbooks and operational evidence exist. | Approved priorities, response and resolution clocks, service desk records, and monthly SLA calculation. |
| QASP | Cloud-log inspection | CloudWatch logs, metrics, alarms, dashboards, and X-Ray are implemented. | Government log destination, retention, access review, alert triage, and recurring inspection evidence. |
| QASP | FinOps | Cost envelopes, price snapshots, and per-run estimated cost receipts are implemented. | Billing reconciliation, allocation tags, forecasts, optimization actions, and accepted reporting cadence. |
| QASP | Responsible AI review | Model cards, source hashes, holdout metrics, approval states, citations, and refusal behavior are represented. | Government RAI process, reviewer assignments, impact assessment, approval evidence, and recurring monitoring. |

## PWS capability mapping

| PWS requirement area | Target interpretation | Prototype boundary |
|---|---|---|
| Source data | Public or licensed science and technology publications, grants, patents, startup investment, company data, and informal literature, plus authorized structured and unstructured Government acquisition and scientific reports | Compass holds minimized public evidence and synthetic test data. Government reports and licensed commercial data are not assumed available and require approved transfer or credentials. |
| Secure cloud platform | Secure cloud processing with row-level and column-level controls | The AWS prototype demonstrates authentication, JWT authorization, RLS and CLS patterns, encryption, private data services, WAF, and audit. It is not an accredited Government environment. |
| Analytics and machine learning | NLP plus approved SageMaker or Azure Machine Learning capabilities | The prototype demonstrates deterministic analytics, document classification, public-evidence forecasting, registry controls, and cited explanation. It does not claim production model approval or universal project-success prediction. |
| Delivery automation | Infrastructure as code, CI/CD, automated testing, and streaming integration | Source-controlled SAM, CloudFormation, GitHub workflows, tests, Step Functions, SQS, EventBridge, and Kinesis seams are present. Exact customer pipelines and sustained streaming loads remain target work. |
| Interoperability | Open formats, modular interfaces, and integration with Advana or Pulse | JSON, CSV, Parquet, HTTP APIs, event contracts, and replaceable adapters are used. No live Advana or Pulse connection is claimed. |
| Security posture | IL5 and FedRAMP High aligned target controls, with no public commercial AI used for CUI | The commercial Satsyil demo contains no CUI and is not an ATO, IL5 authorization, or FedRAMP High authorization. Any CUI path must use a Government-approved boundary and approved model service. |

## Data admission boundary

- Public evidence enters only from lawfully accessible sources with provenance,
  bounded collection, rights review, and direct-PII minimization.
- Licensed commercial evidence requires a valid license and source-specific
  retention and redistribution terms.
- Government acquisition or scientific reports require an authorized transfer,
  classification marking, access policy, and approved processing boundary.
- CUI must not be sent to a public commercial AI service. Model routing must
  fail closed unless the approved environment and data policy allow it.
- The CDRL identified above is not a public source. Its content, attachments,
  Government-only information, and proprietary information are not collected,
  summarized, embedded, indexed, or used as model training data here.

## Presenter-safe conclusion

The prototype proves a production-shaped architecture, bounded execution,
governance controls, and traceable evidence. Exhibit B and QASP values are the
production acceptance targets. Meeting those targets requires Government-zone
integration, accredited security controls, representative load and endurance
tests, operational service records, and customer acceptance.
