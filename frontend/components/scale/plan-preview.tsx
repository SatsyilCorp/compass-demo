import {
  Boxes,
  CalendarClock,
  CircleDollarSign,
  Cpu,
  DatabaseZap,
  Fingerprint,
  LockKeyhole,
  Play,
  RotateCw,
} from "lucide-react";
import {
  formatBytes,
  formatCount,
  formatCurrency,
  formatDuration,
  type ScalePlan,
} from "@/lib/scale";

export function PlanPreview({
  plan,
  loading,
  seed,
  onSeedChange,
  onRefresh,
  onLaunch,
  launching,
  runActive,
}: {
  plan: ScalePlan | null;
  loading: boolean;
  seed: string;
  onSeedChange: (value: string) => void;
  onRefresh: () => void;
  onLaunch: () => void;
  launching: boolean;
  runActive: boolean;
}) {
  const locked = plan?.capacity_state === "locked";
  const launchDisabled = loading || launching || locked || !plan || runActive;

  return (
    <section className="mt-5 overflow-hidden rounded-xl border border-border bg-surface shadow-card" aria-labelledby="scale-plan-heading">
      <header className="flex flex-col gap-4 border-b border-border-2 px-5 py-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <p className="text-[10px] font-bold uppercase tracking-[0.15em] text-gold-ink">Cost-gated execution contract</p>
          <h2 id="scale-plan-heading" className="mt-1 text-lg font-bold text-text-strong">Workload plan</h2>
          <p className="mt-1 text-xs leading-5 text-text-muted">
            Preview binds the exact scale, seed, partition limit, and upper cost bound before launch.
          </p>
        </div>
        <div className="flex flex-col gap-2 sm:flex-row sm:items-end">
          <label className="block">
            <span className="text-[10px] font-bold uppercase tracking-wide text-text-subtle">Deterministic seed</span>
            <span className="mt-1 flex h-11 items-center rounded-md border border-border bg-white px-3 focus-within:border-gov-primary">
              <Fingerprint className="mr-2 size-4 text-text-subtle" aria-hidden />
              <input
                value={seed}
                onChange={(event) => onSeedChange(event.target.value.replace(/\D/g, "").slice(0, 10))}
                inputMode="numeric"
                aria-label="Deterministic seed"
                className="w-32 bg-transparent font-mono text-sm text-text-strong outline-none"
              />
            </span>
          </label>
          <button
            type="button"
            onClick={onRefresh}
            disabled={loading || launching}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md border border-border bg-white px-3 text-xs font-semibold text-text-strong hover:bg-surface-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            <RotateCw className={`size-4 ${loading ? "animate-spin" : ""}`} aria-hidden /> Preview
          </button>
          <button
            type="button"
            onClick={onLaunch}
            disabled={launchDisabled}
            className="inline-flex min-h-11 items-center justify-center gap-2 rounded-md bg-action px-4 text-xs font-bold text-white shadow-soft transition-colors hover:bg-action-hover disabled:cursor-not-allowed disabled:bg-text-subtle"
            title={locked ? "Capacity policy must be unlocked before launch" : undefined}
          >
            {locked ? <LockKeyhole className="size-4" aria-hidden /> : <Play className="size-4" aria-hidden />}
            {locked ? "Capacity locked" : launching ? "Launching" : runActive ? "Run in progress" : "Launch exact plan"}
          </button>
        </div>
      </header>

      {loading && !plan ? (
        <div className="grid grid-cols-2 gap-3 p-5 lg:grid-cols-6" aria-label="Loading workload plan">
          {Array.from({ length: 6 }, (_, index) => <div key={index} className="skeleton h-20 rounded-lg" />)}
        </div>
      ) : plan ? (
        <div className="p-5">
          <dl className="grid grid-cols-2 gap-3 lg:grid-cols-6">
            <PlanMetric icon={DatabaseZap} label="Records" value={formatCount(plan.total_records)} />
            <PlanMetric icon={Boxes} label="Partitions" value={formatCount(plan.partition_count)} />
            <PlanMetric icon={Cpu} label="Worker limit" value={formatCount(plan.concurrency_limit)} />
            <PlanMetric icon={CalendarClock} label="Target" value={formatDuration(plan.target_duration_seconds)} />
            <PlanMetric icon={DatabaseZap} label="Raw estimate" value={formatBytes(plan.estimated_raw_bytes)} />
            <PlanMetric icon={CircleDollarSign} label="Cost ceiling" value={formatCurrency(plan.cost.upper_bound_usd)} emphasis />
          </dl>

          <div className="mt-5 grid gap-5 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.62fr)]">
            <div>
              <h3 className="text-xs font-bold text-text-strong">Synthetic data mix</h3>
              <div className="mt-3 space-y-3">
                {plan.dataset_mix.map((row) => (
                  <div key={row.domain}>
                    <div className="flex items-center justify-between gap-3 text-[11px]">
                      <span className="font-semibold text-text-strong">{row.label}</span>
                      <span className="font-mono text-text-muted">{formatCount(row.records)} · {row.percentage}%</span>
                    </div>
                    <div className="mt-1.5 h-1.5 overflow-hidden rounded-full bg-surface-2">
                      <div className="h-full rounded-full bg-gov-primary" style={{ width: `${row.percentage}%` }} />
                    </div>
                    <p className="mt-1 text-[10px] text-text-subtle">{row.purpose}</p>
                  </div>
                ))}
              </div>
            </div>
            <div className="rounded-lg border border-border bg-surface-2/65 p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h3 className="text-xs font-bold text-text-strong">Modeled run cost</h3>
                  <p className="mt-1 text-[10.5px] leading-4 text-text-muted">{plan.cost.disclaimer}</p>
                </div>
                <span className="rounded-full border border-border bg-white px-2 py-1 text-[9px] font-bold uppercase tracking-wide text-text-subtle">
                  {plan.cost.estimate_source === "replay_model" ? "Replay" : "AWS model"}
                </span>
              </div>
              <div className="mt-4 flex items-end justify-between gap-3">
                <div>
                  <p className="text-[10px] uppercase tracking-wide text-text-subtle">Expected</p>
                  <p className="mt-1 font-mono text-2xl font-bold text-text-strong">{formatCurrency(plan.cost.estimated_run_usd)}</p>
                </div>
                <div className="text-right">
                  <p className="text-[10px] uppercase tracking-wide text-text-subtle">Hard ceiling</p>
                  <p className="mt-1 font-mono text-sm font-bold text-warn">{formatCurrency(plan.cost.upper_bound_usd)}</p>
                </div>
              </div>
              <p className="mt-4 border-t border-border pt-3 text-[10px] leading-4 text-text-subtle">
                Price model date {plan.cost.pricing_as_of}. Incremental idle cost {formatCurrency(plan.cost.incremental_idle_monthly_usd)} per month.
              </p>
            </div>
          </div>
        </div>
      ) : (
        <div className="p-5 text-sm text-text-muted">Select a profile and preview its workload plan.</div>
      )}
    </section>
  );
}

function PlanMetric({
  icon: Icon,
  label,
  value,
  emphasis = false,
}: {
  icon: typeof Boxes;
  label: string;
  value: string;
  emphasis?: boolean;
}) {
  return (
    <div className={`rounded-lg border p-3 ${emphasis ? "border-gold/35 bg-gold-soft" : "border-border bg-white"}`}>
      <dt className="flex items-center gap-1.5 text-[9px] font-bold uppercase tracking-wide text-text-subtle">
        <Icon className={`size-3.5 ${emphasis ? "text-gold-ink" : "text-gov-primary"}`} aria-hidden /> {label}
      </dt>
      <dd className="mt-2 font-mono text-sm font-bold text-text-strong">{value}</dd>
    </div>
  );
}
