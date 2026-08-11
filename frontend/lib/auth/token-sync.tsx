"use client";

import { useEffect } from "react";
import { useAppAuth } from "./use-app-auth";
import { setAuthContext } from "@/lib/api";

/**
 * Bridges `useAppAuth()` (React-context-bound, live) into `lib/api.ts`'s
 * plain module refs (read from plain async functions, outside React). Also
 * doubles as the mock-mode "RLS" wiring: `orgUnit` drives the client-side
 * org_unit filter in lib/mock/*, so the demo tells the same row-visibility
 * story whether or not a backend is deployed.
 */
export function TokenSync() {
  const auth = useAppAuth();
  useEffect(() => {
    setAuthContext({
      bearerToken: auth.idToken,
      role: auth.role,
      orgUnit: auth.orgUnit,
    });
  }, [auth.idToken, auth.role, auth.orgUnit]);
  return null;
}
