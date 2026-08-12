# Compass AWS cost model

Status: bounded planning estimate, not an invoice

Region: `us-east-1`

Pricing accessed: 2026-08-11

Currency: USD

This model separates deterministic browser replay, live workload cost, and the
monthly cost of keeping the AWS platform deployed. It applies no free tier,
credits, Savings Plans, private discounts, tax treatment, or support plan.

The inventory and document-workload estimates below price the current
`public-intel-20260812-full` deployment, which has 13 alarms and 2 dashboards
when Scale is enabled. One authentic public SBIR training job completed, but
Cost Explorer or Cost and Usage Report evidence has not yet reconciled the
bill. The values remain planning estimates rather than observed billing.

## Executive estimate

| Scenario | Modeled cost |
|---|---:|
| Browser replay after the site is deployed | $0.00 incremental AWS workload cost |
| One live document intake, default Lambda classifier | Up to $0.005 |
| One live 10K Scale Run | $0.01915314 |
| One live demo with one document intake and one 10K Scale Run | Up to $0.025 |
| One optional SageMaker training job, `ml.m5.large`, 30-minute hard limit | $0.0575 compute, plus storage and requests |
| Current public-intelligence live-object storage | About $0.0068/month at 294,668,909 bytes across the evidence and SBIR model prefixes |
| Low-use month, one writer, Scale enabled, four live demos | About $126.42 |
| Low-use month, writer plus reader, Scale enabled, four live demos | About $170.22 |

The live demo estimates are workload additions. They do not stop the fixed
monthly platform charges. Browser replay does not call live compute, so its
incremental workload cost is zero while the deployed platform still accrues
its hourly and monthly charges.

## Assumptions

- A month is 730 hours.
- The default database mode has one Aurora Serverless v2 writer at a minimum
  of 0.5 ACU. HA adds one reader with the same minimum.
- The Kinesis ticker stream remains deployed in on-demand mode.
- Scale enabled means thirteen standard CloudWatch alarms and two dashboards.
  Scale disabled means six alarms and one dashboard.
- WAF planning includes one web ACL and three billed rule-equivalents for the
  rate rule and managed rule group configuration.
- One low-use month contains four live demos and 5 GB-month of S3 Standard
  data. Every live demo contains one document intake and one 10K Scale Run.
- The document allowance assumes one file no larger than 10 MB, no more than
  50 API and Lambda requests, 20 Lambda GB-seconds, 10 S3 writes, 20 S3 reads,
  20 Step Functions transitions, 50 DynamoDB writes, 50 DynamoDB reads,
  50 KMS requests, and 0.005 GB of log ingestion. A 25 percent contingency is
  included in the $0.005 allowance.
- The 10K Scale Run estimate already includes a 25 percent contingency and
  comes from the versioned AWS Price List-backed runtime estimator.

## Monthly AWS operating floor

The following rates came from the AWS Price List Query API and official AWS
service pricing pages on 2026-08-11.

| Fixed item | Quantity | Rate | Monthly cost |
|---|---:|---:|---:|
| NAT gateway | 730 hours | $0.045/hour | $32.85 |
| Public IPv4 address | 730 hours | $0.005/hour | $3.65 |
| Aurora writer minimum | 365 ACU-hours | $0.12/ACU-hour | $43.80 |
| On-demand Kinesis stream | 730 hours | $0.04/stream-hour | $29.20 |
| Customer-managed KMS key | 1 key-month | $1.00/key-month | $1.00 |
| Secrets Manager | 1 secret-month | $0.40/secret-month | $0.40 |
| WAF | 1 ACL and 3 modeled rule-equivalents | $5.00/ACL-month and $1.00/rule-month | $8.00 |
| CloudWatch, Scale disabled | 6 alarms and 1 dashboard | $0.10/alarm-month and $3.00/dashboard-month | $3.60 |
| CloudWatch, Scale enabled | 13 alarms and 2 dashboards | $0.10/alarm-month and $3.00/dashboard-month | $7.30 |

| Deployment posture | Fixed monthly estimate |
|---|---:|
| One writer, Scale disabled | $122.50 |
| One writer, Scale enabled | $126.20 |
| Writer plus reader, Scale disabled | $166.30 |
| Writer plus reader, Scale enabled | $170.00 |

The HA calculation adds `365 ACU-hours * $0.12 = $43.80` for the reader.

The low-use total for the normal live demonstration posture is:

```text
one writer, Scale enabled       $126.200
four live demos, $0.025 each       0.100
5 GB-month S3 Standard              0.115
                                      -----
low-use month                    $126.415, rounded to $126.42
```

For HA, replace the first line with $170.00, giving $170.22 after rounding.
These are planning floors, not maximum invoices.

## Live demonstration calculations

### Deterministic replay

The frontend replay uses versioned synthetic evidence and browser execution.
It causes no API, Lambda, Step Functions, SageMaker, or Databricks workload.
Its incremental cloud workload cost is $0.00. Existing CloudFront, WAF,
database, NAT, Kinesis, logging, and other deployed resources still accrue.

### Default live AWS path

The default `MlOpsMode=demo` runs the bounded classical document classifier in
Lambda. One conservative document intake is capped at $0.005 by the assumptions
above. The current 10K Scale Run planning estimate is $0.01915314. Therefore:

```text
$0.005 + $0.01915314 = $0.02415314
planning presentation value = $0.025 per live demo
```

The runtime also has the following profile estimates. Each already includes a
25 percent contingency.

| Scale profile | Records | Planned incremental cost | Server-enforced envelope |
|---|---:|---:|---:|
| 1K | 1,000 | $0.01898818 | $0.10 |
| 10K | 10,000 | $0.01915314 | $0.25 |
| 100K | 100,000 | $0.03380464 | $1.00 |
| 1M | 1,000,000 | $0.13937136 | $10.00 |

### Optional SageMaker path

The optional adapter requests one `ml.m5.large`, sets one instance, and enforces
a 1,800 second maximum. The official AWS Price List Query API returned
`$0.115/hour` for SKU `JMCWJEAPVJNFJ5P4`, usage type
`USE1-Train:ml.m5.large`, on 2026-08-11.

```text
0.5 hours * $0.115/hour = $0.0575 maximum instance compute per submitted job
```

Adding that compute to the $0.025 default live demo gives a modeled subtotal
of $0.0825. Training volume storage, S3, ECR, logs, network transfer, and any
other service usage remain separate. No always-on SageMaker endpoint exists in
the current design, so no endpoint-month is included.

The authentic SBIR session submitted five bounded jobs while packaging and
runtime defects were diagnosed. Four failed and one completed. SageMaker
reported 542 aggregate billable seconds: 125, 129, 89, 90, and 109 seconds.
Using the same $0.115 per hour rate gives:

```text
542 seconds / 3,600 * $0.115 = $0.01731 modeled training compute
```

The successful job accounts for 109 seconds, or about $0.00348 of that modeled
compute. These are rate-based estimates, not reconciled billed values.

### Public evidence and cited intelligence

The public collectors run locally against no-fee public APIs and downloads, so
the completed collection incurred no AWS compute charge. After the corrected
OpenAlex, PubMed, OSTI, USPTO, and official ONR website snapshots were promoted,
the encrypted public-intelligence prefix contained 232,017,568 bytes across 87
current S3 objects. The separate SBIR training and registry prefix contained
62,651,341 bytes across 7 current objects. At the modeled S3 Standard rate of
$0.023 per GB-month, their combined current-object footprint adds about $0.0068
per month. Prior object versions, API requests, KMS requests, logs, and future
snapshots remain separate.

The funding forecast was trained locally from observed USAspending quarterly
obligations and registered as a candidate in SageMaker Model Registry. The
separate SBIR transition candidate was trained on SageMaker and registered as
`PendingManualApproval`. No endpoint exists, so neither candidate adds an
endpoint-hour charge. S3 storage, KMS requests, registry API activity, and the
training compute above remain part of normal service usage.

Each cited explanation uses one API Gateway request, one bounded Lambda
invocation, S3 manifest and index reads that are cached within a warm runtime,
KMS decryption through S3, and at most one Amazon Bedrock request capped at 500
output tokens. Exact Bedrock cost depends on the selected model and input and
output token counts. The runtime returns a deterministic cited answer if the
model is unavailable, and no always-on generative compute is provisioned.

## What is not included

- Aurora storage, backup storage above the included amount, and database I/O.
- NAT data processing and internet or cross-region transfer.
- CloudFront requests and data transfer.
- WAF request charges.
- Bedrock token use if an optional generative path is invoked.
- GuardDuty, Security Hub, and Macie when the optional account security
  baseline is enabled.
- SageMaker storage, ECR, logs, data transfer, and optional endpoint cost.
- CloudWatch custom metrics, log retention, Logs Insights scans, and alarms
  beyond the template inventory.
- S3 requests and storage above the low-use assumptions.
- Tax, AWS Support, discounts, enterprise agreements, and free usage.

## Reconciliation rule

Use this document for a pre-demo planning gate. After a live run, reconcile the
run receipt with AWS Cost and Usage Report or Cost Explorer when delayed billing
records are available. Label the first value `estimated` and the later value
`billed` only when account billing evidence supports it.

## Official sources

All links were accessed on 2026-08-11.

- [AWS Price List Query API](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/using-price-list-query-api.html)
- [Amazon Aurora pricing](https://aws.amazon.com/rds/aurora/pricing/)
- [Amazon VPC pricing](https://aws.amazon.com/vpc/pricing/)
- [Amazon Kinesis Data Streams pricing](https://aws.amazon.com/kinesis/data-streams/pricing/)
- [AWS KMS pricing](https://aws.amazon.com/kms/pricing/)
- [AWS Secrets Manager pricing](https://aws.amazon.com/secrets-manager/pricing/)
- [AWS WAF pricing](https://aws.amazon.com/waf/pricing/)
- [Amazon CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/)
- [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/)
- [AWS Lambda pricing](https://aws.amazon.com/lambda/pricing/)
- [AWS Step Functions pricing](https://aws.amazon.com/step-functions/pricing/)
- [Amazon DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/)
- [Amazon API Gateway pricing](https://aws.amazon.com/api-gateway/pricing/)
- [Amazon SageMaker AI pricing](https://aws.amazon.com/sagemaker/ai/pricing/)

The versioned service rates used by the Scale Run estimator are in
`src/common/python/compass_common/aws_prices_us_east_1.json`. AWS states that
the Price List APIs are informational and the service pricing page controls if
the two differ.
