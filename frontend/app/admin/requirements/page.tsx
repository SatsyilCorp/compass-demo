"use client";

import Link from "next/link";
import { ClipboardCheck, Network } from "lucide-react";

import { DemoCommandCenter } from "@/components/demonstration/demo-command-center";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";

export default function RequirementsPage() {
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker="Factor 3 | Official sequence"
        title="Technical Demonstration Command Center"
        lead="Execute the seven required scenario elements in order, address all five strategic prompts, open the exact working screen and implementation evidence, and keep the full live demonstration within fifty minutes."
        icon={<ClipboardCheck className="size-5" aria-hidden />}
        actions={(
          <Link href="/admin/architecture/" className="inline-flex min-h-10 items-center gap-2 rounded-full border border-gov-primary/25 bg-gov-primary-lighter px-3 text-[10px] font-bold uppercase tracking-wide text-gov-primary hover:bg-gov-primary-lighter/70">
            <Network className="size-3.5" aria-hidden /> Architecture evidence
          </Link>
        )}
      />
      <DemoCommandCenter />
    </AppShell>
  );
}
