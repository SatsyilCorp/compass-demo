"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowRight,
  Database,
  FileInput,
  GitBranch,
  Map,
  RadioTower,
  Split,
  type LucideIcon,
} from "lucide-react";

import { screenContextForPath, type ScreenEvidenceTone } from "@/lib/demo/screen-context";
import { LiveDemoStreamBar } from "./live-demo-stream-bar";

const TONE: Record<ScreenEvidenceTone, {
  icon: LucideIcon;
  badge: string;
  iconClass: string;
  panel: string;
}> = {
  guide: {
    icon: Map,
    badge: "border-gov-primary/25 bg-gov-primary-lighter text-gov-primary",
    iconClass: "bg-gov-primary text-white",
    panel: "border-gov-primary/20 bg-white",
  },
  control: {
    icon: GitBranch,
    badge: "border-info/25 bg-info-soft text-info",
    iconClass: "bg-info text-white",
    panel: "border-info/20 bg-white",
  },
  input: {
    icon: FileInput,
    badge: "border-gold/35 bg-gold-soft text-gold-ink",
    iconClass: "bg-gold text-gov-primary-darker",
    panel: "border-gold/25 bg-white",
  },
  synthetic: {
    icon: Database,
    badge: "border-warn/30 bg-warn-soft text-warn",
    iconClass: "bg-warn text-white",
    panel: "border-warn/20 bg-white",
  },
  public: {
    icon: RadioTower,
    badge: "border-success/30 bg-success-soft text-success",
    iconClass: "bg-success text-white",
    panel: "border-success/20 bg-white",
  },
  mixed: {
    icon: Split,
    badge: "border-info/25 bg-info-soft text-info",
    iconClass: "bg-gov-primary text-white",
    panel: "border-border bg-white",
  },
};

export function ScreenContextBar() {
  const pathname = usePathname() ?? "/";
  const context = screenContextForPath(pathname);
  const style = TONE[context.tone];
  const Icon = style.icon;

  return (
    <>
      <section aria-label="Current screen evidence source" className={`border-b px-4 py-3 sm:px-6 xl:px-8 ${style.panel}`}>
        <div className="mx-auto flex w-full max-w-[1480px] flex-col gap-3 xl:flex-row xl:items-center">
          <div className="flex min-w-0 flex-1 items-start gap-3">
            <span className={`grid size-10 shrink-0 place-items-center rounded-lg ${style.iconClass}`}>
              <Icon className="size-4.5" aria-hidden />
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="text-[10px] font-bold uppercase tracking-wide text-text-subtle">{context.element}</span>
                <span className={`rounded-full border px-2.5 py-1 text-[9px] font-bold uppercase tracking-wide ${style.badge}`}>{context.evidenceLabel}</span>
                <span className="text-xs font-bold text-text-strong">{context.screen}</span>
              </div>
              <div className="mt-1 grid gap-x-5 gap-y-1 text-[10.5px] leading-4 text-text-muted lg:grid-cols-2">
                <p><strong className="text-text-strong">Source:</strong> {context.source}</p>
                <p><strong className="text-text-strong">When it changes:</strong> {context.updateBehavior}</p>
              </div>
            </div>
          </div>
          {context.nextHref && context.nextLabel ? (
            <Link href={context.nextHref} className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-md border border-gov-primary/25 bg-white px-3 text-[10px] font-bold text-gov-primary hover:bg-gov-primary-lighter">
              {context.nextLabel} <ArrowRight className="size-3.5" aria-hidden />
            </Link>
          ) : null}
        </div>
      </section>
      {context.showSyntheticStream ? <LiveDemoStreamBar /> : null}
    </>
  );
}
