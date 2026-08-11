/** Compass brand primitives built as accessible inline vector artwork. */
export function CompassMark({
  className = "h-9 w-9",
  tone = "navy",
}: {
  className?: string;
  tone?: "navy" | "light";
}) {
  const ring = tone === "light" ? "#ffffff" : "var(--color-gov-primary)";
  const ringSoft = tone === "light" ? "rgba(255,255,255,0.5)" : "var(--color-gov-primary-light)";
  const needleNorth = "var(--color-gold-light)";
  const needleSouth = tone === "light" ? "rgba(255,255,255,0.86)" : "var(--color-gov-primary)";

  return (
    <svg viewBox="0 0 48 48" className={className} role="img" aria-label="Compass">
      <circle cx="24" cy="24" r="20.5" fill="none" stroke={ring} strokeWidth="2" />
      <circle cx="24" cy="24" r="15.5" fill="none" stroke={ringSoft} strokeWidth="1" />
      <path d="M24 9.5 29 24 24 22 19 24 24 9.5Z" fill={needleNorth} />
      <path d="M24 38.5 19 24 24 26 29 24 24 38.5Z" fill={needleSouth} />
      <circle cx="24" cy="24" r="2.4" fill={tone === "light" ? "#ffffff" : "var(--color-gov-primary)"} />
      {[0, 90, 180, 270].map((degrees) => (
        <rect
          key={degrees}
          x="23.3"
          y="3.5"
          width="1.4"
          height="3.5"
          fill={ring}
          transform={`rotate(${degrees} 24 24)`}
        />
      ))}
    </svg>
  );
}

export function CompassWordmark({
  tone = "navy",
  subtitle = "S&T Portfolio Intelligence",
  className = "",
  compact = false,
  adaptive = false,
}: {
  tone?: "navy" | "light";
  subtitle?: string;
  className?: string;
  compact?: boolean;
  adaptive?: boolean;
}) {
  const title = tone === "light" ? "text-white" : "text-gov-primary";
  const subtitleColor = tone === "light" ? "text-white/65" : "text-text-muted";

  return (
    <span className={`inline-flex items-center gap-2.5 ${className}`}>
      <CompassMark tone={tone} className="h-9 w-9 shrink-0" />
      {!compact && (
        <span className={`leading-tight ${adaptive ? "compass-adaptive-wordmark-label" : ""}`}>
          <span className={`block font-display text-[17px] font-bold tracking-tight ${title}`}>
            Compass
          </span>
          <span
            className={`compass-adaptive-wordmark-subtitle block text-[10px] font-semibold uppercase tracking-[0.13em] ${subtitleColor}`}
          >
            {subtitle}
          </span>
        </span>
      )}
    </span>
  );
}

export function TrustIndicator({
  className = "",
  tone = "light",
}: {
  className?: string;
  tone?: "light" | "dark";
}) {
  const replay = process.env.NEXT_PUBLIC_USE_MOCK !== "false";
  const colors =
    tone === "dark"
      ? "border-white/15 bg-white/[0.07] text-white"
      : "border-border-strong bg-surface text-text-strong";

  return (
    <span
      className={`inline-flex min-h-8 items-center gap-2 rounded-full border px-3 text-[11px] font-bold tracking-wide ${colors} ${className}`}
      title={
        replay
          ? "Deterministic replay environment using synthetic demonstration data."
          : "Connected service environment using synthetic demonstration data."
      }
    >
      <span
        aria-hidden
        className={`size-2 rounded-full ${replay ? "bg-gold-light" : "bg-emerald-400"}`}
      />
      {replay ? "Replay mode" : "Live services"}
      <span aria-hidden className={tone === "dark" ? "text-white/35" : "text-text-subtle"}>•</span>
      <span className={tone === "dark" ? "text-white/60" : "text-text-muted"}>Synthetic data</span>
    </span>
  );
}

/** Compatibility export used by the standalone sign-in surface. */
export function PrototypePill({ className = "" }: { className?: string }) {
  return <TrustIndicator className={className} />;
}
