/** Shared frontend identity contract for live Cognito and replay personas. */
export type AppRole = "poweruser" | "viewer";

export const ROLES: readonly AppRole[] = ["poweruser", "viewer"];

export const COGNITO_GROUP_TO_ROLE: Readonly<Record<string, AppRole>> = {
  "compass-poweruser": "poweruser",
  "compass-viewer": "viewer",
};

export const COGNITO_GROUP_FOR_ROLE: Record<AppRole, string> = {
  poweruser: "compass-poweruser",
  viewer: "compass-viewer",
};

export const ORG_UNIT_FOR_ROLE: Record<AppRole, string> = {
  poweruser: "ONR-Corporate",
  viewer: "Code-30",
};

export const ROLE_LABELS: Record<AppRole, string> = {
  poweruser: "Power User (ONR-Corporate)",
  viewer: "Viewer (Code-30)",
};

const ROLE_PRECEDENCE: readonly AppRole[] = ["poweruser", "viewer"];

export function normalizeCognitoGroups(raw: unknown): string[] {
  if (Array.isArray(raw)) {
    return raw
      .filter((group): group is string => typeof group === "string")
      .map((group) => group.trim())
      .filter(Boolean);
  }
  if (typeof raw !== "string") return [];

  const value = raw.trim();
  if (!value) return [];
  if (value.startsWith("[") && value.endsWith("]")) {
    try {
      return normalizeCognitoGroups(JSON.parse(value) as unknown);
    } catch {
      return value
        .slice(1, -1)
        .split(/[ ,]+/)
        .map((group) => group.replace(/^['"]|['"]$/g, "").trim())
        .filter(Boolean);
    }
  }
  return value
    .split(",")
    .map((group) => group.trim())
    .filter(Boolean);
}

export function deriveRoleFromGroups(groups: readonly string[]): AppRole | null {
  const resolved = new Set(
    groups.map((group) => COGNITO_GROUP_TO_ROLE[group.trim().toLowerCase()]),
  );
  for (const role of ROLE_PRECEDENCE) {
    if (resolved.has(role)) return role;
  }
  return null;
}
