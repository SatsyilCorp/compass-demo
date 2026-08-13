import Link from "next/link";
import { ClipboardCheck, Map } from "lucide-react";

import { DemoOverview } from "@/components/demonstration/demo-overview";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";

export default function GuidedDemoPage() {
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker="Compass demonstration | Presenter start"
        title="Know exactly what to show and where every value comes from"
        lead="Use the seven-element path for the scored presentation. Open the separate public evidence lane only when you want real records from named public APIs. Every destination repeats its source and update behavior at the top of the screen."
        icon={<Map className="size-5" aria-hidden />}
        actions={<Link href="/admin/requirements/" className="inline-flex min-h-10 items-center gap-2 rounded-full border border-gov-primary/25 bg-gov-primary-lighter px-3 text-[10px] font-bold uppercase tracking-wide text-gov-primary hover:bg-gov-primary-lighter/70"><ClipboardCheck className="size-3.5" aria-hidden /> Full requirement proof</Link>}
      />
      <DemoOverview />
    </AppShell>
  );
}
