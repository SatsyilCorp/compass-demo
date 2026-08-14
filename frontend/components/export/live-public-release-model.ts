export type PortablePreviewSourceRun = {
  source_id: string;
  run_id: string;
  snapshot_sha256?: string | null;
};

export type BrowserPortablePreviewManifest = {
  contract: "compass.browser-portable-preview.v1";
  evidence_mode: "live-public";
  generated_at: string;
  creation_environment: "browser";
  scope: string;
  server_release: false;
  approval_performed: false;
  destination_delivery: false;
  audit_receipt: null;
  source_run_ids: string[];
  source_snapshot_sha256: Array<{ source_id: string; sha256: string | null }>;
  record_count: number;
  records: Array<Record<string, unknown>>;
};

export function buildBrowserPortablePreview(
  rows: Array<Record<string, unknown>>,
  sourceRuns: readonly PortablePreviewSourceRun[],
  generatedAt: string,
): BrowserPortablePreviewManifest {
  return {
    contract: "compass.browser-portable-preview.v1",
    evidence_mode: "live-public",
    generated_at: generatedAt,
    creation_environment: "browser",
    scope: "Latest accepted bounded public record previews currently loaded in this browser",
    server_release: false,
    approval_performed: false,
    destination_delivery: false,
    audit_receipt: null,
    source_run_ids: sourceRuns.map((run) => run.run_id),
    source_snapshot_sha256: sourceRuns.map((run) => ({
      source_id: run.source_id,
      sha256: run.snapshot_sha256 ?? null,
    })),
    record_count: rows.length,
    records: rows,
  };
}

export function portablePreviewCsv(rows: Array<Record<string, unknown>>): string {
  if (rows.length === 0) return "";
  const columns = Object.keys(rows[0]!);
  const escape = (value: unknown) => {
    const normalized = Array.isArray(value) ? value.join("|") : value == null ? "" : String(value);
    return `"${normalized.replaceAll('"', '""')}"`;
  };
  return [columns.join(","), ...rows.map((row) => columns.map((column) => escape(row[column])).join(","))].join("\n");
}
