import type { ReactNode } from "react";

/**
 * Shared page header — the consistent masthead every element page opens
 * with:
 *
 *   KICKER (uppercase, navy)
 *   H1 (Public Sans bold, ink)
 *   lead paragraph (muted)
 *   [optional actions, right-aligned]
 *
 * Element pages (catalog, ingest, analytics, dashboard, export, licenses,
 * admin/pipeline) can import this rather than each rolling their own.
 */
export function PageHeader({
  kicker,
  title,
  lead,
  icon,
  actions,
  className = "",
}: {
  kicker?: ReactNode;
  title: ReactNode;
  lead?: ReactNode;
  /** Small icon shown in a navy chip beside the title. */
  icon?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header className={`flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between ${className}`}>
      <div className="min-w-0">
        {kicker && (
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-gov-primary">{kicker}</p>
        )}
        <h1 className="mt-1.5 flex items-center gap-2.5 text-2xl font-bold leading-tight tracking-tight text-text-strong sm:text-3xl">
          {icon && (
            <span className="inline-flex size-9 shrink-0 items-center justify-center rounded bg-gov-primary text-white">
              {icon}
            </span>
          )}
          <span className="min-w-0">{title}</span>
        </h1>
        {lead && <p className="mt-2 max-w-prose text-sm leading-relaxed text-text-muted">{lead}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </header>
  );
}

export default PageHeader;
