import { evidenceClassPresentation } from "@/lib/operations-evidence";
import type { OperationsEvidenceClass } from "@/lib/types";

const TONE_STYLE = {
  public: "border-success/30 bg-success-soft text-success",
  prediction: "border-info/30 bg-info-soft text-info",
  synthetic: "border-warn/35 bg-warn-soft text-warn",
  control: "border-gov-primary/25 bg-gov-primary-lighter text-gov-primary",
  mixed: "border-gold/35 bg-gold-light/20 text-gold-ink",
  unknown: "border-border bg-surface-2 text-text-muted",
} as const;

export function EvidenceClassBadge({
  evidenceClass,
  compact = false,
}: {
  evidenceClass: OperationsEvidenceClass;
  compact?: boolean;
}) {
  const presentation = evidenceClassPresentation(evidenceClass);
  return (
    <span
      title={`Content provenance: ${presentation.label}`}
      data-evidence-class={evidenceClass}
      className={`inline-flex items-center rounded-full border font-bold uppercase tracking-wide ${TONE_STYLE[presentation.tone]} ${compact ? "px-1.5 py-0.5 text-[7.5px]" : "px-2 py-1 text-[8px]"}`}
    >
      {presentation.label}
    </span>
  );
}
