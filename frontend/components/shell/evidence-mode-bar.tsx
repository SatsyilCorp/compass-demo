"use client";

import { FlaskConical, RadioTower } from "lucide-react";
import { useRouter } from "next/navigation";

import { SINGLE_LIVE_MODE, evidenceModeDisclosure, type EvidenceMode } from "@/lib/evidence-mode";
import { useEvidenceMode } from "@/lib/evidence-mode-context";
import { useMissionDataContext } from "@/lib/mission-data-context";

const OPTIONS: Array<{
  mode: EvidenceMode;
  label: string;
  detail: string;
  icon: typeof RadioTower;
}> = [
  {
    mode: "live",
    label: "Live public evidence",
    detail: "Protected APIs and retained public receipts",
    icon: RadioTower,
  },
  {
    mode: "rehearsal",
    label: "Rehearsal",
    detail: "Explicit deterministic synthetic fixtures",
    icon: FlaskConical,
  },
];

export function EvidenceModeBar() {
  // Single-mode presentation build: the mode is constant, so the toggle
  // disappears entirely. Constant condition - hook order stays stable.
  if (SINGLE_LIVE_MODE) return null;
  const router = useRouter();
  const { hydrated, mode, selectMode } = useEvidenceMode();
  const { selectCurated } = useMissionDataContext();

  const activate = (next: EvidenceMode) => {
    if (hydrated && next === mode) return;
    selectMode(next);
    selectCurated();
    router.push(next === "rehearsal" ? "/rehearsal/" : "/admin/acquisition/");
  };

  return (
    <section className="border-b border-border bg-white px-4 py-2.5 shadow-soft sm:px-6 xl:px-8" aria-label="Evidence mode">
      <div className="mx-auto flex w-full max-w-[1480px] flex-col gap-3 lg:flex-row lg:items-center">
        <div className="min-w-0 flex-1">
          <p className="text-[9px] font-bold uppercase tracking-[0.16em] text-text-subtle">Persistent evidence mode</p>
          <p className="mt-0.5 text-[10.5px] leading-4 text-text-muted">{evidenceModeDisclosure(mode)}</p>
        </div>
        <div className="grid gap-1 rounded-lg border border-border bg-surface-2 p-1 sm:grid-cols-2" role="group" aria-label="Choose evidence mode">
          {OPTIONS.map(({ mode: optionMode, label, detail, icon: Icon }) => {
            const active = optionMode === mode;
            return (
              <button
                key={optionMode}
                type="button"
                aria-pressed={active}
                onClick={() => activate(optionMode)}
                className={`flex min-h-11 items-center gap-2 rounded-md border px-3 text-left transition-colors ${active ? "border-gov-primary bg-gov-primary text-white" : "border-transparent bg-white text-text-muted hover:border-border-strong hover:text-text-strong"}`}
              >
                <Icon className="size-4 shrink-0" aria-hidden />
                <span>
                  <span className="block text-[10px] font-bold">{label}</span>
                  <span className={`block text-[8px] ${active ? "text-white/65" : "text-text-subtle"}`}>{detail}</span>
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </section>
  );
}
