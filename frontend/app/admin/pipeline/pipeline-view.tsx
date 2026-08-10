"use client";

import { useState, type ReactNode } from "react";
import { FileCode2, GitBranch, CircleCheck, XCircle, ArrowRight, ArrowDownRight, type LucideIcon } from "lucide-react";
import { PIPELINE_STATES, HAPPY_PATH, stateById, type StateKind } from "./pipeline-data";

const KIND_ICON: Record<StateKind, LucideIcon> = {
  Task: FileCode2,
  Choice: GitBranch,
  Succeed: CircleCheck,
  Fail: XCircle,
};

const KIND_TONE: Record<StateKind, string> = {
  Task: "border-gov-primary/50 bg-gov-primary-lighter text-gov-primary-dark",
  Choice: "border-gold/60 bg-gold-soft text-gold-ink",
  Succeed: "border-success/50 bg-success-soft text-success",
  Fail: "border-danger/50 bg-danger-soft text-danger",
};

/**
 * Visual of the deployed intake state machine — a div-based spine + stage
 * detail panel, adapted from a prior admin pipeline-view pattern (no
 * canvas/diagramming library). Element 7 (admin/pipeline).
 */
export function PipelineView() {
  const [activeId, setActiveId] = useState<string>("Fetch");
  const active = stateById(activeId);

  return (
    <div className="mt-5">
      {/* Happy-path spine */}
      <div className="overflow-x-auto rounded-xl border border-border bg-surface-2 p-3">
        <ol className="flex min-w-max items-center gap-1">
          {HAPPY_PATH.map((id, i) => {
            const s = stateById(id);
            const Icon = KIND_ICON[s.kind];
            const isActive = id === activeId;
            return (
              <li key={id} className="flex items-center">
                <button
                  type="button"
                  onClick={() => setActiveId(id)}
                  aria-current={isActive ? "step" : undefined}
                  className={`flex w-[122px] flex-col gap-1 rounded-lg border px-2.5 py-2 text-left transition-colors ${
                    isActive
                      ? "border-gov-primary bg-white shadow-[0_0_0_1px_var(--color-gov-primary)]"
                      : "border-border bg-surface hover:bg-surface-2"
                  }`}
                >
                  <span className={`inline-flex size-5 items-center justify-center rounded-full border ${KIND_TONE[s.kind]}`}>
                    <Icon className="size-3" aria-hidden />
                  </span>
                  <span className="text-[11.5px] font-semibold leading-tight text-text-strong">{s.id}</span>
                  <span className="font-mono text-[8.5px] uppercase tracking-wide text-text-subtle">{s.kind}</span>
                </button>
                {i < HAPPY_PATH.length - 1 && <ArrowRight className="mx-1 size-4 shrink-0 text-text-subtle" aria-hidden />}
              </li>
            );
          })}
        </ol>
      </div>

      {/* Off-path branches */}
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
        <BranchCard id="Skipped" from="FetchGate → status = skipped" active={activeId === "Skipped"} onSelect={setActiveId} />
        <BranchCard
          id="Quarantine"
          chainTo="Quarantined"
          from="QualityGate → gate = fail"
          active={activeId === "Quarantine"}
          onSelect={setActiveId}
        />
        <BranchCard id="Failed" from="any Task → States.ALL (caught)" active={activeId === "Failed"} onSelect={setActiveId} />
      </div>

      {/* Active-stage detail panel */}
      <section className="mt-4 rounded-xl border border-border bg-surface p-5 shadow-card">
        <header className="flex flex-wrap items-center gap-3">
          <span className={`inline-flex size-9 items-center justify-center rounded-lg border ${KIND_TONE[active.kind]}`}>
            <StateIcon kind={active.kind} />
          </span>
          <div className="min-w-0 flex-1">
            <h2 className="text-[15px] font-semibold text-text-strong">
              <span className="font-mono text-text-subtle">{active.kind} ·</span> {active.id}
            </h2>
            <p className="mt-0.5 text-[12px] leading-relaxed text-text-muted">{active.comment}</p>
          </div>
        </header>

        <dl className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
          {active.lambda && (
            <Detail label="Lambda">
              <code className="font-mono text-[11.5px] text-text-strong">{active.lambda}</code>
              {active.action && (
                <span className="ml-1.5 text-text-subtle">
                  action = <code className="font-mono">{active.action}</code>
                </span>
              )}
            </Detail>
          )}
          {active.next && (
            <Detail label="Next">
              <code className="font-mono text-[11.5px] text-text-strong">{active.next}</code>
            </Detail>
          )}
          {active.choices && (
            <Detail label="Choices">
              <ul className="space-y-0.5">
                {active.choices.map((c) => (
                  <li key={c.next} className="font-mono text-[11px] text-text-strong">
                    {c.on} → {c.next}
                  </li>
                ))}
                {active.default && <li className="font-mono text-[11px] text-text-subtle">default → {active.default}</li>}
              </ul>
            </Detail>
          )}
          {active.retry && (
            <Detail label="Retry">
              <span className="text-[11.5px] text-text-strong">{active.retry}</span>
            </Detail>
          )}
          {active.catch && (
            <Detail label="Catch">
              <span className="text-[11.5px] text-text-strong">{active.catch}</span>
            </Detail>
          )}
        </dl>

        <div className="mt-4">
          <p className="text-[10px] font-bold uppercase tracking-wider text-text-subtle">
            statemachines/intake.asl.yaml (excerpt)
          </p>
          <pre className="mt-1.5 overflow-auto rounded-lg border border-border-2 bg-surface-2 p-3 font-mono text-[11px] leading-relaxed text-text-strong">
            {active.excerpt}
          </pre>
        </div>
      </section>
    </div>
  );
}

function StateIcon({ kind }: { kind: StateKind }) {
  const Icon = KIND_ICON[kind];
  return <Icon className="size-4" aria-hidden />;
}

function Detail({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <dt className="text-[9.5px] font-bold uppercase tracking-wide text-text-subtle">{label}</dt>
      <dd className="mt-0.5">{children}</dd>
    </div>
  );
}

function BranchCard({
  id,
  from,
  active,
  onSelect,
  chainTo,
}: {
  id: string;
  from: string;
  active: boolean;
  onSelect: (id: string) => void;
  chainTo?: string;
}) {
  const s = stateById(id);
  const Icon = KIND_ICON[s.kind];
  return (
    <button
      type="button"
      onClick={() => onSelect(id)}
      className={`flex items-start gap-2 rounded-lg border px-3 py-2.5 text-left transition-colors ${
        active ? "border-gov-primary bg-white shadow-[0_0_0_1px_var(--color-gov-primary)]" : "border-border bg-surface hover:bg-surface-2"
      }`}
    >
      <ArrowDownRight className="mt-0.5 size-3.5 shrink-0 text-text-subtle" aria-hidden />
      <span className="min-w-0">
        <span className="flex items-center gap-1.5">
          <span className={`inline-flex size-4 items-center justify-center rounded-full border ${KIND_TONE[s.kind]}`}>
            <Icon className="size-2.5" aria-hidden />
          </span>
          <span className="text-[12px] font-semibold text-text-strong">
            {id}
            {chainTo ? ` → ${chainTo}` : ""}
          </span>
        </span>
        <span className="mt-0.5 block text-[10.5px] text-text-subtle">{from}</span>
      </span>
    </button>
  );
}
