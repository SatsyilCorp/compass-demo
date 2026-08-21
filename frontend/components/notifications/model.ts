import type {
  OperationsSignal,
  OperationsSignalAcknowledgeResponse,
  OperationsSignalsResponse,
} from "@/lib/types";

export type SignalActivityGroup = {
  signal: OperationsSignal;
  occurrenceCount: number;
  firstOccurredAt: string;
  lastOccurredAt: string;
};

export type SignalInbox = {
  attention: SignalActivityGroup[];
  activity: SignalActivityGroup[];
  actionableUnread: number;
  actionableEventTotal: number;
  activityTotal: number;
};

export type SignalGuidance = {
  whyItMatters: string;
  recommendedAction: string;
};

export function signalGuidance(signal: OperationsSignal): SignalGuidance {
  const kind = `${signal.signal_type} ${signal.run_kind ?? ""} ${signal.title}`.toLowerCase();
  if (kind.includes("model") && kind.includes("drift")) {
    return {
      whyItMatters: "Recent documents look different from the model's training baseline, so new classifications may become less reliable.",
      recommendedAction: "Review the drift evidence, sample recent classifications, and approve retraining only if the change is confirmed.",
    };
  }
  if (kind.includes("quarant") || kind.includes("quality")) {
    return {
      whyItMatters: "The affected data did not reach the trusted portfolio, so the current dashboard remains protected from the failed records.",
      recommendedAction: "Open the evidence, review the failed checks, correct the source, and submit it again.",
    };
  }
  if (kind.includes("public") || kind.includes("acquisition")) {
    return {
      whyItMatters: "A public-source change can alter portfolio totals or relationships and should be confirmed before it informs a decision.",
      recommendedAction: "Compare the new public snapshot with the prior version and confirm the changed records.",
    };
  }
  if (signal.deliveries.some((delivery) => delivery.state === "failed")) {
    return {
      whyItMatters: "The system retained the event, but one notification channel did not deliver it to its intended destination.",
      recommendedAction: "Review the delivery evidence, repair the channel configuration, and retry the notification.",
    };
  }
  if (signal.severity === "critical") {
    return {
      whyItMatters: "A critical workflow condition could affect the freshness or reliability of decision information.",
      recommendedAction: "Open the evidence now, confirm the affected run, and assign an owner before acknowledging the alert.",
    };
  }
  return {
    whyItMatters: "This condition may require a person to confirm the data or workflow result before it is relied upon.",
    recommendedAction: "Open the evidence, verify what happened, and mark the alert reviewed when the next step is owned.",
  };
}

export function signalNeedsAttention(signal: OperationsSignal): boolean {
  if (signal.status !== "open") return false;
  if (signal.severity === "critical" || signal.severity === "warning") return true;
  return signal.deliveries.some((delivery) => delivery.state === "failed");
}

export function buildSignalInbox(response: OperationsSignalsResponse): SignalInbox {
  const ordered = [...response.signals].sort((left, right) => (
    timestamp(right.occurred_at) - timestamp(left.occurred_at)
  ));
  const attentionEvents = ordered.filter(signalNeedsAttention);
  const attention = groupSignals(attentionEvents, attentionKey);
  const grouped = new Map<string, SignalActivityGroup>();

  for (const signal of ordered) {
    if (signalNeedsAttention(signal)) continue;
    const key = activityKey(signal);
    const existing = grouped.get(key);
    if (existing) {
      existing.occurrenceCount += 1;
      existing.firstOccurredAt = signal.occurred_at;
      continue;
    }
    grouped.set(key, {
      signal,
      occurrenceCount: 1,
      firstOccurredAt: signal.occurred_at,
      lastOccurredAt: signal.occurred_at,
    });
  }

  return {
    attention,
    activity: [...grouped.values()],
    actionableUnread: attention.length,
    actionableEventTotal: attentionEvents.length,
    activityTotal: ordered.length - attentionEvents.length,
  };
}

export function unreadSignalCount(response: OperationsSignalsResponse): number {
  return buildSignalInbox(response).actionableUnread;
}

export function applySignalAcknowledgement(
  response: OperationsSignalsResponse,
  receipt: OperationsSignalAcknowledgeResponse,
): OperationsSignalsResponse {
  const signals = response.signals.map((signal) => signal.event_id === receipt.event_id ? {
    ...signal,
    status: receipt.status,
    acknowledged_at: receipt.acknowledged_at,
    acknowledged_by: receipt.acknowledged_by,
    updated_at: receipt.acknowledged_at,
  } : signal);
  const next = { ...response, signals };
  return { ...next, unread_count: unreadSignalCount(next) };
}

function activityKey(signal: OperationsSignal): string {
  const delivery = signal.deliveries
    .map((item) => `${item.channel}:${item.state}`)
    .sort()
    .join("|");
  return [
    signal.evidence_class,
    signal.signal_type,
    signal.severity,
    signal.status,
    signal.title,
    signal.message,
    delivery,
  ].join("::");
}

function attentionKey(signal: OperationsSignal): string {
  const delivery = signal.deliveries
    .map((item) => `${item.channel}:${item.state}`)
    .sort()
    .join("|");
  return [
    signal.evidence_class,
    signal.signal_type,
    signal.severity,
    signal.title,
    signal.source,
    signal.run_kind ?? "",
    delivery,
  ].join("::");
}

function groupSignals(
  signals: OperationsSignal[],
  keyFor: (signal: OperationsSignal) => string,
): SignalActivityGroup[] {
  const grouped = new Map<string, SignalActivityGroup>();
  for (const signal of signals) {
    const key = keyFor(signal);
    const existing = grouped.get(key);
    if (existing) {
      existing.occurrenceCount += 1;
      existing.firstOccurredAt = signal.occurred_at;
      continue;
    }
    grouped.set(key, {
      signal,
      occurrenceCount: 1,
      firstOccurredAt: signal.occurred_at,
      lastOccurredAt: signal.occurred_at,
    });
  }
  return [...grouped.values()];
}

function timestamp(value: string): number {
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}
