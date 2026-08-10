/**
 * POST /approvals — fixture. Element 6/7 (approval workflow gating the
 * export aggregation guard). Mirrors `approvals` in
 * db/migrations/001_schema.sql.
 */
import type { Approval, ApprovalRequest, ApprovalResponse } from "@/lib/types";

let nextId = 100;

export function createOrAdvanceApproval(req: ApprovalRequest, actor: string): ApprovalResponse {
  const now = new Date().toISOString();
  const approval: Approval = {
    id: nextId++,
    subject_type: req.subject_type,
    subject_id: req.subject_id,
    state: req.action === "request" ? "pending" : req.action === "approve" ? "approved" : "rejected",
    requested_by: actor,
    decided_by: req.action === "request" ? null : actor,
    decided_at: req.action === "request" ? null : now,
    note: req.note ?? null,
    created_at: now,
  };
  return { approval };
}
