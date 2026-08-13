import type {
  OperationsSignalAcknowledgeResponse,
  OperationsSignalsResponse,
} from "@/lib/types";

export function unreadSignalCount(response: OperationsSignalsResponse): number {
  return response.signals.filter((signal) => signal.status === "open").length;
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
  return { ...response, signals, unread_count: signals.filter((signal) => signal.status === "open").length };
}
