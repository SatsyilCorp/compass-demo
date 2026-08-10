"use client";

import { Settings2, ShieldCheck } from "lucide-react";
import { AppShell } from "@/components/shell/app-shell";
import { PageHeader } from "@/components/shell/page-header";
import { PipelineView } from "./pipeline-view";
import { RUNTIME_CONFIG } from "./pipeline-data";

/**
 * /admin/pipeline — a visual of the deployed intake state machine
 * (statemachines/intake.asl.yaml), restricted to the poweruser persona per
 * lib/nav/sidebar-config.ts's Admin section.
 */
export default function AdminPipelinePage() {
  return (
    <AppShell requireRole={["poweruser"]}>
      <PageHeader
        kicker="Element 7 · Admin"
        title="Intake pipeline"
        lead="The deployed intake state machine — an AWS Step Functions EXPRESS workflow fired by every raw-bucket drop and by POST /ingest/simulate. Select a stage for its Lambda, retry/catch policy, and the exact ASL excerpt."
        icon={<Settings2 className="size-4" aria-hidden />}
      />

      <PipelineView />

      <section className="mt-6 rounded-xl border border-border bg-surface p-5 shadow-card">
        <p className="flex items-center gap-2 text-[13px] font-semibold text-text-strong">
          <ShieldCheck className="size-4 text-gov-primary" aria-hidden /> Runtime configuration
        </p>
        <p className="mt-1 text-[12px] text-text-muted">
          Environment variables the intake and quality-gate Lambdas read at invoke time — the levers
          that actually decide gate/curate/quarantine, not just a description of the workflow.
        </p>
        <div className="mt-3 overflow-x-auto">
          <table className="w-full min-w-[560px] border-collapse text-[12px]">
            <thead>
              <tr className="border-b border-border-2 text-left text-[10px] font-bold uppercase tracking-wide text-text-subtle">
                <th className="px-2 py-1.5">Variable</th>
                <th className="px-2 py-1.5">Value</th>
                <th className="px-2 py-1.5">Effect</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border-2">
              {RUNTIME_CONFIG.map((c) => (
                <tr key={c.key}>
                  <td className="px-2 py-1.5 font-mono text-text-strong">{c.key}</td>
                  <td className="px-2 py-1.5 font-mono text-gov-primary-dark">{c.value}</td>
                  <td className="px-2 py-1.5 text-text-muted">{c.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </AppShell>
  );
}
