import type { ReactNode } from "react";

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
  icon?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <header className={`flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between ${className}`}>
      <div className="min-w-0">
        {kicker && (
          <p className="text-[11px] font-bold uppercase tracking-[0.16em] text-gold-ink">{kicker}</p>
        )}
        <h1 className="mt-2 flex items-start gap-3 text-2xl font-bold leading-tight tracking-tight text-text-strong sm:items-center sm:text-3xl">
          {icon && (
            <span className="inline-flex size-10 shrink-0 items-center justify-center rounded-md bg-gov-primary text-white shadow-soft">
              {icon}
            </span>
          )}
          <span className="min-w-0">{title}</span>
        </h1>
        {lead && <p className="mt-3 max-w-3xl text-sm leading-6 text-text-muted sm:text-[15px]">{lead}</p>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export default PageHeader;
