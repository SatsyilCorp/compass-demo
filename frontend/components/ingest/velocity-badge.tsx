import { PackageOpen, Timer, Zap, type LucideIcon } from "lucide-react";
import { VELOCITY_META, velocityForBatch, type Velocity } from "./velocity";

const ICON: Record<Velocity, LucideIcon> = {
  batch: PackageOpen,
  interval: Timer,
  "on-demand": Zap,
};

const TONE: Record<Velocity, string> = {
  batch: "border-border-strong bg-surface-2 text-text-muted",
  interval: "border-info/40 bg-info-soft text-info",
  "on-demand": "border-gold/50 bg-gold-soft text-gold-ink",
};

/** Small pill for a batch row. Pass `forced` for a batch whose velocity is
 * genuinely known (e.g. a simulate-triggered batch is always on-demand);
 * otherwise it's derived illustratively from the batch_id - see velocity.ts. */
export function VelocityBadge({ batchId, forced }: { batchId: string; forced?: Velocity }) {
  const v = forced ?? velocityForBatch(batchId);
  const Icon = ICON[v];
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${TONE[v]}`}
      title={VELOCITY_META[v].blurb}
    >
      <Icon className="size-3" aria-hidden />
      {VELOCITY_META[v].label}
    </span>
  );
}
