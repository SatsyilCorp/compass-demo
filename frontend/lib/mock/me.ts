/**
 * GET /me — fixture. Element 1 (current identity/role/org_unit).
 */
import type { MeResponse, Role } from "@/lib/types";
import { ORG_UNIT_LABELS } from "./grants";

const ORG_UNIT_FOR_ROLE: Record<Role, string> = {
  poweruser: "ONR-Corporate",
  viewer: "Code-30",
};

export function getMe(role: Role | null, orgUnit: string | null): MeResponse {
  const effectiveRole: Role = role ?? "viewer";
  const effectiveOrgUnit = orgUnit ?? ORG_UNIT_FOR_ROLE[effectiveRole];
  return {
    sub: `demo-${effectiveRole}`,
    email: `${effectiveRole}@compass.mock`,
    display_name:
      effectiveRole === "poweruser"
        ? "Power User — ONR Corporate"
        : `Viewer — ${ORG_UNIT_LABELS[effectiveOrgUnit] ?? effectiveOrgUnit}`,
    role: effectiveRole,
    org_unit: effectiveOrgUnit,
    groups: [effectiveRole],
  };
}
