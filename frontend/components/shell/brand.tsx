/**
 * Compass brand primitives — a purpose-built mark + wordmark so the product
 * reads as its own identity. The mark is a compass-rose needle drawn inline
 * so it inherits the Navy/brass tokens in app/globals.css with no asset
 * pipeline.
 */

export function CompassMark({
  className = "h-9 w-9",
  tone = "navy",
}: {
  className?: string;
  /** "navy" = navy ring/field (on light); "light" = white ring (on navy). */
  tone?: "navy" | "light";
}) {
  const ring = tone === "light" ? "#ffffff" : "var(--color-gov-primary)";
  const ringSoft = tone === "light" ? "rgba(255,255,255,0.55)" : "var(--color-gov-primary-light)";
  const needleN = "var(--color-gov-secondary)"; // brass — points true
  const needleS = tone === "light" ? "rgba(255,255,255,0.85)" : "var(--color-gov-primary)";
  return (
    <svg viewBox="0 0 48 48" className={className} role="img" aria-label="Compass">
      <circle cx="24" cy="24" r="20.5" fill="none" stroke={ring} strokeWidth="2" />
      <circle cx="24" cy="24" r="15.5" fill="none" stroke={ringSoft} strokeWidth="1" />
      {/* Needle — brass tip points N, ring-colored tail points S */}
      <path d="M24 9.5 29 24 24 22 19 24 24 9.5Z" fill={needleN} />
      <path d="M24 38.5 19 24 24 26 29 24 24 38.5Z" fill={needleS} />
      <circle cx="24" cy="24" r="2.4" fill={tone === "light" ? "#ffffff" : "var(--color-gov-primary)"} />
      {/* Ordinal ticks */}
      {[0, 90, 180, 270].map((deg) => (
        <rect
          key={deg}
          x="23.3"
          y="3.5"
          width="1.4"
          height="3.5"
          fill={ring}
          transform={`rotate(${deg} 24 24)`}
        />
      ))}
    </svg>
  );
}

export function CompassWordmark({
  tone = "navy",
  subtitle = "S&T Portfolio Intelligence",
  className = "",
}: {
  tone?: "navy" | "light";
  subtitle?: string;
  className?: string;
}) {
  const title = tone === "light" ? "text-white" : "text-gov-primary";
  const sub = tone === "light" ? "text-white/70" : "text-text-muted";
  return (
    <span className={`flex items-center gap-2.5 ${className}`}>
      <CompassMark tone={tone} className="h-9 w-9 shrink-0" />
      <span className="leading-tight">
        <span className={`block font-display text-[17px] font-semibold tracking-tight ${title}`}>
          Compass
        </span>
        <span className={`block text-[10.5px] font-medium uppercase tracking-[0.14em] ${sub}`}>
          {subtitle}
        </span>
      </span>
    </span>
  );
}

/** Persistent prototype / synthetic-data marker shown in the chrome. */
export function PrototypePill({ className = "" }: { className?: string }) {
  return (
    <span
      className={`compass-proto-pill inline-flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[10.5px] font-semibold tracking-wide ${className}`}
      title="Technical demonstration prototype. All data shown is synthetic; this is not a U.S. Navy or ONR system."
    >
      <span className="inline-block size-1.5 rounded-full bg-gold" aria-hidden />
      Prototype · synthetic data
    </span>
  );
}
