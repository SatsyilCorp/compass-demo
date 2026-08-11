"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError, setAuthContext } from "@/lib/api";
import { useAppAuth } from "@/lib/auth/use-app-auth";

/**
 * The one data-loading hook the element 6/7 pages use.
 *
 * Two jobs beyond "fetch on mount":
 *
 *  1. **Persona correctness.** `lib/auth/token-sync.tsx` publishes the bearer
 *     token / role / org_unit into `lib/api.ts`, but it lives in `Providers`
 *     (a parent), and React runs child effects before parent effects. On
 *     first paint a page's fetch would therefore fire before the persona is
 *     published and the mock RLS filter would see `org_unit = null` (zero
 *     rows). Publishing it here too (idempotent, same values) makes the very
 *     first request carry the right persona.
 *  2. **Persona switching.** The demo's persona switcher changes role/org_unit
 *     with no reload, so every query re-runs when they change and the whole
 *     page re-renders under the new RLS/CLS scope. That *is* the security
 *     demo.
 */
export type QueryState<T> = {
  data: T | null;
  error: string | null;
  /** True on the first load and on every reload/persona change. */
  loading: boolean;
  reload: () => void;
};

export function describeError(e: unknown): string {
  if (e instanceof ApiError) {
    const body = e.body as { error?: string; message?: string } | null;
    const detail = body?.error ?? body?.message;
    return detail ? `HTTP ${e.status}: ${detail}` : `HTTP ${e.status}`;
  }
  if (e instanceof Error) return e.message;
  return "Unexpected error";
}

export function useCompassQuery<T>(
  loader: () => Promise<T>,
  queryKey = "default",
): QueryState<T> {
  const auth = useAppAuth();

  // The caller passes an inline arrow; keep it in a ref so a new function
  // identity on every render doesn't re-trigger the effect.
  const loaderRef = useRef(loader);
  loaderRef.current = loader;

  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [nonce, setNonce] = useState(0);

  const { isLoading, idToken, role, orgUnit } = auth;

  useEffect(() => {
    if (isLoading) return;
    let cancelled = false;

    setAuthContext({ bearerToken: idToken, role, orgUnit });
    setLoading(true);
    setError(null);

    loaderRef
      .current()
      .then((result) => {
        if (cancelled) return;
        setData(result);
        setLoading(false);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        setError(describeError(e));
        setData(null);
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [isLoading, idToken, role, orgUnit, nonce, queryKey]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { data, error, loading, reload };
}

/**
 * Imperative sibling of `useCompassQuery` for POST actions (chat, approvals,
 * export). Publishes the persona the same way, then runs the call, tracking
 * pending/error state for the button that triggered it.
 */
export function useCompassAction<TArgs extends unknown[], TResult>(
  action: (...args: TArgs) => Promise<TResult>,
): {
  run: (...args: TArgs) => Promise<TResult>;
  pending: boolean;
  error: string | null;
  clearError: () => void;
} {
  const { idToken, role, orgUnit } = useAppAuth();
  const actionRef = useRef(action);
  actionRef.current = action;

  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const run = useCallback(
    async (...args: TArgs): Promise<TResult> => {
      setAuthContext({ bearerToken: idToken, role, orgUnit });
      setPending(true);
      setError(null);
      try {
        return await actionRef.current(...args);
      } catch (e) {
        setError(describeError(e));
        throw e;
      } finally {
        setPending(false);
      }
    },
    [idToken, role, orgUnit],
  );

  return { run, pending, error, clearError: useCallback(() => setError(null), []) };
}
