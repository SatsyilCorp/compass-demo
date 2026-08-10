/**
 * Sidebar navigation — single source of truth consumed by
 * `components/shell/sidebar.tsx`. Routes map 1:1 to the elements in
 * docs/CONTRACTS.md "Frontend". Icon values are Lucide icon NAMES
 * (kebab-case strings) so this stays plain, JSON-shaped config.
 */
import type { Role } from "@/lib/types";

export type NavItem = {
  href: string;
  label: string;
  icon: string;
  /** Element number from docs/CONTRACTS.md, shown as a hint in the UI. */
  element: number;
};

export type NavSection = {
  label: string;
  items: NavItem[];
  /** Section hidden unless the current role is in this list. Omit = all roles. */
  roles?: Role[];
};

export const SIDEBAR_SECTIONS: NavSection[] = [
  {
    label: "Portfolio",
    items: [
      { href: "/dashboard/", label: "Executive Dashboard", icon: "layout-dashboard", element: 6 },
      { href: "/catalog/", label: "Data Catalog", icon: "database", element: 4 },
      { href: "/analytics/", label: "Topic Analytics", icon: "network", element: 5 },
    ],
  },
  {
    label: "Operations",
    items: [
      { href: "/ingest/", label: "Ingest & Quality", icon: "upload-cloud", element: 3 },
      { href: "/export/", label: "Export", icon: "download", element: 7 },
      { href: "/licenses/", label: "Licenses", icon: "key-round", element: 6 },
    ],
  },
  {
    label: "Admin",
    roles: ["poweruser"],
    items: [{ href: "/admin/pipeline/", label: "Pipeline Config", icon: "settings-2", element: 7 }],
  },
];

export function sidebarFor(role: Role | null): NavSection[] {
  return SIDEBAR_SECTIONS.filter((s) => !s.roles || (role && s.roles.includes(role)));
}
