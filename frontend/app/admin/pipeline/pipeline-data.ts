/**
 * Data mirror of the deployed intake state machine
 * (statemachines/intake.asl.yaml) — an AWS Step Functions EXPRESS workflow
 * fired by RawObjectCreatedRule (every object created in the raw bucket) and
 * by POST /ingest/simulate. This is a build-time snapshot of the real ASL
 * definition, not a live parse of it — kept in one file so drift is a single
 * diff to review.
 */

export type StateKind = "Task" | "Choice" | "Succeed" | "Fail";

export type PipelineState = {
  id: string;
  kind: StateKind;
  comment: string;
  lambda?: "IntakeFunction" | "QualityGateFunction";
  action?: string;
  next?: string;
  choices?: { on: string; next: string }[];
  default?: string;
  retry?: string;
  catch?: string;
  /** Trimmed excerpt of the real statemachines/intake.asl.yaml for this state. */
  excerpt: string;
};

export const PIPELINE_STATES: PipelineState[] = [
  {
    id: "Fetch",
    kind: "Task",
    lambda: "IntakeFunction",
    action: "fetch",
    comment: "Read the S3 object, normalize the schema variant, upsert grants_raw.",
    next: "FetchGate",
    retry: "Lambda faults × 3 (backoff ×2) · States.Timeout × 2",
    catch: "States.ALL → Failed",
    excerpt:
      "Fetch:\n" +
      "  Type: Task\n" +
      "  Resource: arn:aws:states:::lambda:invoke\n" +
      "  Parameters:\n" +
      "    FunctionName: ${IntakeFunctionArn}\n" +
      "    Payload: { action: fetch, detail.$: $.detail }\n" +
      "  Next: FetchGate",
  },
  {
    id: "FetchGate",
    kind: "Choice",
    comment: "Objects that are not ingest drops (exports, RMF artifacts) end here, not as a failure.",
    choices: [
      { on: "status = skipped", next: "Skipped" },
      { on: "status = ok", next: "Validate" },
    ],
    default: "Failed",
    excerpt:
      "FetchGate:\n" +
      "  Type: Choice\n" +
      "  Choices:\n" +
      "    - Variable: $.status\n" +
      "      StringEquals: skipped\n" +
      "      Next: Skipped\n" +
      "    - Variable: $.status\n" +
      "      StringEquals: ok\n" +
      "      Next: Validate\n" +
      "  Default: Failed",
  },
  {
    id: "Validate",
    kind: "Task",
    lambda: "QualityGateFunction",
    action: "validate",
    comment: "Quality rules → grant_quality + row verdicts + the gate decision.",
    next: "QualityGate",
    retry: "Lambda faults × 3 (backoff ×2) · States.Timeout × 2",
    catch: "States.ALL → Failed",
    excerpt:
      "Validate:\n" +
      "  Type: Task\n" +
      "  Resource: arn:aws:states:::lambda:invoke\n" +
      "  Parameters:\n" +
      "    FunctionName: ${QualityGateFunctionArn}\n" +
      "    Payload: { action: validate, batch_id.$: $.batch_id, run_id.$: $.run_id, ... }\n" +
      "  Next: QualityGate",
  },
  {
    id: "QualityGate",
    kind: "Choice",
    comment:
      "Batch row pass-rate at/above the threshold curates; below it the whole batch is held. Rows that failed a rule are marked quarantined either way and never curated.",
    choices: [
      { on: "gate = pass", next: "Persist" },
      { on: "gate = fail", next: "Quarantine" },
    ],
    default: "Failed",
    excerpt:
      "QualityGate:\n" +
      "  Type: Choice\n" +
      "  Choices:\n" +
      "    - Variable: $.gate\n" +
      "      StringEquals: pass\n" +
      "      Next: Persist\n" +
      "    - Variable: $.gate\n" +
      "      StringEquals: fail\n" +
      "      Next: Quarantine\n" +
      "  Default: Failed",
  },
  {
    id: "Persist",
    kind: "Task",
    lambda: "IntakeFunction",
    action: "persist",
    comment: "Insert gate-approved rows into grants_curated (RLS + Titan v2 embeddings).",
    next: "Curated",
    retry: "Lambda faults × 3 (backoff ×2) · States.Timeout × 2",
    catch: "States.ALL → Failed",
    excerpt:
      "Persist:\n" +
      "  Type: Task\n" +
      "  Parameters:\n" +
      "    FunctionName: ${IntakeFunctionArn}\n" +
      "    Payload: { action: persist, batch_id.$: $.batch_id, rows_passed.$: $.rows_passed,\n" +
      "               overall_score.$: $.overall_score }\n" +
      "  Next: Curated",
  },
  {
    id: "Quarantine",
    kind: "Task",
    lambda: "QualityGateFunction",
    action: "quarantine",
    comment: "Batch below threshold — held in grants_raw with a batch anomaly. Nothing is persisted.",
    next: "Quarantined",
    retry: "Lambda faults × 3 (backoff ×2)",
    catch: "States.ALL → Failed",
    excerpt:
      "Quarantine:\n" +
      "  Type: Task\n" +
      "  Parameters:\n" +
      "    FunctionName: ${QualityGateFunctionArn}\n" +
      "    Payload: { action: quarantine, batch_id.$: $.batch_id, overall_score.$: $.overall_score,\n" +
      "               threshold.$: $.threshold }\n" +
      "  Next: Quarantined",
  },
  {
    id: "Curated",
    kind: "Succeed",
    comment: "Batch passed the gate and its clean rows are in grants_curated.",
    excerpt: "Curated:\n  Type: Succeed",
  },
  {
    id: "Quarantined",
    kind: "Succeed",
    comment: "Batch was held. Nothing curated; every row retained with its verdict for review.",
    excerpt: "Quarantined:\n  Type: Succeed",
  },
  {
    id: "Skipped",
    kind: "Succeed",
    comment: "The S3 object was not an ingest drop (e.g. it landed under exports/, rmf/, quarantine/, tmp/).",
    excerpt: "Skipped:\n  Type: Succeed",
  },
  {
    id: "Failed",
    kind: "Fail",
    comment:
      "Every Task retries transient Lambda faults and catches everything else here — an ingest that silently \"succeeds\" after an error is worse than one that stops loudly.",
    excerpt: 'Failed:\n  Type: Fail\n  Error: CompassIntakeFailed\n  Cause: "Intake pipeline failed. ..."',
  },
];

export const HAPPY_PATH = ["Fetch", "FetchGate", "Validate", "QualityGate", "Persist", "Curated"] as const;

export function stateById(id: string): PipelineState {
  const s = PIPELINE_STATES.find((x) => x.id === id);
  if (!s) throw new Error(`unknown pipeline state: ${id}`);
  return s;
}

/**
 * Environment variables the intake/quality-gate Lambdas actually read —
 * src/functions/quality_gate/app.py + rules.py — the levers that decide
 * gate/curate/quarantine, not just a description of the workflow.
 */
export const RUNTIME_CONFIG: { key: string; value: string; note: string }[] = [
  {
    key: "RAW_BUCKET",
    value: "the intake landing bucket",
    note: "RawObjectCreatedRule (EventBridge) fires the state machine on every object created here.",
  },
  {
    key: "QUALITY_PASS_THRESHOLD",
    value: "90 (default)",
    note: "Batch row pass-rate needed to curate — this is what the QualityGate choice's $.gate is computed from.",
  },
  {
    key: "QUALITY_FY_MIN / QUALITY_FY_MAX",
    value: "2015 / 2035 (default)",
    note: "Inclusive fiscal-year window checked by the valid_fiscal_year_range rule.",
  },
  {
    key: "QUALITY_AMOUNT_MAX",
    value: "$100,000,000 (default)",
    note: "Upper sanity bound on a single award, checked by amount_usd_within_bounds.",
  },
  {
    key: "EMBED_ON_INGEST",
    value: "true (default)",
    note: "Persist embeds each curated abstract with Titan v2 for the RAG chat route (element 6).",
  },
  {
    key: "EMBED_MAX_ROWS",
    value: "200 (default)",
    note: "Cap on embedding calls per batch — a slow model call never holds the write transaction open.",
  },
];
