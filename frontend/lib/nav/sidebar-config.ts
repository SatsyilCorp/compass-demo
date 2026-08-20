import type { Role } from "@/lib/types";
import { SINGLE_LIVE_MODE } from "../evidence-mode";
import type { EvidenceMode } from "@/lib/evidence-mode";

export type NavItem = {
  href: string;
  label: string;
  shortLabel: string;
  icon: string;
  stage?: string;
  element: number;
  roles?: Role[];
};

export type NavSection = {
  label: string;
  items: NavItem[];
  roles?: Role[];
  collapsed?: boolean;
};

/** Keep the scored demonstration sequence visible while secondary proof stays collapsible. */
export const SIDEBAR_SECTIONS: NavSection[] = [
  {
    label: "Evidence mode",
    items: [
      { href: "/admin/acquisition/", label: "Live public evidence home", shortLabel: "Live", icon: "radio-tower", element: 1, roles: ["poweruser"] },
      { href: "/rehearsal/", label: "Rehearsal landing", shortLabel: "Rehearsal", icon: "flask-conical", element: 1 },
    ],
  },
  {
    label: "Demonstration sequence",
    items: [
      { href: "/admin/demo/", label: "Start the guided demo", shortLabel: "Start", icon: "map", stage: "START", element: 1, roles: ["poweruser"] },
      { href: "/admin/delivery/", label: "IaC and DevSecOps", shortLabel: "Delivery", icon: "workflow", stage: "02", element: 2, roles: ["poweruser"] },
      { href: "/ingest/", label: "Ingestion and DataOps", shortLabel: "Ingest", icon: "upload-cloud", stage: "03", element: 3 },
      { href: "/catalog/", label: "Governance and catalog", shortLabel: "Govern", icon: "database", stage: "04", element: 4 },
      { href: "/admin/mlops/", label: "Decision analytics and MLOps", shortLabel: "Model", icon: "network", stage: "05", element: 5, roles: ["poweruser"] },
      { href: "/dashboard/", label: "Unified decision workspace", shortLabel: "Decide", icon: "layout-dashboard", stage: "06", element: 6 },
      { href: "/export/", label: "Interoperability and export", shortLabel: "Release", icon: "download", stage: "07", element: 7 },
    ],
  },
  {
    label: "Live public evidence",
    collapsed: true,
    roles: ["poweruser"],
    items: [
      { href: "/admin/acquisition/", label: "Named public source operations", shortLabel: "Sources", icon: "radio-tower", element: 3 },
      { href: "/intelligence/", label: "Accepted public intelligence", shortLabel: "Intelligence", icon: "radar", element: 5 },
    ],
  },
  {
    label: "Supporting evidence",
    collapsed: true,
    items: [
      { href: "/analytics/", label: "Topic intelligence", shortLabel: "Topics", icon: "network", element: 5, roles: ["poweruser"] },
      { href: "/licenses/", label: "Data vendor lifecycle", shortLabel: "Vendors", icon: "key-round", element: 4 },
    ],
  },
  {
    label: "Demo package",
    roles: ["poweruser"],
    collapsed: true,
    items: [
      { href: "/admin/requirements/", label: "Demo requirements trace", shortLabel: "Demo", icon: "clipboard-check", stage: "01", element: 1 },
      { href: "/admin/lineage/", label: "Operational lineage", shortLabel: "Lineage", icon: "workflow", element: 3 },
      { href: "/admin/architecture/", label: "Architecture", shortLabel: "Architecture", icon: "workflow", element: 7 },
      { href: "/admin/scale/", label: "Workload evidence lab", shortLabel: "Scale", icon: "radio-tower", element: 3 },
      { href: "/admin/pipeline/", label: "Mission control", shortLabel: "System", icon: "settings-2", element: 7 },
    ],
  },
];

export function sidebarFor(role: Role | null): NavSection[] {
  return SIDEBAR_SECTIONS
    // Single-mode presentation: the mode-selection section disappears, and the
    // Scale Lab entry goes with it (its page is rehearsal-gated - a dead end
    // when rehearsal cannot be activated).
    .filter((section) => !(SINGLE_LIVE_MODE && section.label === "Evidence mode"))
    .map((section) =>
      SINGLE_LIVE_MODE
        ? { ...section, items: section.items.filter((item) => item.href !== "/admin/scale/") }
        : section,
    )
    .filter((section) => !section.roles || (role && section.roles.includes(role)))
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => !item.roles || (role && item.roles.includes(role))),
    }))
    .filter((section) => section.items.length > 0);
}

export function navItemForPath(pathname: string, role: Role | null): NavItem | undefined {
  const normalized = pathname !== "/rehearsal/" && pathname.startsWith("/rehearsal/")
    ? pathname.slice("/rehearsal".length)
    : pathname;
  return sidebarFor(role)
    .flatMap((section) => section.items)
    .find((item) => normalized === item.href || normalized.startsWith(`${item.href.replace(/\/$/, "")}/`));
}

const REHEARSAL_MISSION_ROUTES = new Set(["/ingest/", "/catalog/", "/analytics/", "/dashboard/", "/export/", "/licenses/"]);

export function navHrefForEvidenceMode(href: string, mode: EvidenceMode): string {
  return mode === "rehearsal" && REHEARSAL_MISSION_ROUTES.has(href)
    ? `/rehearsal${href}`
    : href;
}
