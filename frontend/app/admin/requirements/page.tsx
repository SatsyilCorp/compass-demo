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
        kicker="System view | Solicitation trace"
        title="Requirements traceability"
        lead="Map priority PWS requirements to working prototype capabilities, the exact screen to show, retained source and runtime proof, and the boundary between demonstrated behavior and production roadmap work."
        icon={<ClipboardCheck className="size-5" aria-hidden />}
        actions={(
          <Link href="/admin/architecture/" className="inline-flex min-h-10 items-center gap-2 rounded-full border border-gov-primary/25 bg-gov-primary-lighter px-3 text-[10px] font-bold uppercase tracking-wide text-gov-primary hover:bg-gov-primary-lighter/70">
            <Network className="size-3.5" aria-hidden /> Architecture flow
          </Link>
        )}
      />
      <RequirementsTraceability />
    </AppShell>
  );
}
