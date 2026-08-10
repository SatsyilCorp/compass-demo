"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Count-up figure for KPI tiles. Adapted from a prior dashboard
 * component of the same name, with two changes:
 *   - the animation start value is read from a ref (the original closed over
 *     `display` while excluding it from the dep list, so a value change
 *     mid-flight restarted from a stale number);
 *   - `prefers-reduced-motion` is read per-run rather than once at module
 *     load, so it is correct in a statically exported page.
 */
type Props = {
  value: number;
  durationMs?: number;
  format?: (n: number) => string;
};

const easeOutCubic = (t: number) => 1 - Math.pow(1 - t, 3);

function prefersReduced(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

export function NumberTick({ value, durationMs = 600, format }: Props) {
  const [display, setDisplay] = useState(0);
  const displayRef = useRef(0);

  useEffect(() => {
    displayRef.current = display;
  }, [display]);

  useEffect(() => {
    const from = displayRef.current;
    const delta = value - from;
    if (delta === 0) return;
    if (prefersReduced()) {
      setDisplay(value);
      return;
    }

    let raf = 0;
    const start = performance.now();
    const tick = (now: number) => {
      const t = Math.min(1, (now - start) / durationMs);
      setDisplay(Math.round(from + delta * easeOutCubic(t)));
      if (t < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value, durationMs]);

  return <span>{format ? format(display) : display.toLocaleString("en-US")}</span>;
}

export default NumberTick;
