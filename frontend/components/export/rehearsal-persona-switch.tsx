"use client";

/**
 * Rehearsal-only acting-persona switch. On deployments with real sign-in the
 * rehearsal actor follows the Cognito role, which would leave four-eyes
 * undecidable for a single presenter. Switching here changes only the
 * synthetic replay actor; it never touches the signed-in identity or any
 * live-evidence path.
 */
import { useSyncExternalStore } from "react";
import { UserRoundCog } from "lucide-react";

import type { Role } from "@/lib/types";
import { REPLAY_ACTORS } from "@/lib/mock/actors";
import {
  REHEARSAL_PERSONA_KEY,
  effectiveRehearsalRole,
  setRehearsalPersonaOverride,
} from "@/lib/mock/rehearsal-persona";

function subscribe(listener: () => void): () => void {
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

export function RehearsalPersonaSwitch({
  signedInRole,
  onSwitched,
}: {
  signedInRole: Role | null;
  onSwitched: () => void;
}) {
  const active = useSyncExternalStore(
    subscribe,
    () => effectiveRehearsalRole(signedInRole),
    () => signedInRole ?? "viewer",
  );

  function actAs(role: Role) {
    setRehearsalPersonaOverride(role === (signedInRole ?? "viewer") ? null : role);
    window.dispatchEvent(new Event("compass:rehearsal-persona"));
    onSwitched();
  }

  return (
    <div className="mt-2 inline-flex flex-wrap items-center gap-1.5 rounded-md border border-border bg-surface-2 p-1">
      <span className="inline-flex items-center gap-1 px-1.5 text-[10px] font-semibold uppercase tracking-wide text-text-muted">
        <UserRoundCog className="size-3.5" aria-hidden />
        Act as
      </span>
      {(Object.keys(REPLAY_ACTORS) as Role[]).map((role) => (
        <button
          key={role}
          type="button"
          onClick={() => actAs(role)}
          aria-pressed={active === role}
          className={
            active === role
              ? "rounded bg-gov-primary px-2 py-1 text-[10.5px] font-semibold text-white"
              : "rounded px-2 py-1 text-[10.5px] font-medium text-text-muted transition-colors hover:bg-surface hover:text-text-strong"
          }
        >
          {REPLAY_ACTORS[role]}
        </button>
      ))}
    </div>
  );
}
