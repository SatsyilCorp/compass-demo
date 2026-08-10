"use client";

import { useContext } from "react";
import { AuthContext } from "react-oidc-context";
import { useDemoPersona } from "./demo-persona";

export const AUTH_DISABLED =
  typeof process !== "undefined" &&
  process.env.NEXT_PUBLIC_AUTH_DISABLED === "true";

const COGNITO_DOMAIN = process.env.NEXT_PUBLIC_COGNITO_DOMAIN ?? "";
const COGNITO_CLIENT_ID = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID ?? "";
const POST_LOGOUT_URI =
  process.env.NEXT_PUBLIC_COGNITO_POST_LOGOUT_REDIRECT_URI ??
  "http://localhost:3000/login/";

/**
 * Compass's two demo personas (docs/CONTRACTS.md "RLS"), each a Cognito
 * group mapped 1:1 by the HttpApi JWT authorizer:
 *
 *   poweruser  org_unit ONR-Corporate — the RLS "sees all" branch.
 *   viewer     org_unit Code-30       — sees only its own org_unit's rows.
 *
 * The authorizer injects `org_unit` as a claim; ORG_UNIT_FOR_ROLE below is
 * the frontend's copy of that same mapping, used only for the mock-mode
 * client-side RLS simulation in lib/mock/* (so the demo tells the same
 * security story with or without a deployed backend).
 */
export type AppRole = "poweruser" | "viewer";

export const ROLES: readonly AppRole[] = ["poweruser", "viewer"];

export const ORG_UNIT_FOR_ROLE: Record<AppRole, string> = {
  poweruser: "ONR-Corporate",
  viewer: "Code-30",
};

const ROLE_LABEL: Record<AppRole, string> = {
  poweruser: "Power User (ONR-Corporate)",
  viewer: "Viewer (Code-30)",
};

export type AppAuth = {
  isAuthenticated: boolean;
  isLoading: boolean;
  user: { profile?: { email?: string; name?: string; picture?: string } } | null;
  /** Bearer token to attach to API calls (the ID token, per the JWT authorizer). */
  idToken: string | null;
  /** Raw `cognito:groups` claim (or `[]` if not signed in / no group). */
  groups: string[];
  /** Derived role, or null if the signed-in user carries no recognized group. */
  role: AppRole | null;
  /** `org_unit` this role resolves to (mirrors the authorizer's claim injection). */
  orgUnit: string | null;
  /** Human label for the role/persona chrome. */
  displayName: string | null;
  signinRedirect: () => void | Promise<void>;
  signoutRedirect: () => void | Promise<void>;
};

function buildStub(role: AppRole): AppAuth {
  return {
    isAuthenticated: true,
    isLoading: false,
    user: { profile: { email: "demo@compass.local", name: "Demo User" } },
    idToken: null,
    groups: [role],
    role,
    orgUnit: ORG_UNIT_FOR_ROLE[role],
    displayName: ROLE_LABEL[role],
    signinRedirect: () => {},
    signoutRedirect: () => {},
  };
}

// Cognito's /logout is non-RFC: it ignores `id_token_hint` and instead wants
// `client_id` + `logout_uri` query params. Build the URL ourselves.
function cognitoSignout() {
  if (typeof window === "undefined") return;
  if (!COGNITO_DOMAIN || !COGNITO_CLIENT_ID) {
    window.location.href = POST_LOGOUT_URI;
    return;
  }
  try {
    for (const key of Object.keys(window.sessionStorage)) {
      if (key.startsWith("oidc.")) window.sessionStorage.removeItem(key);
    }
  } catch {
    // sessionStorage may be unavailable in private browsing — ignore.
  }
  const params = new URLSearchParams({
    client_id: COGNITO_CLIENT_ID,
    logout_uri: POST_LOGOUT_URI,
  });
  window.location.href = `${COGNITO_DOMAIN}/logout?${params.toString()}`;
}

/** Precedence when a token somehow carries both groups — poweruser wins. */
const ROLE_PRECEDENCE: AppRole[] = ["poweruser", "viewer"];

function deriveRole(groups: string[]): AppRole | null {
  for (const r of ROLE_PRECEDENCE) {
    if (groups.includes(r)) return r;
  }
  return null;
}

export function useAppAuth(): AppAuth {
  const ctx = useContext(AuthContext);
  // Read unconditionally (rules of hooks); only consulted in no-login demo mode.
  const demoRole = useDemoPersona();
  if (AUTH_DISABLED || !ctx) return buildStub(demoRole);

  const profile = ctx.user?.profile as Record<string, unknown> | undefined;
  const rawGroups = profile?.["cognito:groups"];
  const groups = Array.isArray(rawGroups)
    ? rawGroups.filter((g): g is string => typeof g === "string")
    : typeof rawGroups === "string"
      ? [rawGroups]
      : [];
  const role = deriveRole(groups);

  return {
    isAuthenticated: !!ctx.isAuthenticated,
    isLoading: !!ctx.isLoading,
    user: ctx.user
      ? {
          profile: {
            email: ctx.user.profile?.email,
            name: ctx.user.profile?.name,
            picture: ctx.user.profile?.picture as string | undefined,
          },
        }
      : null,
    idToken: ctx.user?.id_token ?? null,
    groups,
    role,
    orgUnit: role ? ORG_UNIT_FOR_ROLE[role] : null,
    displayName: role ? ROLE_LABEL[role] : null,
    signinRedirect: () => ctx.signinRedirect(),
    signoutRedirect: cognitoSignout,
  };
}

export const ROLE_LABELS = ROLE_LABEL;
