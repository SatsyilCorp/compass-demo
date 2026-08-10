/**
 * Fixed categorical color order for the topic trend chart — the dataviz
 * skill's validated 8-hue set (adjacent-pair CVD-safe: worst adjacent ΔE
 * 9.1 OKLab×100 against an ≥8 target; worst adjacent normal-vision ΔE 19.6
 * against a ≥15 floor). Assigned by fixed slot order and never re-derived
 * per filter — see the `dataviz` skill's references/palette.md.
 */
export const TOPIC_SERIES_COLORS = [
  "#2a78d6", // 1 blue
  "#eb6834", // 2 orange
  "#1baf7a", // 3 aqua
  "#eda100", // 4 yellow
  "#e87ba4", // 5 magenta
  "#008300", // 6 green
  "#4a3aa7", // 7 violet
  "#e34948", // 8 red
] as const;

export function seriesColor(index: number): string {
  return TOPIC_SERIES_COLORS[index % TOPIC_SERIES_COLORS.length]!;
}
