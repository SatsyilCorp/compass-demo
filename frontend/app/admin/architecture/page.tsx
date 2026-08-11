"use client";

import Link from "next/link";
import { Boxes, ClipboardCheck, ExternalLink, LogIn, Network } from "lucide-react";

import { ArchitectureExplorer } from "@/components/architecture/architecture-explorer";
import { AppFooter } from "@/components/shell/app-footer";
import { CompassWordmark } from "@/components/shell/brand";
import { GovBanner } from "@/components/shell/gov-banner";
import { PageHeader } from "@/components/shell/page-header";
import { SkipNav } from "@/components/shell/skip-nav";

export default function ArchitecturePage() {
  return (
    <>
      <SkipNav />
      <GovBanner />
      <div className="flex min-h-[calc(100vh-2.75rem)] flex-col bg-bg">
        <header className="sticky top-0 z-30 border-b border-border bg-white/95 shadow-soft backdrop-blur" role="banner">
          <div className="mx-auto flex min-h-[68px] w-full max-w-[1480px] items-center gap-4 px-4 sm:px-6 xl:px-8">
            <Link href="/" aria-label="Compass home" className="shrink-0 rounded-md focus-visible:outline-offset-4">
              <CompassWordmark tone="navy" adaptive />
            </Link>
            <div className="hidden min-w-0 border-l border-border pl-4 sm:block">
              <p className="text-[10px] font-bold uppercase tracking-[0.16em] text-text-subtle">Public system view</p>
              <p className="mt-0.5 truncate text-sm font-bold text-text-strong">Architecture</p>
            </div>
            <div className="ml-auto flex items-center gap-3">
              <span className="hidden rounded-full border border-success/30 bg-success-soft px-3 py-1.5 text-[10px] font-bold uppercase tracking-wide text-success md:inline-flex">
                Public reference
              </span>
              <Link
                href="/login/"
                className="inline-flex min-h-11 items-center gap-2 rounded-md border border-gov-primary/25 bg-gov-primary px-3 text-xs font-bold text-white transition-colors hover:bg-gov-primary-dark"
              >
                <LogIn className="size-4" aria-hidden />
                <span className="hidden sm:inline">Sign in to Compass</span>
                <span className="sm:hidden">Sign in</span>
              </Link>
            </div>
          </div>
        </header>
        <main id="main-content" tabIndex={-1} className="min-w-0 flex-1 px-4 py-6 sm:px-6 sm:py-8 xl:px-8">
          <div className="mx-auto flex w-full max-w-[1480px] flex-col gap-6">
            <PageHeader
              kicker="System view | AWS-native proposed and implemented topology"
              title="Architecture Explorer"
              lead="Follow the direct document-drop path, event processing, Bronze, Silver, Gold evidence, SageMaker Adapter, model lifecycle, governed decision products, secure export, CI/CD, IaC, security, scale, and recovery seams. Conditional services and unexecuted production controls are labeled explicitly."
              icon={<Network className="size-5" aria-hidden />}
              actions={(
                <div className="flex flex-wrap gap-2">
                  <Link href="/admin/requirements/" className="inline-flex min-h-10 items-center gap-2 rounded-full border border-gov-primary/25 bg-gov-primary-lighter px-3 text-[10px] font-bold uppercase tracking-wide text-gov-primary hover:bg-gov-primary-lighter/70">
                    <ClipboardCheck className="size-3.5" aria-hidden /> Requirements trace
                  </Link>
                  <a
                    href="https://aws.amazon.com/architecture/icons/"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex min-h-10 items-center gap-2 rounded-full border border-[#ff9900]/40 bg-[#fff7e8] px-3 text-[10px] font-bold uppercase tracking-wide text-[#7a4a00] hover:bg-[#ffefd1]"
                  >
                    <Boxes className="size-3.5" aria-hidden /> Official AWS icons <ExternalLink className="size-3" aria-hidden />
                  </a>
                </div>
              )}
            />
            <div id="architecture-diagram-top">
              <ArchitectureExplorer />
            </div>
          </div>
        </main>
        <AppFooter />
      </div>
    </>
  );
}
