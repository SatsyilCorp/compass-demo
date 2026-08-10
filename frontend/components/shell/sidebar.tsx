"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Database,
  Network,
  UploadCloud,
  Download,
  KeyRound,
  Settings2,
  CircleDot,
  type LucideIcon,
} from "lucide-react";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import { sidebarFor } from "@/lib/nav/sidebar-config";
import { CompassWordmark, PrototypePill } from "./brand";

const ICONS: Record<string, LucideIcon> = {
  "layout-dashboard": LayoutDashboard,
  database: Database,
  network: Network,
  "upload-cloud": UploadCloud,
  download: Download,
  "key-round": KeyRound,
  "settings-2": Settings2,
};

/**
 * Navy sidebar rail — the app's primary navigation, role-aware (the "Admin"
 * section only renders for the `poweruser` persona; see
 * lib/nav/sidebar-config.ts). Links cover every element page from
 * docs/CONTRACTS.md "Frontend".
 */
export function Sidebar() {
  const pathname = usePathname() ?? "";
  const { role, displayName, orgUnit } = useAppAuth();
  const sections = sidebarFor(role);

  return (
    <aside
      className="compass-rail sticky top-0 hidden h-screen w-[260px] shrink-0 flex-col text-white/80 lg:flex"
      aria-label="Primary navigation"
    >
      <div className="compass-rise px-5 pb-4 pt-5">
        <Link href="/dashboard/" className="block rounded-lg outline-none">
          <CompassWordmark tone="light" />
        </Link>
      </div>

      {displayName && (
        <div className="mx-5 mb-2 flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-3 py-2">
          <CircleDot className="size-3.5 shrink-0 text-gold" aria-hidden />
          <div className="min-w-0">
            <p className="text-[9.5px] font-medium uppercase tracking-[0.16em] text-white/45">
              Active persona
            </p>
            <p className="truncate text-[12.5px] font-semibold text-white">{displayName}</p>
            {orgUnit && <p className="truncate text-[10.5px] text-white/55">org_unit: {orgUnit}</p>}
          </div>
        </div>
      )}

      <nav className="min-h-0 flex-1 overflow-y-auto px-3 py-3">
        {sections.map((section) => (
          <div key={section.label} className="mb-5">
            <p className="px-3 pb-1.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-gold/80">
              {section.label}
            </p>
            <ul className="m-0 list-none space-y-0.5 p-0">
              {section.items.map((item) => {
                const active =
                  pathname === item.href || pathname.startsWith(item.href.replace(/\/$/, "") + "/");
                const Icon = ICONS[item.icon] ?? CircleDot;
                return (
                  <li key={item.href} className="relative">
                    {active && (
                      <span
                        aria-hidden
                        className="absolute inset-y-1 left-0 w-[3px] rounded-full bg-gov-secondary"
                      />
                    )}
                    <Link
                      href={item.href}
                      aria-current={active ? "page" : undefined}
                      className={`flex items-center gap-2.5 rounded-md px-3 py-2 text-[13px] transition-colors ${
                        active ? "bg-white/10 font-semibold text-white" : "text-white/70 hover:bg-white/5 hover:text-white"
                      }`}
                    >
                      <Icon className={`size-[16px] shrink-0 ${active ? "text-gold" : "text-white/45"}`} aria-hidden />
                      <span className="truncate">{item.label}</span>
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t border-white/10 px-5 py-4">
        <PrototypePill />
        <p className="mt-3 text-[10px] text-white/45">Built by Satsyil Corp</p>
      </div>
    </aside>
  );
}
