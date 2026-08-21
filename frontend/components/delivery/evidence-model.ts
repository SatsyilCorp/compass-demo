export type DeliveryQualityStatus = "success" | "failure" | "pending" | "unverified";

export type DeliveryEvidence = {
  revision: string | null;
  revisionLabel: string;
  qualityStatus: DeliveryQualityStatus;
  qualityLabel: string;
  qualityRunUrl: string | null;
  isCommitBoundSuccess: boolean;
  caveat: string;
};

const EXACT_REVISION = /^[0-9a-f]{40}$/;
const EXACT_QUALITY_RUN_PATH = /^\/SatsyilCorp\/compass-demo\/actions\/runs\/\d+\/?$/;

export function deliveryEvidence(input: {
  sourceRevision?: string;
  qualityStatus?: string;
  qualityRunUrl?: string;
}): DeliveryEvidence {
  const revision = EXACT_REVISION.test(input.sourceRevision ?? "") ? input.sourceRevision! : null;
  const qualityRunUrl = revision ? exactQualityRunUrl(input.qualityRunUrl) : null;
  const qualityStatus = revision && qualityRunUrl
    ? normalizeQualityStatus(input.qualityStatus)
    : "unverified";
  const isCommitBoundSuccess = qualityStatus === "success";

  return {
    revision,
    revisionLabel: revision ? revision.slice(0, 12) : "Not recorded",
    qualityStatus,
    qualityLabel: qualityStatusLabel(qualityStatus),
    qualityRunUrl,
    isCommitBoundSuccess,
    caveat: isCommitBoundSuccess
      ? "The frontend build is bound to this exact deployed revision and successful quality workflow receipt."
      : "No successful exact-commit quality receipt is bound to this frontend build. Gate cards below describe source-controlled definitions, not completed execution.",
  };
}

function normalizeQualityStatus(status?: string): DeliveryQualityStatus {
  if (status === "success" || status === "failure" || status === "pending") return status;
  return "unverified";
}

function qualityStatusLabel(status: DeliveryQualityStatus): string {
  if (status === "success") return "Verified success";
  if (status === "failure") return "Failed";
  if (status === "pending") return "Running";
  return "Not verified";
}

function exactQualityRunUrl(value?: string): string | null {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    if (parsed.protocol !== "https:" || parsed.hostname !== "github.com") return null;
    if (parsed.search || parsed.hash || !EXACT_QUALITY_RUN_PATH.test(parsed.pathname)) return null;
    return parsed.toString().replace(/\/$/, "");
  } catch {
    return null;
  }
}
