import type {
  PublicAcquisitionList,
  PublicAcquisitionRecord,
  PublicEvidenceThread,
  PublicSourceHealth,
} from "@/lib/api";
import type { OperationsSignalsResponse } from "@/lib/types";

export const DEMO_FAILURE_SOURCE_ID = "grants-gov-onr";

const DEMO_NOW = "2026-08-13T20:45:00.000Z";
const DEMO_MODEL_VERSION = "demo-doc-nb-replay-v1";

type DemoSource = {
  source_id: string;
  label: string;
  authority: string;
  cadence_seconds: number;
  data_kind: string;
  record: NonNullable<PublicAcquisitionRecord["record_preview"]>[number];
  document_class: string;
  confidence: number;
};

const DEMO_SOURCES: DemoSource[] = [
  {
    source_id: "usaspending-onr-grants",
    label: "USAspending award replay",
    authority: "Synthetic replay shaped like USAspending",
    cadence_seconds: 300,
    data_kind: "Synthetic public-award schema fixture",
    document_class: "investment_brief",
    confidence: 0.91,
    record: {
      source_record_id: "DEMO-AWARD-0001",
      record_type: "award",
      title: "Synthetic maritime autonomy sensor award",
      description: "Synthetic award record for a failure-safe demonstration.",
      recipient_name: "Demo Maritime Research Lab",
      award_amount_usd: 2450000,
      topics: ["maritime autonomy", "sensor fusion"],
      identity_keys: ["AWARD#DEMO-N0001426-0001", "RECIPIENT#DEMO-LAB-01"],
    },
  },
  {
    source_id: "grants-gov-onr",
    label: "Grants.gov opportunity replay",
    authority: "Synthetic replay shaped like Grants.gov",
    cadence_seconds: 900,
    data_kind: "Synthetic funding-opportunity schema fixture",
    document_class: "grant_abstract",
    confidence: 0.96,
    record: {
      source_record_id: "DEMO-OPPORTUNITY-0001",
      record_type: "funding_opportunity",
      title: "Synthetic maritime autonomy sensor opportunity",
      description: "Synthetic opportunity linked to the demo award by an explicit fixture key.",
      status: "posted",
      topics: ["maritime autonomy", "sensor fusion"],
      identity_keys: ["AWARD#DEMO-N0001426-0001"],
    },
  },
  {
    source_id: "federal-register-onr",
    label: "Federal Register notice replay",
    authority: "Synthetic replay shaped like Federal Register",
    cadence_seconds: 1800,
    data_kind: "Synthetic regulatory-notice schema fixture",
    document_class: "technical_report",
    confidence: 0.84,
    record: {
      source_record_id: "DEMO-NOTICE-0001",
      record_type: "regulatory_notice",
      title: "Synthetic maritime testing notice",
      description: "Synthetic notice used to rehearse cross-source review.",
      topics: ["maritime testing", "environmental review"],
      identity_keys: [],
    },
  },
  {
    source_id: "crossref-onr",
    label: "Crossref publication replay",
    authority: "Synthetic replay shaped like Crossref",
    cadence_seconds: 3600,
    data_kind: "Synthetic publication-metadata schema fixture",
    document_class: "publication_summary",
    confidence: 0.93,
    record: {
      source_record_id: "DEMO-DOI-0001",
      record_type: "publication",
      title: "Synthetic sensor fusion publication",
      description: "Synthetic publication metadata for deterministic replay.",
      citation_count: 12,
      topics: ["sensor fusion", "maritime testing"],
      identity_keys: ["DOI#10.0000/COMPASS.DEMO.0001"],
    },
  },
];

function completedRun(source: DemoSource): PublicAcquisitionRecord {
  return {
    contract: "compass.public-acquisition.v1",
    run_id: `demo-${source.source_id}-accepted`,
    source_id: source.source_id,
    source_label: `DEMO REPLAY | ${source.label}`,
    source: `demo://${source.source_id}`,
    status: "completed",
    stage: "accepted-snapshot",
    started_at: "2026-08-13T20:44:52.000Z",
    updated_at: DEMO_NOW,
    watermark: DEMO_NOW,
    snapshot_sha256: "d".repeat(64),
    record_count: 1,
    total_available: 1,
    profile: "quick",
    requested_records: 1,
    pages_fetched: 1,
    duration_ms: 1250,
    added_records: 1,
    changed_records: 0,
    unchanged_records: 0,
    not_observed_records: 0,
    has_more_source_pages: false,
    review_flag_count: source.source_id === "usaspending-onr-grants" ? 1 : 0,
    review_flags: source.source_id === "usaspending-onr-grants"
      ? [{ source_record_id: source.record.source_record_id, recipient_name: source.record.recipient_name, award_amount_usd: source.record.award_amount_usd, reasons: ["synthetic high-value review rehearsal"] }]
      : [],
    record_preview: [source.record],
    identity_summary: {
      indexed_records: 1,
      identity_key_count: source.record.identity_keys?.length ?? 0,
      link_method: "synthetic exact key fixture",
      governance_owner: "Demo Portfolio Data Product Owner",
      governance_steward: "Demo Public Evidence Data Steward",
      classification: "SYNTHETIC",
    },
    classification_status: "completed",
    classification_summary: {
      status: "completed",
      run_id: `demo-ml-${source.source_id}`,
      model_version: DEMO_MODEL_VERSION,
      model_registered: false,
      record_count: 1,
      class_counts: { [source.document_class]: 1 },
      review_required_count: 0,
      mean_confidence: source.confidence,
      artifact_uri: `demo://classifications/${source.source_id}.json`,
      artifact_sha256: "c".repeat(64),
      preview: [{
        source_record_id: source.record.source_record_id,
        document_class: source.document_class,
        confidence: source.confidence,
        review_required: false,
      }],
      disclosure: "Synthetic classifier replay. No model endpoint was invoked.",
    },
    poll_mode: "scheduled-micro-batch",
    scope_disclosure: "Synthetic replay fixture. No public API request was made.",
  };
}

function failedRun(source: DemoSource): PublicAcquisitionRecord {
  return {
    contract: "compass.public-acquisition.v1",
    run_id: `demo-${source.source_id}-failed`,
    source_id: source.source_id,
    source_label: `DEMO FAILURE | ${source.label}`,
    source: `demo://${source.source_id}/timeout`,
    status: "failed",
    stage: "source-acquisition",
    started_at: DEMO_NOW,
    updated_at: DEMO_NOW,
    profile: "quick",
    duration_ms: 3000,
    failure_code: "SyntheticTimeoutRehearsal",
    poll_mode: "scheduled-micro-batch",
    scope_disclosure: "Synthetic failure rehearsal. The prior accepted demo snapshot remains active.",
  };
}

function evidenceThreads(): PublicEvidenceThread[] {
  return [
    {
      thread_id: "demo-exact-award-thread",
      match_type: "exact-identity",
      identity_key: "AWARD#DEMO-N0001426-0001",
      match_score: 1,
      review_status: "verified-key",
      explanation: "Synthetic records share an explicit demo identity key.",
      shared_terms: [],
      owner: "Demo Portfolio Data Product Owner",
      steward: "Demo Public Evidence Data Steward",
      facts: DEMO_SOURCES.slice(0, 2).map((source) => ({
        source_id: source.source_id,
        source_label: `DEMO REPLAY | ${source.label}`,
        run_id: `demo-${source.source_id}-accepted`,
        record_id: source.record.source_record_id,
        record_type: source.record.record_type ?? "record",
        title: source.record.title ?? source.record.source_record_id,
        model_version: DEMO_MODEL_VERSION,
        document_class: source.document_class,
      })),
    },
    {
      thread_id: "demo-candidate-topic-thread",
      match_type: "explainable-candidate",
      identity_key: null,
      match_score: 0.67,
      review_status: "analyst-review",
      explanation: "Synthetic records share normalized maritime-testing terms and require review.",
      shared_terms: ["maritime", "testing"],
      owner: "Demo Portfolio Data Product Owner",
      steward: "Demo Public Evidence Data Steward",
      facts: DEMO_SOURCES.slice(2, 4).map((source) => ({
        source_id: source.source_id,
        source_label: `DEMO REPLAY | ${source.label}`,
        run_id: `demo-${source.source_id}-accepted`,
        record_id: source.record.source_record_id,
        record_type: source.record.record_type ?? "record",
        title: source.record.title ?? source.record.source_record_id,
        model_version: DEMO_MODEL_VERSION,
        document_class: source.document_class,
      })),
    },
  ];
}

export function buildAcquisitionDemoReplay(
  failureSourceId: string | null = null,
): PublicAcquisitionList {
  const accepted = DEMO_SOURCES.map(completedRun);
  const failedSource = DEMO_SOURCES.find((source) => source.source_id === failureSourceId);
  const health: PublicSourceHealth[] = DEMO_SOURCES.map((source) => ({
    source_id: source.source_id,
    label: `DEMO REPLAY | ${source.label}`,
    authority: source.authority,
    endpoint: `demo://${source.source_id}`,
    cadence_seconds: source.cadence_seconds,
    data_kind: source.data_kind,
    model_use: "Synthetic classification and relationship rehearsal",
    status: source.source_id === failureSourceId ? "failed" : "healthy",
    last_attempt_at: DEMO_NOW,
    last_accepted_at: DEMO_NOW,
    age_seconds: 0,
    success_rate: source.source_id === failureSourceId ? 0.5 : 1,
    average_duration_ms: source.source_id === failureSourceId ? 3000 : 1250,
    latest_run_id: source.source_id === failureSourceId
      ? `demo-${source.source_id}-failed`
      : `demo-${source.source_id}-accepted`,
    latest_record_count: 1,
    latest_added_records: 1,
    latest_changed_records: 0,
    latest_review_flag_count: source.source_id === "usaspending-onr-grants" ? 1 : 0,
    classification_status: "completed",
    model_version: DEMO_MODEL_VERSION,
    has_more_source_pages: false,
  }));
  return {
    contract: "compass.public-acquisition-list.v1",
    mode: "replay",
    generated_at: DEMO_NOW,
    schedule: "operator-controlled synthetic replay",
    source_transport: "Local deterministic fixture. No external API request.",
    display_refresh: "one-second visual projection",
    source_health: health,
    evidence_threads: evidenceThreads(),
    acquisitions: failedSource ? [failedRun(failedSource), ...accepted] : accepted,
  };
}

export function buildAcquisitionDemoSignals(
  failureSourceId: string | null = null,
): OperationsSignalsResponse {
  const failure = failureSourceId
    ? [{
      event_id: `demo-failure-${failureSourceId}`,
      signal_type: "public_acquisition_failure_rehearsal",
      severity: "critical" as const,
      title: "DEMO FAILURE: source timeout rehearsed",
      message: "A synthetic timeout was recorded. The previous accepted snapshot remains available to every decision surface.",
      status: "open" as const,
      occurred_at: DEMO_NOW,
      updated_at: DEMO_NOW,
      run_id: `demo-${failureSourceId}-failed`,
      run_kind: "public_acquisition",
      href: "/admin/acquisition/?mode=demo",
      source: "Synthetic failure rehearsal",
      deliveries: [
        { channel: "in_app" as const, state: "delivered" as const, attempted_at: DEMO_NOW, delivered_at: DEMO_NOW, detail: "Visible only in demo replay." },
        { channel: "email" as const, state: "not_configured" as const, attempted_at: null, delivered_at: null, detail: "No email is sent by a synthetic rehearsal." },
      ],
      acknowledged_at: null,
      acknowledged_by: null,
    }]
    : [];
  const signals = [
    ...failure,
    {
      event_id: "demo-acquisition-accepted",
      signal_type: "public_acquisition_replay",
      severity: "info" as const,
      title: "DEMO REPLAY: synthetic snapshot accepted",
      message: "Four deterministic fixture records passed the replay path without calling a public API.",
      status: "open" as const,
      occurred_at: DEMO_NOW,
      updated_at: DEMO_NOW,
      run_id: "demo-usaspending-onr-grants-accepted",
      run_kind: "public_acquisition",
      href: "/admin/acquisition/?mode=demo",
      source: "Synthetic acquisition replay",
      deliveries: [{ channel: "in_app" as const, state: "delivered" as const, attempted_at: DEMO_NOW, delivered_at: DEMO_NOW, detail: "Browser-local demonstration evidence." }],
      acknowledged_at: null,
      acknowledged_by: null,
    },
  ];
  return {
    contract: "compass.operations.signals.v1",
    mode: "replay",
    generated_at: DEMO_NOW,
    unread_count: signals.length,
    signals,
    disclosure: "Synthetic replay. These notifications do not represent a cloud failure or external delivery.",
  };
}
