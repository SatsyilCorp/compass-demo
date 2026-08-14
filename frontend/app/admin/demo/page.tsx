"use client";

import Link from "next/link";
import { ClipboardCheck, Map } from "lucide-react";

import { DemoOverview } from "@/components/demonstration/demo-overview";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { useEvidenceMode } from "@/lib/evidence-mode-context";

export default function GuidedDemoPage() {
  const { mode } = useEvidenceMode();
  const rehearsal = mode === "rehearsal";
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker={rehearsal ? "Compass rehearsal | Presenter start" : "Compass live demonstration | Presenter start"}
        title={rehearsal ? "Follow one synthetic fixture through the isolated workflow" : "Follow one real public record from source to decision"}
        lead={rehearsal ? "Use the seven-element path with deterministic fixtures, explicit user actions, and persistent rehearsal labels. This path does not call public authorities or claim operational cloud results." : "Use the seven-element path with live public evidence as the default. AWS polls each authority at a responsible cadence while the browser projects retained changes in near real time. Enter the separate rehearsal workspace only by explicit choice."}
        icon={<Map className="size-5" aria-hidden />}
        actions={<Link href="/admin/requirements/" className="inline-flex min-h-10 items-center gap-2 rounded-full border border-gov-primary/25 bg-gov-primary-lighter px-3 text-[10px] font-bold uppercase tracking-wide text-gov-primary hover:bg-gov-primary-lighter/70"><ClipboardCheck className="size-3.5" aria-hidden /> Full requirement proof</Link>}
      />
      <DemoOverview />
    </AppShell>
  );
}
