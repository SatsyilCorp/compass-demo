/**
 * Quality/health score chip - the compact score badge used in the catalog
 * table and reused (larger) at the top of the expandable quality panel.
 * Tone thresholds mirror the 3-tier status palette already defined in
 * app/globals.css (success / warn / danger) so a reader learns the mapping
 * once and reuses it everywhere in Compass.
 */
export type ScoreTone = "success" | "warn" | "danger";

export function scoreTone(score: number): ScoreTone {
  if (score >= 90) return "success";
  if (score >= 70) return "warn";
  return "danger";
}

const TONE_CLASSES: Record<ScoreTone, string> = {
  success: "border-success/40 bg-success-soft text-success",
  warn: "border-warn/40 bg-warn-soft text-warn",
  danger: "border-danger/40 bg-danger-soft text-danger",
};

export function ScoreChip({
  score,
  size = "md",
  className = "",
}: {
  score: number;
  size?: "sm" | "md" | "lg";
  className?: string;
}) {
  const tone = scoreTone(score);
  const pad =
    size === "sm" ? "px-1.5 py-0.5 text-[10.5px]" : size === "lg" ? "px-2.5 py-1.5 text-sm" : "px-2 py-1 text-xs";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border font-mono font-semibold tabular-nums ${TONE_CLASSES[tone]} ${pad} ${className}`}
      title={`Quality score ${score.toFixed(1)} / 100`}
    >
      {score.toFixed(1)}
    </span>
  );
}
