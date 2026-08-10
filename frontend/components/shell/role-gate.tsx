"use client";

import { useAppAuth, type AppRole } from "@/lib/auth/use-app-auth";

type Props = {
  allow: AppRole[];
  /** Render this when the role doesn't match instead of nothing. */
  fallback?: React.ReactNode;
  children: React.ReactNode;
};

/**
 * Inline UI gate driven by the current persona's role — for hiding/showing
 * a control or panel within a page. For full-route gating use
 * `<AuthGuard requireRole={[...]}>` instead.
 */
export function RoleGate({ allow, fallback = null, children }: Props) {
  const { role } = useAppAuth();
  if (role && allow.includes(role)) return <>{children}</>;
  return <>{fallback}</>;
}
