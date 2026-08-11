"use client";

import Link from "next/link";
import { ClipboardCheck, Workflow } from "lucide-react";

import { DeliveryControl } from "@/components/delivery/delivery-control";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";

export default function DeliveryPage() {
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker="Element 2 of 7 | Infrastructure as Code and Automation"
        title="IaC and DevSecOps Delivery Control"
        lead="Walk from reviewed source through Terraform and SAM validation, security and STIG policy, automated tests, protected approval, short-lived OIDC deployment, runtime verification, and rollback evidence."
        icon={<Workflow className="size-5" aria-hidden />}
        actions={<Link href="/admin/requirements/" className="inline-flex min-h-10 items-center gap-2 rounded-full border border-gov-primary/25 bg-gov-primary-lighter px-3 text-[10px] font-bold uppercase tracking-wide text-gov-primary hover:bg-gov-primary-lighter/70"><ClipboardCheck className="size-3.5" aria-hidden /> Demo sequence</Link>}
      />
      <DeliveryControl />
    </AppShell>
  );
}

