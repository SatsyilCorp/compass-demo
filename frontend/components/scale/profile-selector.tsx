import { CheckCircle2, LockKeyhole, Sparkles } from "lucide-react";
import type { ScaleProfile, ScaleProfileId } from "@/lib/scale";

export function ProfileSelector({
  profiles,
  selected,
  onSelect,
  disabled,
}: {
  profiles: ScaleProfile[];
  selected: ScaleProfileId;
  onSelect: (profileId: ScaleProfileId) => void;
  disabled?: boolean;
}) {
  return (
    <fieldset disabled={disabled}>
      <legend className="text-[11px] font-bold uppercase tracking-[0.15em] text-text-subtle">
        Synthetic workload profile
      </legend>
      <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {profiles.map((profile) => {
          const active = selected === profile.id;
          const locked = profile.capacity_state === "locked";
          return (
            <label
              key={profile.id}
              className={`relative flex min-h-44 cursor-pointer flex-col rounded-xl border p-4 transition-all ${
                active
                  ? "border-gov-primary bg-white shadow-[0_0_0_1px_var(--color-gov-primary),var(--shadow-card)]"
                  : "border-border bg-surface hover:border-border-strong hover:shadow-soft"
              } ${disabled ? "cursor-not-allowed opacity-65" : ""}`}
            >
              <input
                type="radio"
                name="scale-profile"
                value={profile.id}
                checked={active}
                onChange={() => onSelect(profile.id)}
                className="sr-only"
                aria-describedby={`scale-profile-${profile.id}-description`}
              />
              <span className="flex items-start justify-between gap-3">
                <span className="font-mono text-2xl font-bold tracking-tight text-text-strong">{profile.short_label}</span>
                {locked ? (
                  <span className="inline-flex items-center gap-1 rounded-full border border-warn/35 bg-warn-soft px-2 py-1 text-[9px] font-bold uppercase tracking-wide text-warn">
                    <LockKeyhole className="size-3" aria-hidden /> Locked
                  </span>
                ) : active ? (
                  <CheckCircle2 className="size-5 text-success" aria-label="Selected" />
                ) : profile.recommended ? (
                  <span className="inline-flex items-center gap-1 rounded-full bg-gold-soft px-2 py-1 text-[9px] font-bold uppercase tracking-wide text-gold-ink">
                    <Sparkles className="size-3" aria-hidden /> Demo pick
                  </span>
                ) : null}
              </span>
              <span className="mt-2 text-sm font-semibold text-text-strong">{profile.label}</span>
              <span id={`scale-profile-${profile.id}-description`} className="mt-2 text-xs leading-5 text-text-muted">
                {profile.description}
              </span>
              <span className="mt-auto pt-3 text-[10.5px] leading-4 text-text-subtle">{profile.capacity_note}</span>
            </label>
          );
        })}
      </div>
    </fieldset>
  );
}
