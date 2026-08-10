"use client";

import Link from "next/link";
import { CompassWordmark, PrototypePill } from "./brand";
import { UserMenu } from "./user-menu";

/**
 * Compass masthead — sits above page content. Carries the wordmark (shown
 * on narrow screens where the sidebar rail is hidden), the persistent
 * "Prototype · synthetic data" marker, and the account/persona control.
 */
export function AppHeader() {
  return (
    <header className="sticky top-0 z-30 border-b-2 border-gov-primary bg-surface" role="banner">
      <div aria-hidden className="h-0.5 w-full bg-gold/80" />
      <div className="flex h-16 items-center gap-4 px-4 sm:px-6">
        <Link href="/dashboard/" className="shrink-0 lg:hidden">
          <CompassWordmark tone="navy" />
        </Link>
        <p className="hidden min-w-0 truncate text-sm font-semibold text-text-strong lg:block">
          Compass — S&amp;T Portfolio Intelligence
        </p>
        <div className="ml-auto flex items-center gap-3">
          <PrototypePill className="hidden sm:inline-flex" />
          <span className="hidden h-6 w-px bg-border sm:block" />
          <UserMenu />
        </div>
      </div>
    </header>
  );
}
