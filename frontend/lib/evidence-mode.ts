export const EVIDENCE_MODE_STORAGE_KEY = "compass.evidence-mode.v1";

export type EvidenceMode = "live" | "rehearsal";

export const DEFAULT_EVIDENCE_MODE: EvidenceMode = "live";

/**
 * Build-time presentation switch. When NEXT_PUBLIC_SINGLE_MODE=true the app
 * presents a single live evidence mode: rehearsal stays in the codebase for
 * flag-off practice builds, but it cannot be selected, routed to, persisted,
 * or read by the adapters. Inlined at build time (same pattern as
 * NEXT_PUBLIC_AUTH_DISABLED in lib/auth/use-app-auth.ts).
 */
export const SINGLE_LIVE_MODE =
  typeof process !== "undefined" && process.env.NEXT_PUBLIC_SINGLE_MODE === "true";

let runtimeEvidenceMode: EvidenceMode = DEFAULT_EVIDENCE_MODE;
let runtimeHydrated = false;

export function parseEvidenceMode(raw: string | null | undefined): EvidenceMode {
  if (SINGLE_LIVE_MODE) return "live";
  return raw === "rehearsal" ? "rehearsal" : DEFAULT_EVIDENCE_MODE;
}

export function evidenceModeForPath(pathname: string | null | undefined): EvidenceMode | null {
  if (SINGLE_LIVE_MODE) return null;
  const path = (pathname ?? "/").split("?")[0]?.split("#")[0] ?? "/";
  return path === "/rehearsal" || path.startsWith("/rehearsal/") ? "rehearsal" : null;
}

export function resolveInitialEvidenceMode(
  pathname: string | null | undefined,
  persisted: string | null | undefined,
): EvidenceMode {
  return evidenceModeForPath(pathname) ?? parseEvidenceMode(persisted);
}

export function readEvidenceMode(storage?: Pick<Storage, "getItem"> | null): EvidenceMode {
  if (!storage) return DEFAULT_EVIDENCE_MODE;
  try {
    return parseEvidenceMode(storage.getItem(EVIDENCE_MODE_STORAGE_KEY));
  } catch {
    return DEFAULT_EVIDENCE_MODE;
  }
}

export function persistEvidenceMode(
  mode: EvidenceMode,
  storage?: Pick<Storage, "setItem"> | null,
): void {
  if (!storage) return;
  try {
    storage.setItem(EVIDENCE_MODE_STORAGE_KEY, mode);
  } catch {
    // Runtime mode remains explicit even when browser persistence is unavailable.
  }
}

export function setRuntimeEvidenceMode(mode: EvidenceMode): void {
  runtimeEvidenceMode = SINGLE_LIVE_MODE ? "live" : mode;
  runtimeHydrated = true;
}

export function getRuntimeEvidenceMode(): EvidenceMode {
  if (!runtimeHydrated && typeof window !== "undefined") {
    setRuntimeEvidenceMode(readEvidenceMode(window.localStorage));
  }
  return runtimeEvidenceMode;
}

export function usesRehearsalEvidence(): boolean {
  if (SINGLE_LIVE_MODE) return false;
  return getRuntimeEvidenceMode() === "rehearsal";
}

export function evidenceModeHome(mode: EvidenceMode): string {
  return mode === "rehearsal" ? "/rehearsal/" : "/admin/acquisition/";
}

export function evidenceModeLabel(mode: EvidenceMode): string {
  return mode === "rehearsal" ? "Rehearsal" : "Live public evidence";
}

export function evidenceModeDisclosure(mode: EvidenceMode): string {
  return mode === "rehearsal"
    ? "Synthetic fixtures are active because rehearsal was explicitly selected. Nothing is presented as live evidence."
    : "Protected public evidence is active. A failed or unavailable live request remains unavailable and never loads a synthetic substitute.";
}
