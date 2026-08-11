import { CompassMark } from "./brand";

export function AppFooter() {
  return (
    <footer className="border-t border-border bg-white" role="contentinfo">
      <div className="mx-auto flex w-full max-w-[1480px] flex-col gap-3 px-4 py-5 text-xs text-text-subtle sm:flex-row sm:items-center sm:justify-between sm:px-6 xl:px-8">
        <div className="flex items-center gap-2.5">
          <CompassMark tone="navy" className="size-7" />
          <p className="font-semibold text-text-muted">Compass by Satsyil Corp</p>
        </div>
        <p>Technical demonstration. Not an official U.S. Navy or ONR system.</p>
      </div>
    </footer>
  );
}
