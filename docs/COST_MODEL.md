# Compass AWS cost model

Status: price-backed forecast with Satsyil runtime reconciliation
Region: `us-east-1`
Price snapshot captured: `2026-08-11T05:30:00Z`
Price source: AWS Price List Query API

This model separates fixed monthly platform cost from incremental Scale Run cost. It applies no free tier or private discount. It is intended as a conservative launch gate, not a billing statement.

## Fixed monthly platform estimate

| Deployment mode | Aurora topology | Estimated fixed cost per 730-hour month |
|---|---|---:|
| Demo | One Aurora Serverless v2 writer at 0.5 minimum ACU | $119.90 |
| HA | One writer and one reader, each at 0.5 minimum ACU | $163.70 |

The fixed estimate includes one NAT gateway, one public IPv4 address, Aurora
minimum capacity, one on-demand Kinesis stream, one KMS key, one Secrets
Manager secret, one WAF web ACL with three modeled rules, and eleven CloudWatch
alarms. The deployed observability surface also includes two dashboards.

The Satsyil stack was deployed in HA mode on 2026-08-11 with one Aurora writer
and one reader. The $163.70 figure remains a forecast for a 730-hour month. It
is not observed billing.

It excludes usage-sensitive storage, data transfer, API traffic, Lambda work, Bedrock model use, tax, support plans, optional account-level security services, discounts, and free tier. CloudFront has no modeled fixed monthly charge, but requests and transfer are billed when used.

## Incremental Scale Run estimate

| Profile | Total records | Exact partitions | Estimated run cost | Enforced envelope |
|---|---:|---:|---:|---:|
| 1K | 1,000 | 6 | $0.01898818 | $0.10 |
| 10K | 10,000 | 6 | $0.01915314 | $0.25 |
| 100K | 100,000 | 11 | $0.03380464 | $1.00 |
| 1M | 1,000,000 | 41 | $0.13937136 | $10.00 |

Running all four profiles once is estimated at $0.21131732 in incremental AWS usage. The server still denies a run when its fresh estimate exceeds either its profile envelope or the deployment hard cap.

## Satsyil runtime reconciliation

| Profile | Duration | Planned estimate | Accrued model estimate | Envelope |
|---|---:|---:|---:|---:|
| 1K | 21.351 s | $0.01898818 | $0.01227206 | $0.10 |
| 10K | 20.329 s | $0.01915314 | $0.01232190 | $0.25 |
| 100K | 25.853 s | $0.03380464 | $0.01785423 | $1.00 |
| 1M | 72.615 s | $0.13937136 | $0.05309299 | $10.00 |
| **Total** | 140.148 s | **$0.21131732** | **$0.09554118** | n/a |

All four runs completed below their enforced envelopes. The planned estimate
is computed before launch and includes a 25 percent contingency. The accrued
model estimate uses observed service quantities recorded by the terminal run.
Neither value is a bill or a Cost Explorer reconciliation.

Every estimate includes a 25 percent contingency and line-item evidence for Lambda ARM compute and requests, S3 storage and requests, SQS requests, Step Functions transitions, DynamoDB reads, writes, and storage, Athena bytes scanned, CloudWatch log ingestion, KMS requests, and HTTP API requests.

## Runtime reconciliation

Each terminal Scale Run records observed service quantities and an accrued
model estimate. Billing reconciliation remains labeled pending until delayed
account billing data is available. The product never labels an estimate as
billed cost.

## Reproduce the estimates

```bash
PYTHONPATH=src/common/python python3 scripts/estimate_scale_cost.py --profile 10k
PYTHONPATH=src/common/python python3 scripts/estimate_scale_cost.py --idle-month --database-mode ha
```

The versioned price evidence is stored in `src/common/python/compass_common/aws_prices_us_east_1.json`.

## Official service pricing pages

- [AWS Lambda pricing](https://aws.amazon.com/lambda/pricing/)
- [Amazon S3 pricing](https://aws.amazon.com/s3/pricing/)
- [Amazon SQS pricing](https://aws.amazon.com/sqs/pricing/)
- [AWS Step Functions pricing](https://aws.amazon.com/step-functions/pricing/)
- [Amazon DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/)
- [Amazon Athena pricing](https://aws.amazon.com/athena/pricing/)
- [Amazon CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/)
- [Amazon Aurora pricing](https://aws.amazon.com/rds/aurora/pricing/)
- [Amazon VPC pricing](https://aws.amazon.com/vpc/pricing/)
