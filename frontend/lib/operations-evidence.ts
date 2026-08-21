import type { OperationsEvidenceClass } from "./types";

export type EvidenceClassPresentation = {
  label: string;
  tone: "public" | "prediction" | "synthetic" | "control" | "mixed" | "unknown";
};

export function normalizeOperationsEvidenceClass(
  value: unknown,
  detailValue?: unknown,
): OperationsEvidenceClass {
  const candidate = normalizedValue(value) ?? normalizedValue(detailValue);
  return candidate ?? "unclassified";
}

export function isLivePublicOperationsEvidenceClass(value: unknown): boolean {
  const normalized = normalizeOperationsEvidenceClass(value);
  return normalized === "operational-control"
    || normalized === "public"
    || normalized.startsWith("public-");
}

export function evidenceClassPresentation(
  evidenceClass: OperationsEvidenceClass,
): EvidenceClassPresentation {
  const normalized = normalizeOperationsEvidenceClass(evidenceClass);
  if (normalized.includes("synthetic") || normalized.includes("replay")) {
    return { label: "Synthetic demo evidence", tone: "synthetic" };
  }
  if (normalized === "public-predicted" || normalized === "predicted") {
    return { label: "Predicted public evidence", tone: "prediction" };
  }
  if (normalized === "public-observed" || normalized === "observed") {
    return { label: "Observed public evidence", tone: "public" };
  }
  if (normalized === "public" || normalized === "public-evidence") {
    return { label: "Public evidence", tone: "public" };
  }
  if (normalized === "public-derived" || normalized === "sanitized-application-projection") {
    return { label: "Derived public evidence", tone: "prediction" };
  }
  if (normalized === "operational-control") {
    return { label: "Operational control", tone: "control" };
  }
  if (normalized === "mixed-evidence") {
    return { label: "Mixed evidence", tone: "mixed" };
  }
  if (normalized === "unclassified") {
    return { label: "Unclassified evidence", tone: "unknown" };
  }
  return {
    label: `${humanize(normalized)} evidence`,
    tone: "unknown",
  };
}

function normalizedValue(value: unknown): OperationsEvidenceClass | null {
  if (typeof value !== "string") return null;
  const normalized = value.trim().toLowerCase().replaceAll("_", "-").replaceAll(" ", "-");
  return /^[a-z0-9][a-z0-9.-]{0,79}$/.test(normalized)
    ? normalized as OperationsEvidenceClass
    : null;
}

function humanize(value: string): string {
  return value.replaceAll("-", " ");
}
