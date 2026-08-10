"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  LogIn,
  ShieldCheck,
  Smartphone,
  KeyRound,
  Lock,
  Users,
  ArrowRight,
  LogOut,
  CircleUserRound,
  Radar,
} from "lucide-react";
import { SkipNav } from "@/components/shell/skip-nav";
import { GovBanner } from "@/components/shell/gov-banner";
import { CompassWordmark, PrototypePill } from "@/components/shell/brand";
import { useAppAuth, AUTH_DISABLED, ROLES, ROLE_LABELS, type AppRole } from "@/lib/auth/use-app-auth";
import { setDemoPersona } from "@/lib/auth/demo-persona";
import { getMe } from "@/lib/api";
import type { MeResponse } from "@/lib/types";

/**
 * /login — element 1 (identity).
 *
 *   1. Cognito Hosted UI redirect (or, in the offline demo, a persona
 *      switcher standing in for it — see lib/auth/demo-persona.ts).
 *   2. An MFA explainer, grounded in the real UserPool config in
 *      template.yaml (MfaConfiguration: ON, SOFTWARE_TOKEN_MFA).
 *   3. A zero-trust / least-privilege panel, grounded in the real
 *      deny-by-default JWT authorizer + RLS/CLS story in docs/CONTRACTS.md
 *      and db/migrations/002_rls.sql.
 *   4. Once signed in, the actual GET /me response: role, org_unit, and the
 *      rest of the identity claim set the JWT authorizer derives.
 */
export default function LoginPage() {
  const auth = useAppAuth();
  const router = useRouter();
  const [me, setMe] = useState<MeResponse | null>(null);
  const [meLoading, setMeLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    if (!auth.isAuthenticated) {
      setMe(null);
      return;
    }
    setMeLoading(true);
    getMe()
      .then((res) => {
        if (!cancelled) setMe(res);
      })
      .catch(() => {
        if (!cancelled) setMe(null);
      })
      .finally(() => {
        if (!cancelled) setMeLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [auth.isAuthenticated, auth.role, auth.orgUnit]);

  return (
    <>
      <SkipNav />
      <GovBanner />
      <div className="min-h-screen bg-bg">
        <header className="border-b border-border-2 bg-surface">
          <div className="mx-auto flex max-w-[1200px] items-center justify-between px-4 py-4 sm:px-6">
            <Link href="/" className="rounded outline-none">
              <CompassWordmark tone="navy" />
            </Link>
            <PrototypePill className="hidden sm:inline-flex" />
          </div>
        </header>

        <main id="main-content" tabIndex={-1} className="mx-auto max-w-[1200px] px-4 py-10 sm:px-6 sm:py-14">
          <p className="text-[11px] font-semibold uppercase tracking-[0.15em] text-gov-primary">Element 1 · Identity</p>
          <h1 className="mt-1.5 text-2xl font-bold text-text-strong sm:text-3xl">Sign in to Compass</h1>
          <p className="mt-2 max-w-2xl text-sm leading-relaxed text-text-muted">
            Identity, MFA, and every downstream row a user can see all derive from one Cognito JWT —
            this page walks through how.
          </p>

          <div className="mt-8 grid grid-cols-1 gap-6 lg:grid-cols-2 lg:items-start">
            <IdentityCard auth={auth} me={me} meLoading={meLoading} onContinue={() => router.push("/dashboard/")} />

            <div className="space-y-5">
              <MfaExplainer />
              <ZeroTrustExplainer />
            </div>
          </div>
        </main>
      </div>
    </>
  );
}

function IdentityCard({
  auth,
  me,
  meLoading,
  onContinue,
}: {
  auth: ReturnType<typeof useAppAuth>;
  me: MeResponse | null;
  meLoading: boolean;
  onContinue: () => void;
}) {
  if (auth.isLoading) {
    return (
      <div className="rounded-lg border border-border bg-surface p-6 shadow-card">
        <div className="skeleton h-5 w-40 rounded" />
        <div className="skeleton mt-3 h-9 w-full rounded" />
      </div>
    );
  }

  if (!auth.isAuthenticated) {
    return (
      <div className="rounded-lg border border-border bg-surface p-6 shadow-card">
        <p className="flex items-center gap-2 text-[13px] font-semibold text-text-strong">
          <LogIn className="size-4 text-gov-primary" aria-hidden /> Cognito Hosted UI
        </p>
        <p className="mt-2 text-[12.5px] leading-relaxed text-text-muted">
          Compass has no password form of its own — signing in redirects to the Cognito Hosted UI,
          which challenges for a password and then a TOTP code before issuing a JWT carrying{" "}
          <code className="font-mono text-[11.5px]">cognito:groups</code>.
        </p>
        <button
          type="button"
          onClick={() => auth.signinRedirect()}
          className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-md bg-gov-primary px-4 py-3 text-sm font-semibold text-white shadow-card transition-colors hover:bg-action-hover"
        >
          Continue to Cognito Hosted UI <ArrowRight className="size-4" aria-hidden />
        </button>
      </div>
    );
  }

  const role = me?.role ?? auth.role;
  return (
    <div className="rounded-lg border border-border bg-surface p-6 shadow-card">
      <p className="flex items-center gap-2 text-[13px] font-semibold text-text-strong">
        <CircleUserRound className="size-4 text-gov-primary" aria-hidden />
        <code className="font-mono">GET /me</code>
      </p>

      {AUTH_DISABLED && (
        <div className="mt-3 rounded-md border border-warn/40 bg-warn-soft px-3 py-2 text-[11.5px] text-warn">
          Demo mode — the Hosted UI redirect above is bypassed (
          <code className="font-mono">NEXT_PUBLIC_AUTH_DISABLED=true</code>). Pick a persona to see
          how role and org_unit change what &ldquo;/me&rdquo; returns.
          <label className="mt-2 flex items-center gap-2">
            <Users className="size-3.5 shrink-0" aria-hidden />
            <select
              value={role ?? "poweruser"}
              onChange={(e) => setDemoPersona(e.target.value as AppRole)}
              className="w-full rounded border border-warn/40 bg-surface px-2 py-1 text-[12px] font-medium text-text-strong"
            >
              {ROLES.map((r) => (
                <option key={r} value={r}>
                  {ROLE_LABELS[r]}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      {meLoading || !me ? (
        <div className="mt-4 space-y-2">
          <div className="skeleton h-4 w-3/4 rounded" />
          <div className="skeleton h-4 w-1/2 rounded" />
          <div className="skeleton h-4 w-2/3 rounded" />
        </div>
      ) : (
        <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2.5 text-[12.5px]">
          <Field label="display_name" value={me.display_name} />
          <Field label="role" value={me.role} mono />
          <Field label="org_unit" value={me.org_unit} mono />
          <Field label="email" value={me.email} />
          <Field label="sub" value={me.sub} mono truncate />
          <Field label="groups" value={me.groups.join(", ") || "—"} mono />
        </dl>
      )}

      <div className="mt-5 flex items-center gap-2">
        <button
          type="button"
          onClick={onContinue}
          className="inline-flex flex-1 items-center justify-center gap-2 rounded-md bg-gov-primary px-4 py-2.5 text-[13px] font-semibold text-white shadow-card transition-colors hover:bg-action-hover"
        >
          Enter Compass <ArrowRight className="size-4" aria-hidden />
        </button>
        {!AUTH_DISABLED && (
          <button
            type="button"
            onClick={() => auth.signoutRedirect()}
            className="inline-flex items-center gap-1.5 rounded-md border border-border px-3 py-2.5 text-[12.5px] font-medium text-text-muted hover:border-border-strong hover:text-text-strong"
          >
            <LogOut className="size-3.5" aria-hidden /> Sign out
          </button>
        )}
      </div>
    </div>
  );
}

function Field({ label, value, mono, truncate }: { label: string; value: string; mono?: boolean; truncate?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-[9.5px] font-semibold uppercase tracking-wide text-text-subtle">{label}</dt>
      <dd className={`mt-0.5 text-text-strong ${mono ? "font-mono text-[11.5px]" : ""} ${truncate ? "truncate" : ""}`}>{value}</dd>
    </div>
  );
}

function MfaExplainer() {
  return (
    <section className="rounded-lg border border-border bg-surface p-5 shadow-card">
      <p className="flex items-center gap-2 text-[13px] font-semibold text-text-strong">
        <Smartphone className="size-4 text-gov-primary" aria-hidden /> Multi-factor authentication
      </p>
      <ul className="mt-3 space-y-2 text-[12px] leading-relaxed text-text-muted">
        <li className="flex gap-2">
          <KeyRound className="mt-0.5 size-3.5 shrink-0 text-gov-secondary" aria-hidden />
          MFA is enforced pool-wide (<code className="font-mono text-[11px]">MfaConfiguration: ON</code>) with a TOTP
          software token — no SMS fallback.
        </li>
        <li className="flex gap-2">
          <Lock className="mt-0.5 size-3.5 shrink-0 text-gov-secondary" aria-hidden />
          16-character minimum password, upper/lower/number/symbol all required; temporary passwords expire in 7
          days.
        </li>
        <li className="flex gap-2">
          <Users className="mt-0.5 size-3.5 shrink-0 text-gov-secondary" aria-hidden />
          Sign-up is admin-only — the two demo personas are seeded, never self-registered.
        </li>
        <li className="flex gap-2">
          <ShieldCheck className="mt-0.5 size-3.5 shrink-0 text-gov-secondary" aria-hidden />
          ID and access tokens live 1 hour, refresh tokens 8 hours — short-lived by design, re-issued through the
          same MFA-gated flow.
        </li>
      </ul>
      {AUTH_DISABLED && (
        <p className="mt-3 border-t border-border-2 pt-3 text-[11px] text-text-subtle">
          None of this runs in this walkthrough — the Hosted UI redirect is bypassed for the offline demo. It is
          real configuration on the deployed user pool.
        </p>
      )}
    </section>
  );
}

function ZeroTrustExplainer() {
  return (
    <section className="rounded-lg border border-border bg-surface p-5 shadow-card">
      <p className="flex items-center gap-2 text-[13px] font-semibold text-text-strong">
        <Radar className="size-4 text-gov-primary" aria-hidden /> Zero trust, least privilege
      </p>
      <ul className="mt-3 space-y-2 text-[12px] leading-relaxed text-text-muted">
        <li>
          <strong className="text-text-strong">Deny-by-default on every route</strong> — the HttpApi's default
          authorizer is the Cognito JWT authorizer; there is no unauthenticated route.
        </li>
        <li>
          <strong className="text-text-strong">Re-verified, not just trusted</strong> — a second Lambda authorizer
          independently checks the same token's signature against the pool's live JWKS, issuer, and expiry before
          deriving <code className="font-mono text-[11px]">role</code>/<code className="font-mono text-[11px]">org_unit</code>.
          Anything it can't fully verify is denied.
        </li>
        <li>
          <strong className="text-text-strong">One group, one row scope</strong> —{" "}
          <code className="font-mono text-[11px]">compass-poweruser</code> → org_unit{" "}
          <code className="font-mono text-[11px]">ONR-Corporate</code> (whole portfolio);{" "}
          <code className="font-mono text-[11px]">compass-viewer</code> → org_unit{" "}
          <code className="font-mono text-[11px]">Code-30</code> (its own rows only).
        </li>
        <li>
          <strong className="text-text-strong">Enforced again at the database</strong> —{" "}
          <code className="font-mono text-[11px]">grants_curated</code> runs{" "}
          <code className="font-mono text-[11px]">FORCE ROW LEVEL SECURITY</code>, and the app's runtime role isn't
          the table owner, so it can't bypass the policy even by accident.
        </li>
        <li>
          <strong className="text-text-strong">Column-level, too</strong> — the viewer role has no{" "}
          <code className="font-mono text-[11px]">SELECT</code> grant on{" "}
          <code className="font-mono text-[11px]">amount_usd</code>; award dollar figures are unreadable, not just
          hidden in the UI.
        </li>
        <li>
          <strong className="text-text-strong">Every export is audited</strong> — writes an immutable{" "}
          <code className="font-mono text-[11px]">audit_log</code> row, and rows above the export cap require an
          approval before they'll run.
        </li>
      </ul>
    </section>
  );
}
