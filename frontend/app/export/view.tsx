"use client";

import { useEvidenceMode } from "@/lib/evidence-mode-context";

export function EvidenceModeExport({ live, rehearsal }: { live: React.ReactNode; rehearsal: React.ReactNode }) {
  const { mode } = useEvidenceMode();
  return mode === "rehearsal" ? rehearsal : live;
}
