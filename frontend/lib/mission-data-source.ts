import type { EvidenceMode } from "@/lib/evidence-mode";

export function curatedEvidenceSourceLabel(mode: EvidenceMode): string {
  return mode === "rehearsal"
    ? "Explicit fixture-backed rehearsal projection"
    : "Protected live public serving projection";
}
