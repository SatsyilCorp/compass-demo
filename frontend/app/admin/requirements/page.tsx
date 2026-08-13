"use client";

import Link from "next/link";
import { ClipboardCheck, Network } from "lucide-react";

import { RequirementsTraceability } from "@/components/requirements/requirements-traceability";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";

export default function RequirementsPage() {
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker="Demo requirements | Evidence-led proof"
        title="Requirement proof and presenter path"
        lead="Show the exact user action, protected screen or API, implementation locator, differentiator, and caveat for every demo ask. Live, configured, target, dependency, and incomplete states remain visibly separate."
        icon={<ClipboardCheck className="size-5" aria-hidden />}
        actions={(
          <Link href="/admin/architecture/" className="inline-flex min-h-10 items-center gap-2 rounded-full border border-gov-primary/25 bg-gov-primary-lighter px-3 text-[10px] font-bold uppercase tracking-wide text-gov-primary hover:bg-gov-primary-lighter/70">
            <Network className="size-3.5" aria-hidden /> Architecture evidence
          </Link>
        )}
      />
      <RequirementsTraceability />
    </AppShell>
  );
}
