"use client";

import Link from "next/link";
import { SINGLE_LIVE_MODE } from "@/lib/evidence-mode";
import { Menu, Presentation } from "lucide-react";
import { usePathname } from "next/navigation";
import { useAppAuth } from "@/lib/auth/use-app-auth";
import { navItemForPath } from "@/lib/nav/sidebar-config";
import { NotificationCenter } from "@/components/notifications/notification-center";
import { evidenceModeHome } from "@/lib/evidence-mode";
import { useEvidenceMode } from "@/lib/evidence-mode-context";
import { CompassWordmark } from "./brand";
import { UserMenu } from "./user-menu";

export function AppHeader({
  menuOpen = false,
  onMenuOpen,
  presenterOpen = false,
  onPresenterToggle,
}: {
  menuOpen?: boolean;
  onMenuOpen?: () => void;
  presenterOpen?: boolean;
  onPresenterToggle?: () => void;
}) {
  const pathname = usePathname() ?? "";
  const { role } = useAppAuth();
  const { mode } = useEvidenceMode();
  const currentItem = navItemForPath(pathname, role);

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-white/95 shadow-soft backdrop-blur" role="banner">
      <div className="flex min-h-[68px] items-center gap-2 px-3 sm:gap-4 sm:px-6">
        <button
          type="button"
          onClick={onMenuOpen}
          aria-label="Open primary navigation"
          aria-controls="mobile-primary-navigation"
          aria-expanded={menuOpen}
          className="grid size-11 shrink-0 place-items-center rounded-md text-gov-primary transition-colors hover:bg-gov-primary-lighter lg:hidden"
        >
          <Menu className="size-5" aria-hidden />
        </button>

        <Link
          href={evidenceModeHome(mode)}
          aria-label="Compass dashboard"
          className="shrink-0 rounded-md focus-visible:outline-offset-4 lg:hidden"
        >
          <CompassWordmark tone="navy" adaptive />
        </Link>

        <div className="hidden min-w-0 border-l border-border pl-4 md:block lg:border-l-0 lg:pl-0">
          <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-text-subtle">
            Mission workspace
          </p>
          <p className="mt-0.5 truncate text-sm font-bold text-text-strong">
            {currentItem?.label ?? "Portfolio intelligence"}
          </p>
        </div>

        <div className="ml-auto flex min-w-0 items-center gap-2">
          {role === "poweruser" ? <NotificationCenter /> : null}
          {SINGLE_LIVE_MODE ? null : <button
            type="button"
            onClick={onPresenterToggle}
            aria-pressed={presenterOpen}
            className={`inline-flex min-h-11 items-center gap-2 rounded-md border px-3 text-sm font-semibold transition-colors ${
              presenterOpen
                ? "border-gold bg-gold-soft text-gold-ink"
                : "border-border bg-surface text-text-muted hover:bg-surface-2 hover:text-text-strong"
            }`}
            aria-label={presenterOpen ? "Presenter guide active" : "Open presenter guide"}
          >
            <Presentation className="size-4" aria-hidden />
            <span className="hidden xl:inline">{presenterOpen ? "Guide active" : "Presenter guide"}</span>
          </button>}
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
