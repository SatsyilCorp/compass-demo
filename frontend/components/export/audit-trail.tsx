"use client";

import clsx from "clsx";
import { ScrollText } from "lucide-react";

import { dateTimeShort } from "@/components/dashboard/format";

/**
 * Audit trail (element 7).
 *
 * Honest framing, stated on the panel: this is a client-side echo of the calls
 * this page made in this session. The authoritative record is the append-only
 * `compass.audit_log` table, written server-side by `POST /export` and
 * `POST /approvals`; the prototype exposes no read endpoint for it, so nothing
 * here is presented as having been read back from the database.
 */
export type AuditEvent = {
  id: number;
  at: string;
  actor: string;
  action: string;
  resource: string;
  detail: Record<string, unknown>;
  outcome: "ok" | "denied";
};

export function AuditTrail({ events }: { events: AuditEvent[] }) {
  return (
    <section className="rounded-md border border-border bg-surface shadow-soft">
      <header className="flex items-start gap-2.5 border-b border-border px-4 py-3">
        <span className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded bg-gov-primary text-white">
          <ScrollText className="size-4" aria-hidden />
        </span>
        <div>
          <h2 className="text-[14.5px] font-semibold text-text-strong">Audit trail</h2>
          <p className="mt-0.5 text-[11.5px] leading-snug text-text-muted">
            Every call this page made, in order. The API writes the same actions to the append-only{" "}
            <code className="font-mono text-[11px]">compass.audit_log</code> table server-side; this
            list is the client&apos;s echo of them, not a read-back of that table.
          </p>
        </div>
      </header>

      {events.length === 0 ? (
        <p className="px-4 py-6 text-center text-[12px] text-text-subtle">
          No export activity yet in this session.
        </p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] border-collapse text-left">
            <thead>
              <tr className="border-b border-border text-[10px] uppercase tracking-[0.1em] text-text-subtle">
                <th scope="col" className="px-4 py-2 font-semibold">
                  At
                </th>
                <th scope="col" className="px-4 py-2 font-semibold">
                  Actor
                </th>
                <th scope="col" className="px-4 py-2 font-semibold">
                  Action
                </th>
                <th scope="col" className="px-4 py-2 font-semibold">
                  Resource
                </th>
                <th scope="col" className="px-4 py-2 font-semibold">
                  Detail
                </th>
              </tr>
            </thead>
            <tbody>
              {events.map((e) => (
                <tr key={e.id} className="border-b border-border-2 last:border-b-0 align-top">
                  <td className="whitespace-nowrap px-4 py-2 font-mono text-[11px] text-text-muted">
                    {dateTimeShort(e.at)}
                  </td>
                  <td className="whitespace-nowrap px-4 py-2 text-[11.5px] text-text">{e.actor}</td>
                  <td className="whitespace-nowrap px-4 py-2">
                    <span
                      className={clsx(
                        "rounded px-1.5 py-0.5 font-mono text-[11px] font-semibold",
                        e.outcome === "denied"
                          ? "bg-danger-soft text-danger"
                          : "bg-success-soft text-success",
                      )}
                    >
                      {e.action}
                    </span>
                  </td>
                  <td className="whitespace-nowrap px-4 py-2 font-mono text-[11px] text-text-muted">
                    {e.resource}
                  </td>
                  <td className="max-w-[420px] break-all px-4 py-2 font-mono text-[10.5px] leading-snug text-text-muted">
                    {JSON.stringify(e.detail)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </section>
  );
}

export default AuditTrail;
