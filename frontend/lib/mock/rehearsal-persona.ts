/**
 * Optional acting-persona override for replay mode. On a deployment with real
 * Cognito sign-in, the rehearsal actor normally follows the signed-in role, so
 * a single presenter cannot satisfy four-eyes without switching accounts.
 * This override lets rehearsal - and only rehearsal - act as the other
 * synthetic persona. It persists per browser beside the scenario and is
 * cleared by a replay reset. Live evidence paths never read it.
 */
import type { Role } from "@/lib/types";
import { ORG_UNIT_FOR_ROLE } from "../auth/identity-contract";

export const REHEARSAL_PERSONA_KEY = "compass:rehearsal-persona:v1";

const VALID_ROLES: readonly Role[] = ["viewer", "poweruser"];

export function getRehearsalPersonaOverride(): Role | null {
  if (typeof window === "undefined") return null;
  try {
    const stored = window.localStorage.getItem(REHEARSAL_PERSONA_KEY);
    return VALID_ROLES.includes(stored as Role) ? (stored as Role) : null;
  } catch {
    return null;
  }
}

export function setRehearsalPersonaOverride(role: Role | null): void {
  if (typeof window === "undefined") return;
  try {
    if (role === null) window.localStorage.removeItem(REHEARSAL_PERSONA_KEY);
    else window.localStorage.setItem(REHEARSAL_PERSONA_KEY, role);
  } catch {
    // Storage may be unavailable in private browsing - the switch is a no-op.
  }
}

export function clearRehearsalPersonaOverride(): void {
  setRehearsalPersonaOverride(null);
}

/** Effective role for rehearsal adapters: explicit override wins. */
export function effectiveRehearsalRole(role: Role | null | undefined): Role {
  return getRehearsalPersonaOverride() ?? role ?? "viewer";
}

/**
 * Effective identity pair for rehearsal adapters. When an override is active,
 * the org unit follows the overridden role so row scope stays coherent.
 */
export function effectiveRehearsalIdentity(
  role: Role | null | undefined,
  orgUnit: string | null | undefined,
): { role: Role; orgUnit: string } {
  const override = getRehearsalPersonaOverride();
  if (override) return { role: override, orgUnit: ORG_UNIT_FOR_ROLE[override] };
  const effRole = role ?? "viewer";
  return { role: effRole, orgUnit: orgUnit ?? ORG_UNIT_FOR_ROLE[effRole] };
}

/** Subscribe to override changes (storage event across tabs, custom event in-tab). */
export function subscribeRehearsalPersona(listener: () => void): () => void {
  if (typeof window === "undefined") return () => {};
  const onStorage = (event: StorageEvent) => {
    if (event.key === REHEARSAL_PERSONA_KEY) listener();
  };
  window.addEventListener("storage", onStorage);
  window.addEventListener("compass:rehearsal-persona", listener);
  return () => {
    window.removeEventListener("storage", onStorage);
    window.removeEventListener("compass:rehearsal-persona", listener);
  };
}
