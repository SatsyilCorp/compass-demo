/**
 * GET /stream/recent — fixture. A recent-activity ticker across the
 * pipeline (ingest, quality, anomaly, analytics, approval, export).
 * Element 3.
 */
import type { Role, StreamRecentResponse, StreamRecord } from "@/lib/types";
import { visibleGrants } from "./grants";

const KIND_MESSAGE: { kind: StreamRecord["kind"]; message: (grantNo: string) => string }[] = [
  { kind: "ingest", message: (g) => `Curated ${g} from landing batch` },
  { kind: "quality", message: (g) => `Quality gate passed for ${g}` },
  { kind: "anomaly", message: (g) => `Amount-outlier flagged on ${g}` },
  { kind: "analytics", message: (g) => `Topic model re-scored ${g}` },
  { kind: "approval", message: (g) => `Export approval requested referencing ${g}` },
  { kind: "export", message: (g) => `Filtered export completed (includes ${g})` },
];

export function getStreamRecent(role: Role | null, orgUnit: string | null): StreamRecentResponse {
  const visible = visibleGrants(role, orgUnit);
  const n = Math.min(18, visible.length);
  const now = Date.now();
  const records: StreamRecord[] = Array.from({ length: n }, (_, i) => {
    const g = visible[i % visible.length]!;
    const template = KIND_MESSAGE[i % KIND_MESSAGE.length]!;
    return {
      id: `stream-${i}`,
      at: new Date(now - i * 96_000).toISOString(),
      kind: template.kind,
      message: template.message(g.grant_no),
      grant_no: g.grant_no,
      org_unit: g.org_unit,
    };
  });
  return { records };
}
