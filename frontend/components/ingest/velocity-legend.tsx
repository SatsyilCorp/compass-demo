import { PackageOpen, Timer, Zap, type LucideIcon } from "lucide-react";
import { VELOCITY_META, type Velocity } from "./velocity";

const ICON: Record<Velocity, LucideIcon> = {
  batch: PackageOpen,
  interval: Timer,
  "on-demand": Zap,
};

/**
 * The three ingestion velocities Compass's intake state machine serves,
 * explained side by side. Element 3.
 */
export function VelocityLegend() {
  const order: Velocity[] = ["batch", "interval", "on-demand"];
  return (
    <section aria-labelledby="velocity-legend-h" className="rounded-lg border border-border bg-surface p-4 shadow-card">
      <h2 id="velocity-legend-h" className="text-[13px] font-semibold text-text-strong">
        Three ingestion velocities
      </h2>
      <p className="mt-1 text-[12px] text-text-muted">
        The same intake state machine - Fetch &rarr; Validate &rarr; Persist / Quarantine - processes
        drops arriving at three different cadences.
      </p>
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
        {order.map((v) => {
          const meta = VELOCITY_META[v];
          const Icon = ICON[v];
          return (
            <div key={v} className="rounded-md border border-border-2 bg-surface-2 p-3">
              <p className="flex items-center gap-1.5 text-[12px] font-semibold text-gov-primary">
                <Icon className="size-3.5" aria-hidden /> {meta.label}
              </p>
              <p className="mt-0.5 text-[10.5px] font-medium uppercase tracking-wide text-text-subtle">
                {meta.cadence}
              </p>
              <p className="mt-1.5 text-[11.5px] leading-snug text-text-muted">{meta.blurb}</p>
            </div>
          );
        })}
      </div>
      <p className="mt-3 text-[10.5px] text-text-subtle">
        Velocity tags on the batches below are an illustrative client-side classification for this
        demo - the <code className="font-mono">IngestBatch</code> API shape carries no velocity
        field. A batch you trigger with &ldquo;Drop a file&rdquo; is genuinely on-demand.
      </p>
    </section>
  );
}
