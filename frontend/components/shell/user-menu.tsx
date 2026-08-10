"use client";

import { LogOut, Users } from "lucide-react";
import { useAppAuth, AUTH_DISABLED, ROLES, ROLE_LABELS, type AppRole } from "@/lib/auth/use-app-auth";
import { setDemoPersona } from "@/lib/auth/demo-persona";

/**
 * Account control in the top-right of the app header.
 *
 * No-login demo mode (`NEXT_PUBLIC_AUTH_DISABLED=true`): a plain persona
 * `<select>` so one browser tab can switch between the two demo personas
 * from docs/CONTRACTS.md ("poweruser" / ONR-Corporate, "viewer" / Code-30)
 * without a real Cognito sign-in — no popover/menu library needed.
 *
 * Real auth: the signed-in user's role + a sign-out button.
 */
export function UserMenu() {
  const auth = useAppAuth();

  if (AUTH_DISABLED) {
    return (
      <label className="flex items-center gap-2 rounded-full border border-border bg-surface py-1 pl-3 pr-1.5 text-sm">
        <Users className="size-3.5 text-text-subtle" aria-hidden />
        <span className="sr-only">Switch demo persona</span>
        <select
          value={auth.role ?? "poweruser"}
          onChange={(e) => setDemoPersona(e.target.value as AppRole)}
          className="cursor-pointer border-none bg-transparent py-1 pr-1 text-[13px] font-medium text-text-strong outline-none"
        >
          {ROLES.map((r) => (
            <option key={r} value={r}>
              {ROLE_LABELS[r]}
            </option>
          ))}
        </select>
      </label>
    );
  }

  return (
    <div className="flex items-center gap-3">
      {auth.displayName && (
        <span className="hidden text-sm font-medium text-text-strong sm:inline">{auth.displayName}</span>
      )}
      <button
        type="button"
        onClick={() => auth.signoutRedirect()}
        className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-1.5 text-[13px] font-medium text-text-muted transition-colors hover:border-border-strong hover:text-text-strong"
      >
        <LogOut className="size-3.5" aria-hidden />
        Sign out
      </button>
    </div>
  );
}
