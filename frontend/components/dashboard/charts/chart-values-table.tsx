"use client";

/**
 * The table view behind a plotted chart.
 *
 * Any value that a chart carries only in a hover tooltip is unreachable to a
 * keyboard or screen-reader user and invisible in print. The SVG charts here
 * therefore ship a collapsed table of the same rows — the numbers are never
 * gated behind hover or color.
 */
export function ChartValuesTable({
  caption,
  columns,
  rows,
}: {
  caption: string;
  columns: string[];
  rows: (string | number)[][];
}) {
  if (rows.length === 0) return null;
  return (
    <details className="mt-3">
      <summary className="cursor-pointer text-[11px] font-semibold text-text-muted">
        {caption}
      </summary>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full border-collapse text-left">
          <thead>
            <tr className="border-b border-border text-[10px] uppercase tracking-[0.1em] text-text-subtle">
              {columns.map((c) => (
                <th key={c} scope="col" className="py-1.5 pr-4 font-semibold">
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((r, i) => (
              <tr key={i} className="border-b border-border-2 last:border-b-0">
                {r.map((cell, j) => (
                  <td
                    key={j}
                    className={
                      j === 0
                        ? "py-1.5 pr-4 text-[11.5px] text-text"
                        : "py-1.5 pr-4 font-mono text-[11.5px] tabular-nums text-text-strong"
                    }
                  >
                    {cell}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </details>
  );
}

export default ChartValuesTable;
