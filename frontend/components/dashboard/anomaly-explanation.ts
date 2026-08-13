import type { Anomaly } from "../../lib/types";

export type AnomalyExplanation = {
  title: string;
  whatHappened: string;
  whyItMatters: string;
  recommendedAction: string;
};

export function friendlyAnomalyKind(kind: string): string {
  const normalized = kind.trim().toLowerCase().replaceAll("-", "_");
  if (normalized.includes("funding") || normalized.includes("zscore") || normalized.includes("amount")) {
    return "Unusual funding amount";
  }
  if (normalized.includes("quality") || normalized.includes("schema") || normalized.includes("quarantine")) {
    return "Data quality issue";
  }
  if (normalized.includes("duplicate")) return "Possible duplicate record";
  if (normalized.includes("missing_abstract") || normalized.includes("missing_summary")) return "Missing document summary";
  if (normalized.includes("org_unit") || normalized.includes("organization")) return "Organization does not match";
  if (normalized.includes("fiscal_year") || normalized.includes("appropriation")) return "Fiscal year needs confirmation";
  if (normalized.includes("milestone") || normalized.includes("schedule")) {
    return "Schedule needs review";
  }
  if (normalized.includes("license")) return "License needs attention";
  return "Unusual portfolio record";
}

export function explainAnomaly(anomaly: Anomaly): AnomalyExplanation {
  const kind = anomaly.kind.trim().toLowerCase().replaceAll("-", "_");
  const identifier = anomaly.grant_no ?? (anomaly.grant_id ? `grant ${anomaly.grant_id}` : "this intake");

  if (kind.includes("funding") || kind.includes("zscore") || kind.includes("amount")) {
    const peerGroup = anomaly.program_area ? ` other ${anomaly.program_area} awards` : " similar awards";
    return {
      title: "Unusual funding amount",
      whatHappened: `${identifier} has a funding amount that is far from${peerGroup}.`,
      whyItMatters: "The amount may be completely valid, but it could also reflect a source-data error or an exceptional investment that deserves confirmation.",
      recommendedAction: "Compare the amount with the award document and program context, then record whether it is valid or needs correction.",
    };
  }

  if (kind.includes("quality") || kind.includes("schema") || kind.includes("quarantine")) {
    return {
      title: "Data quality issue",
      whatHappened: `${identifier} did not pass one or more required data checks.`,
      whyItMatters: "The affected data was not published into the trusted portfolio, so it cannot influence a decision until it is reviewed.",
      recommendedAction: "Review the failed checks, correct the source record, and submit it again.",
    };
  }

  if (kind.includes("duplicate")) {
    return {
      title: "Possible duplicate record",
      whatHappened: `${identifier} resembles another record in the same intake.`,
      whyItMatters: "Counting the same award twice could overstate activity or funding, but similar records can also be legitimate amendments.",
      recommendedAction: "Compare both records with their source documents, then merge, correct, or confirm them as separate awards.",
    };
  }

  if (kind.includes("missing_abstract") || kind.includes("missing_summary")) {
    return {
      title: "Missing document summary",
      whatHappened: `${identifier} does not include enough descriptive text for reliable analysis.`,
      whyItMatters: "Topic classification and search results may be incomplete until the missing context is restored.",
      recommendedAction: "Open the source document, add the missing abstract or summary, and run the quality checks again.",
    };
  }

  if (kind.includes("org_unit") || kind.includes("organization")) {
    return {
      title: "Organization does not match",
      whatHappened: `${identifier} names an organization that differs from its submitting-office evidence.`,
      whyItMatters: "An incorrect owner can route the record to the wrong portfolio view or reviewer.",
      recommendedAction: "Confirm the owning organization against the source record, correct it if needed, and record the decision.",
    };
  }

  if (kind.includes("fiscal_year") || kind.includes("appropriation")) {
    return {
      title: "Fiscal year needs confirmation",
      whatHappened: `${identifier} has a fiscal year that differs from the expected award or appropriation period.`,
      whyItMatters: "The difference can change year-over-year funding views, although a valid correction or carryover may explain it.",
      recommendedAction: "Confirm the fiscal year against the award evidence, then correct or approve the record.",
    };
  }

  if (kind.includes("milestone") || kind.includes("schedule")) {
    return {
      title: "Schedule needs review",
      whatHappened: `${identifier} has a milestone or schedule pattern that differs from its plan.`,
      whyItMatters: "A schedule exception can affect delivery timing, but it does not by itself mean the project will fail.",
      recommendedAction: "Confirm the current milestone status with the program owner and document the recovery plan if one is needed.",
    };
  }

  return {
    title: friendlyAnomalyKind(anomaly.kind),
    whatHappened: `${identifier} looks different from comparable records in the visible portfolio.`,
    whyItMatters: "This is a review prompt, not a conclusion. A person should verify the source evidence before acting on it.",
    recommendedAction: "Open the supporting evidence, confirm the source values, and record the review decision.",
  };
}
