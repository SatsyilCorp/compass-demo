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
  attention: OperationsSignal[];
  activity: SignalActivityGroup[];
  actionableUnread: number;
  activityTotal: number;
};

export function signalNeedsAttention(signal: OperationsSignal): boolean {
  if (signal.status !== "open") return false;
  if (signal.severity === "critical" || signal.severity === "warning") return true;
  return signal.deliveries.some((delivery) => delivery.state === "failed");
}

export function buildSignalInbox(response: OperationsSignalsResponse): SignalInbox {
  const ordered = [...response.signals].sort((left, right) => (
    timestamp(right.occurred_at) - timestamp(left.occurred_at)
  ));
  const attention = ordered.filter(signalNeedsAttention);
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
    activityTotal: ordered.length - attention.length,
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
    signal.signal_type,
    signal.severity,
    signal.status,
    signal.title,
    signal.message,
    delivery,
  ].join("::");
}

function timestamp(value: string): number {
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? 0 : parsed;
}
