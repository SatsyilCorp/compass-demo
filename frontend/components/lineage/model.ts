import type {
  OperationsLineageStage,
  OperationsRunStatus,
} from "@/lib/types";

export const TERMINAL_RUN_STATUSES = new Set<OperationsRunStatus>([
  "completed",
  "quarantined",
  "failed",
  "expired",
  "cancelled",
]);

export function orderedStages(stages: OperationsLineageStage[]): OperationsLineageStage[] {
  return [...stages].sort((left, right) => left.sequence - right.sequence || left.stage_id.localeCompare(right.stage_id));
}

export function lineageProgress(stages: OperationsLineageStage[]): {
  complete: number;
  active: number;
  pending: number;
  total: number;
  percentage: number;
} {
  const complete = stages.filter((stage) => ["completed", "quarantined", "failed", "skipped"].includes(stage.status)).length;
  const active = stages.filter((stage) => stage.status === "running").length;
  const pending = stages.filter((stage) => stage.status === "pending").length;
  return {
    complete,
    active,
    pending,
    total: stages.length,
    percentage: stages.length === 0 ? 0 : Math.round((complete / stages.length) * 100),
  };
}

export function shortDigest(value: string | null | undefined, visible = 12): string {
  if (!value) return "Not recorded";
  if (value.length <= visible * 2 + 1) return value;
  return `${value.slice(0, visible)}...${value.slice(-visible)}`;
}

export function isAttentionStatus(status: OperationsRunStatus): boolean {
  return status === "failed" || status === "quarantined" || status === "expired";
}
