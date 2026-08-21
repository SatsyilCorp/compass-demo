# AWS public SBIR transition model receipt

Status: trained, registered candidate, executed on a current public cohort, not approved, no endpoint

## Outcome

SageMaker training job
`compass-doc-sbir-transition-20260812-0134` completed successfully in Satsyil
AWS. It used 11,287 authentic public Navy SBIR examples and wrote a
KMS-encrypted model artifact. SageMaker Model Registry package version 2 is
`PendingManualApproval`. There is no model endpoint.

Compass also executed package version 2 through an ephemeral, network-isolated
SageMaker Batch Transform job on 25 PII-minimized, label-excluded public Navy
Phase I records dated after the model evaluation cutoff. Execution
`sbir-batch-20260812T215434-d6230e7c` completed with 25 of 25 responses in 72
observed transform seconds. The temporary SageMaker Model was deleted, the
single-run lock was released, package approval stayed unchanged, and no
endpoint was created. This is current-cohort scoring evidence, not an
independent accuracy evaluation and not a production approval.

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
| Training-recorded model artifact digest | `652665a26f65230c2eb6019c65ca706bdb248414ed71b8d3365a05431045fd0a` |
| Model artifact source version | `6ki61OUXqpqujj5uHes3k0Sz2AoryxlB` |
| Registry bundle digest | `51a3fcc71c46ecb514b2c3866f5153f7771838d07b43fc0807f4a89a5d6b424b` |
| Model-card digest | `5f2a26edfd17035054d6e056be9bdc41dd2781958825eb10910ab5322d8a5bc4` |

## Bounded execution evidence

| Item | Value |
|---|---|
| Execution ID | `sbir-batch-20260812T215434-d6230e7c` |
| Transform job ARN | `arn:aws:sagemaker:us-east-1:551185375163:transform-job/sbir-batch-20260812T215434-d6230e7c` |
| Terminal status | `COMPLETED` |
| Input records | 25 public, PII-minimized, post-cutoff Phase I records |
| Prediction records | 25, all marked for human review |
| Positive proxy signals | 21 of 25 at the candidate threshold |
| Observed probability range | 0.42408883 to 0.73451578 |
| Observed mean probability | 0.593405744 |
| Observed duration | 72 seconds |
| Estimate-only compute | $0.0023 at the configured $0.115 per hour rate |
| Current scoring source digest | `fcfb8499daacc1ab1b83c2b3d250572b2379cc7f3f9cc954bc7fa0b443b7b28f` |
| Candidate pool digest | `45df1368c1dced57ee99bb16f74ce2d8596587a4a177462011394b1526ee5aba` |
| Input digest | `199564f9a92ce0d74e411772d04da76efc00ad0065e92121ac31447cb90a42b6` |
| Output digest | `ea1dfe25474a35b8582d04125a2aaee1b52c79003dd9ca550114da4a03e5f489` |
| Receipt digest | `19ba154538eb0a4f2e35c3c41555cbc113052d3e04468f82449ea9a5357f42ac` |
| Temporary model | Deleted after receipt reconciliation |
| Endpoint count | 0 |

The values are public transition signals, not ONR mission-success predictions.
The 25 current records were selected reproducibly as the newest eligible
public Phase I record per normalized organization and exact topic after
2023-12-31 and through 2026-08-12. Outcome labels and later follow-on awards
were excluded from the scoring input. Earlier smoke and failed receipts remain
durable in the protected execution history.

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
- Exact package ARN, model object version, artifact digest, and image digest
- CloudWatch training log stream
- Immutable Model Registry version and human approval gate
- Per-run EventBridge Scheduler cleanup guard for timeout, cleanup, and lock release
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
