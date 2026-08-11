import type { Role } from "@/lib/types";

export type NavItem = {
  href: string;
  label: string;
  shortLabel: string;
  icon: string;
  stage?: string;
  element: number;
};

export type NavSection = {
  label: string;
  items: NavItem[];
  roles?: Role[];
};

/**
 * Navigation follows the product's decision flow. Requirement element numbers
 * remain in metadata for presenter tooling, but do not appear in product copy.
 */
export const SIDEBAR_SECTIONS: NavSection[] = [
  {
    label: "Mission flow",
    items: [
      { href: "/ingest/", label: "Ingest and quality", shortLabel: "Ingest", icon: "upload-cloud", stage: "01", element: 3 },
      { href: "/catalog/", label: "Governed catalog", shortLabel: "Govern", icon: "database", stage: "02", element: 4 },
      { href: "/analytics/", label: "Topic intelligence", shortLabel: "Discover", icon: "network", stage: "03", element: 5 },
      { href: "/dashboard/", label: "Decision brief", shortLabel: "Decide", icon: "layout-dashboard", stage: "04", element: 6 },
      { href: "/export/", label: "Governed release", shortLabel: "Release", icon: "download", stage: "05", element: 7 },
    ],
  },
  {
    label: "Governance",
    items: [
      { href: "/licenses/", label: "License posture", shortLabel: "Licenses", icon: "key-round", element: 6 },
    ],
  },
  {
    label: "System",
    roles: ["poweruser"],
    items: [
      { href: "/admin/requirements/", label: "Requirements trace", shortLabel: "Requirements", icon: "clipboard-check", element: 7 },
      { href: "/admin/architecture/", label: "Architecture", shortLabel: "Architecture", icon: "workflow", element: 7 },
      { href: "/admin/scale/", label: "Scale Lab", shortLabel: "Scale", icon: "radio-tower", element: 7 },
      { href: "/admin/pipeline/", label: "Mission control", shortLabel: "System", icon: "settings-2", element: 7 },
    ],
  },
];

export function sidebarFor(role: Role | null): NavSection[] {
  return SIDEBAR_SECTIONS.filter((section) => !section.roles || (role && section.roles.includes(role)));
}

export function navItemForPath(pathname: string, role: Role | null): NavItem | undefined {
  return sidebarFor(role)
    .flatMap((section) => section.items)
    .find((item) => pathname === item.href || pathname.startsWith(`${item.href.replace(/\/$/, "")}/`));
}
