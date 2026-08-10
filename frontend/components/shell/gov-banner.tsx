"use client";

import { useId, useState } from "react";
import { ChevronDown } from "lucide-react";

/**
 * Compass's disclosure banner — styled after the familiar federal
 * "official website" banner pattern (flag glyph, expandable detail strip)
 * but with HONEST copy: Compass is a Satsyil-built technical-demonstration
 * prototype for a competitive proposal, not a deployed U.S. Navy/ONR
 * system, and every record in it is synthetic. It never claims to be an
 * official government website.
 */
export function GovBanner() {
  const [open, setOpen] = useState(false);
  const contentId = useId();

  return (
    <section aria-label="Prototype disclosure banner" className="border-b border-border-2 bg-surface-2">
      <div className="mx-auto flex max-w-[1400px] items-center gap-3 px-4 py-1.5 text-[12px] text-text-muted">
        <span aria-hidden className="inline-flex h-3.5 w-5 shrink-0 overflow-hidden rounded-[1px]">
          <svg viewBox="0 0 24 16" width="20" height="14" role="presentation">
            <rect width="24" height="16" fill="#fff" />
            <g fill="var(--color-gov-secondary)">
              {[0, 2, 4, 6, 8, 10, 12].map((y) => (
                <rect key={y} y={y * 1.14} width="24" height="1.14" />
              ))}
            </g>
            <rect width="10" height="8.5" fill="var(--color-gov-primary)" />
          </svg>
        </span>
        <p className="min-w-0 flex-1 truncate">
          <strong className="text-text-strong">Technical demonstration prototype</strong> — not an
          official U.S. Navy or ONR system. All data shown is synthetic.
        </p>
        <button
          type="button"
          aria-expanded={open}
          aria-controls={contentId}
          onClick={() => setOpen((v) => !v)}
          className="inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-0.5 font-medium text-gov-primary hover:underline"
        >
          Learn more
          <ChevronDown
            aria-hidden
            className={`size-3.5 transition-transform ${open ? "rotate-180" : ""}`}
          />
        </button>
      </div>
      <div id={contentId} hidden={!open} className="border-t border-border-2 bg-surface">
        <div className="mx-auto grid max-w-[1400px] gap-6 px-4 py-4 text-[13px] leading-relaxed text-text-muted sm:grid-cols-2">
          <p>
            <strong className="text-text-strong">Compass</strong> is a Satsyil Corp technical
            demonstration built for a competitive proposal evaluation of an S&amp;T Portfolio
            Intelligence platform concept. It is not deployed, operated, or endorsed by the U.S.
            Navy, the Office of Naval Research, or any federal agency.
          </p>
          <p>
            Every grant, award amount, dataset, and identity in this prototype is{" "}
            <strong className="text-text-strong">synthetically generated</strong>. Nothing here
            reflects a real ONR program, awardee, or funding decision.
          </p>
        </div>
      </div>
    </section>
  );
}
