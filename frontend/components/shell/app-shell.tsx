"use client";

import { AuthGuard } from "@/components/shell/auth-guard";
import { SkipNav } from "@/components/shell/skip-nav";
import { GovBanner } from "@/components/shell/gov-banner";
import { AppHeader } from "@/components/shell/app-header";
import { Sidebar } from "@/components/shell/sidebar";
import { AppFooter } from "@/components/shell/app-footer";
import type { AppRole } from "@/lib/auth/use-app-auth";

/**
 * Compass application shell — wraps every signed-in element page.
 *
 *   1. Skip-to-main link (WCAG 2.4.1).
 *   2. Prototype disclosure banner (honest, non-impersonating — see
 *      gov-banner.tsx).
 *   3. Navy sidebar rail — role-aware nav to every element page.
 *   4. Masthead: "Compass — S&T Portfolio Intelligence" + persona control.
 *   5. Main content.
 *   6. Footer with the same disclosure repeated.
 *
 * Usage in an element page:
 *   export default function CatalogPage() {
 *     return <AppShell><PageHeader .../> ... </AppShell>;
 *   }
 * Pass `requireRole` to additionally gate the whole page to one persona
 * (e.g. the admin/pipeline page to `["poweruser"]`).
 */
export function AppShell({
  children,
  requireRole,
}: {
  children: React.ReactNode;
  requireRole?: AppRole[];
}) {
  return (
    <AuthGuard expected="signed-in" requireRole={requireRole}>
      <SkipNav />
      <GovBanner />
      <div className="flex min-h-screen bg-bg">
        <Sidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <AppHeader />
          <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 px-4 py-6 sm:px-6 sm:py-8">
            <div className="mx-auto max-w-[1400px]">{children}</div>
          </main>
          <AppFooter />
        </div>
      </div>
    </AuthGuard>
  );
}
