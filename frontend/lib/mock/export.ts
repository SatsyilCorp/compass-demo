/**
 * POST /export — fixture. Element 7. Enforces the same aggregation guard
 * the real Lambda does: > EXPORT_MAX_ROWS (default 5000, mocked lower here
 * so the demo can trigger it) without an approval_token throws 428.
 */
import type { ExportApprovalRequiredBody, ExportRequest, ExportResponse, Role } from "@/lib/types";
import { visibleGrants } from "./grants";

export const MOCK_EXPORT_MAX_ROWS = 20;

export class ExportApprovalRequiredError extends Error {
  status = 428 as const;
  body: ExportApprovalRequiredBody;
  constructor(body: ExportApprovalRequiredBody) {
    super("approval_required");
    this.body = body;
  }
}

export function runExport(req: ExportRequest, role: Role | null, orgUnit: string | null): ExportResponse {
  const rowCount = visibleGrants(role, orgUnit).length;
  if (rowCount > MOCK_EXPORT_MAX_ROWS && !req.approval_token) {
    throw new ExportApprovalRequiredError({
      error: "approval_required",
      row_count: rowCount,
      max_rows: MOCK_EXPORT_MAX_ROWS,
    });
  }
  const export_id = `export-${Date.now()}`;
  return {
    export_id,
    row_count: rowCount,
    format: req.format,
    download_url: `data:application/octet-stream;base64,`, // demo stub — no real file in mock mode
    audited: true,
  };
}
