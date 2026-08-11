"use client";

import { useCallback, useEffect, useState } from "react";
import { AuthGuard } from "@/components/shell/auth-guard";
import { SkipNav } from "@/components/shell/skip-nav";
import { GovBanner } from "@/components/shell/gov-banner";
import { AppHeader } from "@/components/shell/app-header";
import { Sidebar } from "@/components/shell/sidebar";
import { AppFooter } from "@/components/shell/app-footer";
import type { AppRole } from "@/lib/auth/use-app-auth";
import { PresenterGuide } from "@/components/presenter/presenter-guide";
import { EvidenceSetBar } from "@/components/shell/evidence-set-bar";

export function AppShell({
  children,
  requireRole,
}: {
  children: React.ReactNode;
  requireRole?: AppRole[];
}) {
  const [mobileNavigationOpen, setMobileNavigationOpen] = useState(false);
  const [presenterOpen, setPresenterOpen] = useState(false);
  const closeMobileNavigation = useCallback(() => setMobileNavigationOpen(false), []);

  useEffect(() => {
    setPresenterOpen(new URLSearchParams(window.location.search).get("presenter") === "1");
  }, []);

  const togglePresenter = useCallback(() => {
    setPresenterOpen((current) => {
      const next = !current;
      const url = new URL(window.location.href);
      if (next) url.searchParams.set("presenter", "1");
      else url.searchParams.delete("presenter");
      window.history.replaceState({}, "", `${url.pathname}${url.search}${url.hash}`);
      return next;
    });
  }, []);

  return (
    <AuthGuard expected="signed-in" requireRole={requireRole}>
      <SkipNav />
      <GovBanner />
      <div className="flex min-h-[calc(100vh-2.75rem)] bg-bg">
        <Sidebar mobileOpen={mobileNavigationOpen} onMobileClose={closeMobileNavigation} />
        <div className="flex min-w-0 flex-1 flex-col overflow-x-clip">
          <AppHeader
            menuOpen={mobileNavigationOpen}
            onMenuOpen={() => setMobileNavigationOpen(true)}
            presenterOpen={presenterOpen}
            onPresenterToggle={togglePresenter}
          />
          <EvidenceSetBar />
          <main
            id="main-content"
            tabIndex={-1}
            className="min-w-0 flex-1 px-4 py-6 sm:px-6 sm:py-8 xl:px-8"
          >
            <div className="mx-auto w-full max-w-[1480px]">{children}</div>
          </main>
          <AppFooter />
        </div>
      </div>
      <PresenterGuide open={presenterOpen} onClose={togglePresenter} />
    </AuthGuard>
  );
}
