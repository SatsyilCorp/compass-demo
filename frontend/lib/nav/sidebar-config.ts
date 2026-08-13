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
  collapsed?: boolean;
};

/** Keep the main product workflow small. Detailed proof remains available on demand. */
export const SIDEBAR_SECTIONS: NavSection[] = [
  {
    label: "Workspace",
    items: [
      { href: "/dashboard/", label: "Overview", shortLabel: "Overview", icon: "layout-dashboard", element: 6 },
      { href: "/ingest/", label: "Bring in data", shortLabel: "Ingest", icon: "upload-cloud", element: 3 },
      { href: "/catalog/", label: "Trusted data", shortLabel: "Catalog", icon: "database", element: 4 },
      { href: "/intelligence/", label: "Intelligence", shortLabel: "Intelligence", icon: "radar", element: 5 },
      { href: "/export/", label: "Share results", shortLabel: "Export", icon: "download", element: 7 },
    ],
  },
  {
    label: "Analysis tools",
    collapsed: true,
    items: [
      { href: "/analytics/", label: "Topic analysis", shortLabel: "Topics", icon: "network", element: 5 },
      { href: "/licenses/", label: "Data sources and licenses", shortLabel: "Sources", icon: "key-round", element: 4 },
    ],
  },
  {
    label: "Demo evidence",
    roles: ["poweruser"],
    collapsed: true,
    items: [
      { href: "/admin/requirements/", label: "Demo guide", shortLabel: "Demo", icon: "clipboard-check", element: 1 },
      { href: "/admin/mlops/", label: "Models and MLOps", shortLabel: "Models", icon: "network", element: 5 },
      { href: "/admin/delivery/", label: "Delivery and security", shortLabel: "Delivery", icon: "workflow", element: 2 },
      { href: "/admin/lineage/", label: "Run history and lineage", shortLabel: "Lineage", icon: "workflow", element: 3 },
      { href: "/admin/architecture/", label: "Architecture", shortLabel: "Architecture", icon: "workflow", element: 7 },
      { href: "/admin/scale/", label: "Scale testing", shortLabel: "Scale", icon: "radio-tower", element: 3 },
      { href: "/admin/pipeline/", label: "System health", shortLabel: "System", icon: "settings-2", element: 7 },
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
