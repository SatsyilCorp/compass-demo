"use client";

import { useId, useState } from "react";
import { ChevronDown } from "lucide-react";

export function GovBanner() {
  const [open, setOpen] = useState(false);
  const contentId = useId();
  const replay = process.env.NEXT_PUBLIC_USE_MOCK !== "false";

  return (
    <section aria-label="Environment status and prototype disclosure" className="relative z-40 border-b border-border bg-surface-2">
      <div className="mx-auto flex min-h-11 max-w-[1480px] items-center gap-2 px-4 text-xs text-text-muted sm:gap-3 sm:px-6 xl:px-8">
        <span
          aria-hidden
          className={`size-2 shrink-0 rounded-full ring-4 ${
            replay ? "bg-gold ring-gold-soft" : "bg-success ring-success-soft"
          }`}
        />
        <p className="min-w-0 flex-1 truncate">
          <strong className="text-text-strong">{replay ? "Replay mode" : "Live services"}</strong>
          <span className="mx-2 text-border-strong" aria-hidden>|</span>
          Technical prototype using public and synthetic data
        </p>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={contentId}
          onClick={() => setOpen((value) => !value)}
          className="inline-flex min-h-11 shrink-0 items-center gap-1.5 rounded-md px-2 font-semibold text-gov-primary transition-colors hover:bg-gov-primary-lighter"
        >
          <span className="hidden sm:inline">About this demo</span>
          <span className="sm:hidden">About</span>
          <ChevronDown
            aria-hidden
            className={`size-4 transition-transform ${open ? "rotate-180" : ""}`}
          />
        </button>
      </div>
      <div id={contentId} hidden={!open} className="border-t border-border bg-white">
        <div className="mx-auto grid max-w-[1480px] gap-5 px-4 py-5 text-[13px] leading-6 text-text-muted sm:grid-cols-2 sm:px-6 xl:px-8">
          <p>
            <strong className="text-text-strong">Compass</strong> is a Satsyil Corp technical
            demonstration prepared for evaluation of an S&amp;T portfolio intelligence concept. It
            is not deployed, operated, or endorsed by the U.S. Navy, ONR, or any federal agency.
          </p>
          <p>
            Live source operations use bounded, PII-minimized records from named public APIs.
            Seeded mission workflows remain synthetic. No screen represents an authoritative ONR
            inventory or an approved government funding decision.
          </p>
        </div>
      </div>
    </section>
  );
}
