"use client";

/**
 * Element-mapped source viewer. Evaluators asked to see the implementation
 * alongside the demo, so each element screen can open the exact
 * source-controlled files behind it - read from the repository at build time
 * and stamped with the revision. Purely presentational; no data paths change.
 */
import { useEffect, useState } from "react";
import { Code2, X } from "lucide-react";

import {
  CODE_TOUR,
  CODE_TOUR_REVISION,
  type CodeTourFile,
} from "@/lib/code-tour/sources.generated";

export function CodeTourButton({ route }: { route: string }) {
  const files = CODE_TOUR[route];
  const [open, setOpen] = useState(false);
  if (!files?.length) return null;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="inline-flex min-h-10 shrink-0 items-center justify-center gap-2 rounded-md border border-gov-primary/25 bg-white px-3 text-[10px] font-bold text-gov-primary hover:bg-gov-primary-lighter"
      >
        <Code2 className="size-3.5" aria-hidden />
        View the code
      </button>
      {open ? <CodeTourDrawer files={files} onClose={() => setOpen(false)} /> : null}
    </>
  );
}

function CodeTourDrawer({ files, onClose }: { files: CodeTourFile[]; onClose: () => void }) {
  const [active, setActive] = useState(0);
  const current = files[Math.min(active, files.length - 1)];

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-gov-primary-darker/40" role="dialog" aria-modal="true" aria-label="Source code for this element">
      <button type="button" aria-label="Close code view" className="flex-1 cursor-default" onClick={onClose} />
      <aside className="flex h-full w-full max-w-3xl flex-col border-l border-border bg-surface shadow-elevated">
        <header className="flex items-start justify-between gap-3 border-b border-border bg-surface-2 px-5 py-4">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-wide text-gov-secondary">Source-controlled implementation</p>
            <h2 className="mt-0.5 truncate font-mono text-[13px] font-bold text-text-strong">{current.file}</h2>
            <p className="mt-1 text-[11.5px] leading-5 text-text-muted">{current.note}</p>
          </div>
          <button type="button" onClick={onClose} className="grid size-9 shrink-0 place-items-center rounded-md border border-border text-text-muted hover:bg-surface-2" aria-label="Close">
            <X className="size-4" aria-hidden />
          </button>
        </header>
        {files.length > 1 ? (
          <nav className="flex flex-wrap gap-1.5 border-b border-border px-5 py-2.5" aria-label="Files for this element">
            {files.map((f, i) => (
              <button
                key={f.file}
                type="button"
                onClick={() => setActive(i)}
                aria-pressed={i === active}
                className={
                  i === active
                    ? "rounded bg-gov-primary px-2.5 py-1.5 text-[10.5px] font-bold text-white"
                    : "rounded border border-border px-2.5 py-1.5 text-[10.5px] font-semibold text-text-muted hover:bg-surface-2"
                }
              >
                {f.title}
              </button>
            ))}
          </nav>
        ) : null}
        <div className="min-h-0 flex-1 overflow-auto bg-gov-primary-darker px-0 py-3">
          <pre className="px-5 font-mono text-[11px] leading-[1.55] text-gov-primary-light">
            {current.code.split("\n").map((line, i) => (
              <div key={i} className="flex">
                <span className="w-12 shrink-0 select-none pr-4 text-right text-gov-primary-light/40">{current.startLine + i}</span>
                <span className="whitespace-pre">{line || " "}</span>
              </div>
            ))}
          </pre>
        </div>
        <footer className="border-t border-border bg-surface-2 px-5 py-2.5 text-[10px] text-text-muted">
          Lines {current.startLine}-{current.endLine} of {current.totalLines} · sliced from the repository at revision <span className="font-mono font-bold">{CODE_TOUR_REVISION}</span> · open source
        </footer>
      </aside>
    </div>
  );
}
