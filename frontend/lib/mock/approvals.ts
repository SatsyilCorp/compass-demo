/**
 * Persistent approval workflow for replay mode. Records keep stable IDs,
 * require a separate persona for decisions, and bind export approvals to the
 * fingerprint of the blocked request that created them.
 */
import type {
  ApprovalRequest,
  ApprovalResponse,
  ApprovalsListResponse,
  Role,
} from "@/lib/types";
import { replayActor } from "./actors";
import { effectiveRehearsalRole } from "./rehearsal-persona";
import {
  opaqueApprovalToken,
  replayCapabilityHash,
  replayCapabilitySecret,
} from "./approval-token";
import { createOrUpdateScenarioApproval, getScenarioState } from "./scenario-store";

export async function createOrAdvanceApproval(
  req: ApprovalRequest,
  role: Role,
): Promise<ApprovalResponse> {
  role = effectiveRehearsalRole(role);
  const actor = replayActor(role);
  let capabilitySecret: string | null = null;
  let capabilityHash: string | undefined;
  if (req.action === "approve") {
    const pending = getScenarioState().approvals.find(
      (approval) =>
        approval.subject_type === req.subject_type &&
        approval.subject_id === req.subject_id &&
        approval.state === "pending",
    );
    if (!pending) throw new Error("approval_not_found");
    capabilitySecret = await replayCapabilitySecret(pending.id, pending.subject_id);
    capabilityHash = await replayCapabilityHash(capabilitySecret);
  }
  const approval = createOrUpdateScenarioApproval(
    req.subject_type,
    req.subject_id,
    req.action,
    actor,
    req.note,
    capabilityHash,
  );
  const active =
    approval.state === "approved" &&
    !approval.consumed_at &&
    new Date(approval.expires_at).getTime() >
      new Date(getScenarioState().logical_now).getTime();
  return {
    approval,
    ...(active && capabilitySecret
      ? { approval_token: opaqueApprovalToken(approval.id, capabilitySecret) }
      : {}),
    four_eyes: {
      enforced: true,
      requester: approval.requested_by,
      decider: approval.decided_by,
      same_actor_blocked: true,
    },
  };
}

export function listPendingApprovals(role: Role): ApprovalsListResponse {
  role = effectiveRehearsalRole(role);
  const state = getScenarioState();
  const actor = replayActor(role);
  const now = new Date(state.logical_now).getTime();
  const approvals = state.approvals
    .filter(
      (approval) =>
        approval.state === "pending" &&
        (!approval.expires_at || new Date(approval.expires_at).getTime() > now) &&
        (role === "poweruser" || approval.requested_by === actor),
    )
    .sort((left, right) => left.created_at.localeCompare(right.created_at));
  return {
    approvals,
    actor,
    scope: role === "poweruser" ? "all_pending" : "requested_by_actor",
    can_decide: role === "poweruser",
    four_eyes_enforced: true,
    tokens_included: false,
    generated_at: state.logical_now,
  };
}
