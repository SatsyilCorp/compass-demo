"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useRef } from "react";
import {
  CircleDot,
  ChevronDown,
  ClipboardCheck,
  Database,
  Download,
  KeyRound,
  LayoutDashboard,
  Network,
  RadioTower,
  Settings2,
  UploadCloud,
  Workflow,
  X,
  type LucideIcon,
} from "lucide-react";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import { sidebarFor, type NavSection } from "@/lib/nav/sidebar-config";
import { CompassWordmark } from "./brand";

const ICONS: Record<string, LucideIcon> = {
  "layout-dashboard": LayoutDashboard,
  database: Database,
  network: Network,
  "upload-cloud": UploadCloud,
  download: Download,
  "key-round": KeyRound,
  "settings-2": Settings2,
  "radio-tower": RadioTower,
  workflow: Workflow,
  "clipboard-check": ClipboardCheck,
  radar: Network,
};

type SidebarProps = {
  mobileOpen?: boolean;
  onMobileClose?: () => void;
};

export function Sidebar({ mobileOpen = false, onMobileClose = () => undefined }: SidebarProps) {
  const pathname = usePathname() ?? "";
  const { role } = useAppAuth();
  const sections = sidebarFor(role);
  const closeButtonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!mobileOpen) return;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    closeButtonRef.current?.focus();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onMobileClose();
    };
    window.addEventListener("keydown", onKeyDown);
    return () => {
      document.body.style.overflow = previousOverflow;
      window.removeEventListener("keydown", onKeyDown);
    };
  }, [mobileOpen, onMobileClose]);

  return (
    <>
      <aside
        className="compass-rail sticky top-0 hidden h-screen w-[280px] shrink-0 flex-col text-white lg:flex"
        aria-label="Primary navigation"
      >
        <RailContent
          pathname={pathname}
          sections={sections}
        />
      </aside>

      {mobileOpen && (
        <div className="fixed inset-0 z-50 lg:hidden">
          <button
            type="button"
            aria-label="Close navigation"
            className="absolute inset-0 min-h-11 w-full bg-gov-primary-darker/70 backdrop-blur-[2px]"
            onClick={onMobileClose}
          />
          <aside
            id="mobile-primary-navigation"
            role="dialog"
            aria-modal="true"
            aria-label="Primary navigation"
            className="compass-rail compass-drawer-enter relative flex h-full w-[min(88vw,340px)] flex-col text-white shadow-2xl"
          >
            <button
              ref={closeButtonRef}
              type="button"
              onClick={onMobileClose}
              className="absolute right-3 top-3 z-10 grid size-11 place-items-center rounded-md text-white/70 transition-colors hover:bg-white/10 hover:text-white"
              aria-label="Close navigation menu"
            >
              <X className="size-5" aria-hidden />
            </button>
            <RailContent
              pathname={pathname}
              sections={sections}
              onNavigate={onMobileClose}
              mobile
            />
          </aside>
        </div>
      )}
    </>
  );
}

function RailContent({
  pathname,
  sections,
  onNavigate,
  mobile = false,
}: {
  pathname: string;
  sections: NavSection[];
  onNavigate?: () => void;
  mobile?: boolean;
}) {
  return (
    <>
      <div className="border-b border-white/10 px-5 pb-5 pt-5">
        <Link
          href="/dashboard/"
          onClick={onNavigate}
          className="inline-flex min-h-11 items-center rounded-md focus-visible:outline-offset-4"
        >
          <CompassWordmark tone="light" />
        </Link>
        {mobile && <p className="mt-2 text-xs text-white/45">Mission workspace</p>}
      </div>

      <nav className="min-h-0 flex-1 overflow-y-auto px-3 py-5">
        {sections.map((section) => {
          const sectionActive = section.items.some((item) => (
            pathname === item.href || pathname.startsWith(`${item.href.replace(/\/$/, "")}/`)
          ));
          if (section.collapsed) {
            return (
              <details key={section.label} open={sectionActive} className="group mb-3 last:mb-0">
                <summary className="flex min-h-11 cursor-pointer list-none items-center gap-3 rounded-md px-3 text-[12px] font-bold text-white/65 transition-colors hover:bg-white/[0.07] hover:text-white [&::-webkit-details-marker]:hidden">
                  <ChevronDown className="size-4 -rotate-90 text-white/40 transition-transform group-open:rotate-0" aria-hidden />
                  <span>{section.label}</span>
                </summary>
                <NavItems pathname={pathname} section={section} onNavigate={onNavigate} nested />
              </details>
            );
          }
          return (
            <div key={section.label} className="mb-6 last:mb-0">
              <p className="px-3 pb-2 text-[10px] font-bold uppercase tracking-[0.17em] text-gold-light/75">
                {section.label}
              </p>
              <NavItems pathname={pathname} section={section} onNavigate={onNavigate} />
            </div>
          );
        })}
      </nav>

      <div className="border-t border-white/10 px-5 py-4">
        <p className="text-[11px] font-semibold text-white/55">Compass demonstration</p>
        <p className="mt-1 text-[10px] text-white/35">Built by Satsyil Corp</p>
      </div>
    </>
  );
}

function NavItems({
  pathname,
  section,
  onNavigate,
  nested = false,
}: {
  pathname: string;
  section: NavSection;
  onNavigate?: () => void;
  nested?: boolean;
}) {
  return (
    <ul className={`m-0 list-none space-y-1 p-0 ${nested ? "pb-2 pl-3" : ""}`}>
      {section.items.map((item) => {
        const active = pathname === item.href || pathname.startsWith(`${item.href.replace(/\/$/, "")}/`);
        const Icon = ICONS[item.icon] ?? CircleDot;
        return (
          <li key={item.href}>
            <Link
              href={item.href}
              onClick={onNavigate}
              aria-current={active ? "page" : undefined}
              className={`group relative flex min-h-11 items-center gap-3 rounded-md px-3 py-2 text-[13px] transition-colors ${
                active
                  ? "bg-white/12 font-semibold text-white"
                  : "text-white/68 hover:bg-white/[0.07] hover:text-white"
              }`}
            >
              <span aria-hidden className={`absolute inset-y-2 left-0 w-[3px] rounded-full ${active ? "bg-gold-light" : "bg-transparent"}`} />
              <Icon className={`size-[17px] shrink-0 ${active ? "text-gold-light" : "text-white/45 group-hover:text-white/75"}`} aria-hidden />
              <span className="min-w-0 flex-1 truncate">{item.label}</span>
            </Link>
          </li>
        );
      })}
    </ul>
  );
}
