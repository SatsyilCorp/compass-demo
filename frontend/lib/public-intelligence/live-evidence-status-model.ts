export type LiveEvidenceStatusState = "attention" | "verifying" | "running" | "stopped";

export function liveEvidenceStatusState(
  control: { enabled: boolean } | null,
  error: string | null,
): LiveEvidenceStatusState {
  if (error) return "attention";
  if (!control) return "verifying";
  return control.enabled ? "running" : "stopped";
}
