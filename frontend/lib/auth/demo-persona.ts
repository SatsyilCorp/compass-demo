"use client";

/**
 * Demo persona override (no-login mode only).
 *
 * When `NEXT_PUBLIC_AUTH_DISABLED=true` there is no real Cognito session, so
 * there is no `cognito:groups` claim to derive a role from. To let one
 * browser tab demo both personas - poweruser (ONR-Corporate, sees every
 * org_unit) and viewer (Code-30, sees only its own rows) - we keep the
 * selected persona in `sessionStorage` (per-tab) and expose it through
 * `useSyncExternalStore` so the sidebar, AuthGuard, and persona switcher all
 * re-render instantly on change (no reload, hydration-safe).
 *
 * Outside demo mode this module is inert - `useAppAuth` ignores the override
 * and derives the role from the real ID token's `cognito:groups` claim.
 */
import { useSyncExternalStore } from "react";
import type { AppRole } from "./identity-contract";

const KEY = "compass:demo-persona";
const DEFAULT_PERSONA: AppRole = "poweruser";
const VALID: readonly AppRole[] = ["poweruser", "viewer"];

const listeners = new Set<() => void>();

export function getDemoPersona(): AppRole {
  if (typeof window === "undefined") return DEFAULT_PERSONA;
  try {
    const v = window.sessionStorage.getItem(KEY);
    if (v && (VALID as readonly string[]).includes(v)) return v as AppRole;
  } catch {
    // sessionStorage may be unavailable (private mode) - fall through to default.
  }
  return DEFAULT_PERSONA;
}

export function setDemoPersona(role: AppRole): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(KEY, role);
  } catch {
    // ignore - still notify so in-memory subscribers in this tab update.
  }
  listeners.forEach((l) => l());
}

function subscribe(cb: () => void): () => void {
  listeners.add(cb);
  const onStorage = (e: StorageEvent) => {
    if (e.key === KEY) cb();
  };
  if (typeof window !== "undefined") window.addEventListener("storage", onStorage);
  return () => {
    listeners.delete(cb);
    if (typeof window !== "undefined") window.removeEventListener("storage", onStorage);
  };
}

/** Reactive current demo persona. Always returns the default during SSR/prerender. */
export function useDemoPersona(): AppRole {
  return useSyncExternalStore(subscribe, getDemoPersona, () => DEFAULT_PERSONA);
}
