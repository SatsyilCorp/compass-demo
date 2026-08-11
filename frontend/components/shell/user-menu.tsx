"use client";

import { LogOut, Users } from "lucide-react";
import { useAppAuth, AUTH_DISABLED, ROLES, type AppRole } from "@/lib/auth/use-app-auth";
import { setDemoPersona } from "@/lib/auth/demo-persona";

const COMPACT_ROLE_LABEL: Record<AppRole, string> = {
  poweruser: "Power user",
  viewer: "Viewer",
};

export function UserMenu() {
  const auth = useAppAuth();

  if (AUTH_DISABLED) {
    return (
      <label className="flex min-h-11 max-w-40 items-center gap-1.5 rounded-full border border-border bg-white pl-3 pr-2 text-sm shadow-soft sm:max-w-none sm:gap-2">
        <Users className="hidden size-4 shrink-0 text-text-subtle sm:block" aria-hidden />
        <span className="sr-only">Switch demo persona</span>
        <select
          value={auth.role ?? "poweruser"}
          onChange={(event) => setDemoPersona(event.target.value as AppRole)}
          aria-label="Active demo persona"
          className="min-w-0 cursor-pointer border-none bg-transparent py-2 text-xs font-bold text-text-strong outline-none sm:text-[13px]"
        >
          {ROLES.map((role) => (
            <option key={role} value={role}>
              {COMPACT_ROLE_LABEL[role]}
            </option>
          ))}
        </select>
      </label>
    );
  }

  return (
    <div className="flex items-center gap-2 sm:gap-3">
      {auth.displayName && (
        <span className="hidden max-w-48 truncate text-sm font-semibold text-text-strong md:inline">
          {auth.displayName}
        </span>
      )}
      <button
        type="button"
        onClick={() => auth.signoutRedirect()}
        className="inline-flex min-h-11 items-center gap-2 rounded-md border border-border px-3 text-[13px] font-semibold text-text-muted transition-colors hover:border-border-strong hover:bg-surface-2 hover:text-text-strong"
      >
        <LogOut className="size-4" aria-hidden />
        <span className="hidden sm:inline">Sign out</span>
        <span className="sr-only sm:hidden">Sign out</span>
      </button>
    </div>
  );
}
