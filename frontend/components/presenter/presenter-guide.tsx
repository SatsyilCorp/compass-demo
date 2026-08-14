"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Clock3,
  ExternalLink,
  Presentation,
  RotateCcw,
  X,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";

import { useEvidenceMode } from "@/lib/evidence-mode-context";
import { presenterStepsForMode } from "@/lib/demonstration/presenter-steps";

const STEP_KEY = "compass.presenter.step";
const START_KEY = "compass.presenter.started_at";

function elapsedLabel(seconds: number): string {
  const minutes = Math.floor(seconds / 60).toString().padStart(2, "0");
  const remainder = Math.floor(seconds % 60).toString().padStart(2, "0");
  return `${minutes}:${remainder}`;
}

export function PresenterGuide({ open, onClose }: { open: boolean; onClose: () => void }) {
  const pathname = usePathname() ?? "/dashboard/";
  const router = useRouter();
  const { mode } = useEvidenceMode();
  const steps = useMemo(() => presenterStepsForMode(mode), [mode]);
  const [collapsed, setCollapsed] = useState(false);
  const [stepIndex, setStepIndex] = useState(0);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    if (!open) return;
    const savedStep = Number(window.sessionStorage.getItem(STEP_KEY));
    const routeMatch = steps.findIndex((step) => pathname.startsWith(step.route));
    const initial = Number.isInteger(savedStep) && savedStep >= 0 && savedStep < steps.length
      ? savedStep
      : Math.max(0, routeMatch);
    setStepIndex(initial);

    const savedStart = Number(window.sessionStorage.getItem(START_KEY));
    const start = Number.isFinite(savedStart) && savedStart > 0 ? savedStart : Date.now();
    window.sessionStorage.setItem(START_KEY, String(start));
    setStartedAt(start);
  }, [open, pathname, steps]);

  useEffect(() => {
    if (!open || startedAt === null) return;
    const update = () => setElapsed(Math.max(0, (Date.now() - startedAt) / 1000));
    update();
    const timer = window.setInterval(update, 1000);
    return () => window.clearInterval(timer);
  }, [open, startedAt]);

  const step = steps[stepIndex];
  const nextStep = steps[Math.min(stepIndex + 1, steps.length - 1)];
  const progress = ((stepIndex + 1) / steps.length) * 100;
  const routeIsCurrent = pathname.startsWith(step.route);

  const move = (nextIndex: number) => {
    const bounded = Math.max(0, Math.min(steps.length - 1, nextIndex));
    setStepIndex(bounded);
    window.sessionStorage.setItem(STEP_KEY, String(bounded));
    router.push(`${steps[bounded].route}?presenter=1`);
  };

  const resetTimer = () => {
    const now = Date.now();
    window.sessionStorage.setItem(START_KEY, String(now));
    setStartedAt(now);
    setElapsed(0);
  };

  if (!open) return null;

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={() => setCollapsed(false)}
        className="fixed bottom-4 right-4 z-50 inline-flex min-h-12 items-center gap-2 rounded-full border border-gold bg-gov-primary px-4 text-sm font-semibold text-white shadow-elevated"
      >
        <Presentation className="size-4 text-gold-light" aria-hidden />
        {mode === "rehearsal" ? "Rehearsal" : "Live"} step {stepIndex + 1} of {steps.length}
        <span className="font-mono text-white/70">{elapsedLabel(elapsed)}</span>
      </button>
    );
  }

  return (
    <aside
      aria-label="Presenter guide"
      className="fixed inset-x-3 bottom-3 z-50 overflow-hidden rounded-xl border border-gold/60 bg-gov-primary text-white shadow-2xl sm:left-auto sm:w-[min(520px,calc(100vw-2rem))]"
    >
      <div className="h-1 bg-white/15" aria-hidden>
        <div className="h-full bg-gold-light transition-[width]" style={{ width: `${progress}%` }} />
      </div>
      <header className="flex items-start gap-3 border-b border-white/10 px-4 py-3">
        <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-lg bg-white/10 text-gold-light">
          <Presentation className="size-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-[11px] font-bold uppercase tracking-[0.13em] text-white/55">
            <span>{step.element === "Strategic prompts" ? step.element : `Element ${step.element}`}</span>
            <span aria-hidden>|</span>
            <span>{mode === "rehearsal" ? "Rehearsal" : "Live public"}</span>
            <span aria-hidden>|</span>
            <span>Step {stepIndex + 1} of {steps.length}</span>
            <span aria-hidden>|</span>
            <span>{step.target}</span>
          </div>
          <h2 className="mt-1 text-base font-semibold !text-white">{step.title}</h2>
        </div>
        <button
          type="button"
          onClick={() => setCollapsed(true)}
          aria-label="Collapse presenter guide"
          className="grid size-11 shrink-0 place-items-center rounded-md text-white/60 hover:bg-white/10 hover:text-white"
        >
          <ChevronDown className="size-4" aria-hidden />
        </button>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close presenter guide"
          className="grid size-11 shrink-0 place-items-center rounded-md text-white/60 hover:bg-white/10 hover:text-white"
        >
          <X className="size-4" aria-hidden />
        </button>
      </header>

      <div className="grid gap-3 p-4 sm:grid-cols-2">
        <section className="rounded-lg border border-white/10 bg-white/[0.06] p-3">
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-gold-light">Point to this proof</p>
          <p className="mt-2 text-xs leading-5 text-white/78">{step.proof}</p>
        </section>
        <section className="rounded-lg border border-white/10 bg-white/[0.06] p-3">
          <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-gold-light">Narration cue</p>
          <p className="mt-2 text-xs leading-5 text-white/78">{step.narration}</p>
        </section>
      </div>

      <footer className="flex flex-wrap items-center gap-2 border-t border-white/10 px-4 py-3">
        <button
          type="button"
          onClick={resetTimer}
          className="inline-flex min-h-11 items-center gap-2 rounded-md px-2 text-xs font-semibold text-white/65 hover:bg-white/10 hover:text-white"
        >
          <RotateCcw className="size-3.5" aria-hidden /> Reset
        </button>
        <span className="inline-flex min-h-11 items-center gap-2 rounded-md bg-black/15 px-3 font-mono text-sm font-semibold text-white">
          <Clock3 className="size-4 text-gold-light" aria-hidden /> {elapsedLabel(elapsed)}
        </span>
        <div className="ml-auto flex items-center gap-2">
          <button
            type="button"
            onClick={() => move(stepIndex - 1)}
            disabled={stepIndex === 0}
            aria-label="Previous presenter step"
            className="grid size-11 place-items-center rounded-md border border-white/15 text-white transition hover:bg-white/10 disabled:opacity-35"
          >
            <ChevronLeft className="size-4" aria-hidden />
          </button>
          {!routeIsCurrent ? (
            <Link
              href={`${step.route}?presenter=1`}
              className="inline-flex min-h-11 items-center gap-2 rounded-md bg-gold-light px-4 text-xs font-bold text-gov-primary-dark"
            >
              Open step <ExternalLink className="size-3.5" aria-hidden />
            </Link>
          ) : (
            <button
              type="button"
              onClick={() => move(stepIndex + 1)}
              disabled={stepIndex === steps.length - 1}
              className="inline-flex min-h-11 items-center gap-2 rounded-md bg-gold-light px-4 text-xs font-bold text-gov-primary-dark disabled:opacity-45"
            >
              {stepIndex === steps.length - 1 ? "Demo complete" : `Next: ${nextStep.title}`}
              <ChevronRight className="size-3.5" aria-hidden />
            </button>
          )}
        </div>
      </footer>
    </aside>
  );
}
