# AWS public SBIR transition model receipt

Status: trained, registered candidate, not approved, not deployed

## Outcome

SageMaker training job
`compass-doc-sbir-transition-20260812-0134` completed successfully in Satsyil
AWS. It used 11,287 authentic public Navy SBIR examples and wrote a
KMS-encrypted model artifact. SageMaker Model Registry package version 2 is
`PendingManualApproval`. There is no model endpoint.

The candidate estimates whether a public Navy SBIR Phase I record is followed
by a public Phase II or Phase III record for the same normalized organization
and exact topic within 36 months. It does not estimate ONR mission success,
commercialization, causation, source-selection merit, or an internal decision.

## Evidence

| Item | Value |
|---|---|
| Training job ARN | `arn:aws:sagemaker:us-east-1:551185375163:training-job/compass-doc-sbir-transition-20260812-0134` |
| Training status | `Completed` |
| Billable duration | 109 seconds |
| Runtime | Python 3.10.20, scikit-learn 1.4.2, NumPy 2.1.0 |
| Managed image digest | `sha256:b77026dc1972b759579139314c03482103809a80fa52e2ee696c52e1270a626d` |
| Model package ARN | `arn:aws:sagemaker:us-east-1:551185375163:model-package/compass-demo-public-sbir-transition/2` |
| Approval state | `PendingManualApproval` |
| Endpoint count | 0 |
| Dataset digest | `0dda670313a1e9d3098b4d4e0b2048a3c7d7b4186de87731afad53f9f77400db` |
| Model artifact digest | `652665a26f65230c2eb6019c65ca706bdb248414ed71b8d3365a05431045fd0a` |
| Registry bundle digest | `51a3fcc71c46ecb514b2c3866f5153f7771838d07b43fc0807f4a89a5d6b424b` |

## Evaluation

The split is chronological and group-safe:

| Partition | Period | Records |
|---|---|---:|
| Fit | 2002 to 2014 | 6,776 |
| Calibration | 2014 to 2018 | 2,251 |
| Test | 2019 to 2023 | 2,260 |

| Holdout metric | Value |
|---|---:|
| ROC AUC | 0.62642675 |
| Brier score | 0.26166652 |
| F1 | 0.57034796 |
| Balanced accuracy | 0.55787966 |
| Precision | 0.43036530 |
| Recall | 0.84529148 |

These modest measurements are model evidence, not a production accuracy
claim. Deployment requires independent validation, subgroup review, security
review, Government data authorization, a human approval decision, monitoring,
and an explicit endpoint cost gate.

## Controls exercised

- One `ml.m5.large` instance with a 1,800-second hard stop
- Network isolation enabled
- Inter-container traffic encryption enabled
- KMS encryption for input, training volume, output, and registry bundle
- Exact public dataset and source hashes
- CloudWatch training log stream
- Immutable Model Registry version and human approval gate
- No automatic promotion and no endpoint

Four earlier bounded attempts failed while the framework bootstrap, Python
runtime, logging permission, and incomplete source archive were diagnosed.
Their billable durations were 125, 129, 89, and 90 seconds. The incomplete
registry package version 1 was rejected before deployment. These events remain
part of the operational audit trail.

## Reproduction

`mlops/sagemaker/public_sbir_transition/submit_training.py` produces a dry-run
job receipt by default. AWS mutation requires its explicit `--submit` flag, an
exact account ID, a named profile, a unique S3 prefix, the KMS key ARN, the
dataset, and the execution role. `run.sh`, `train.py`, and `inference.py` define
the managed-container contracts.
