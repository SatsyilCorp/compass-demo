import type { Role } from "@/lib/types";

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
    .filter((section) => !section.roles || (role && section.roles.includes(role)))
    .map((section) => ({
      ...section,
      items: section.items.filter((item) => !item.roles || (role && item.roles.includes(role))),
    }))
    .filter((section) => section.items.length > 0);
}

export function navItemForPath(pathname: string, role: Role | null): NavItem | undefined {
  return sidebarFor(role)
    .flatMap((section) => section.items)
    .find((item) => pathname === item.href || pathname.startsWith(`${item.href.replace(/\/$/, "")}/`));
}
