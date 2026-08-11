"use client";

import { NuqsAdapter } from "nuqs/adapters/next/app";
import { AuthProvider } from "react-oidc-context";
import { WebStorageStateStore } from "oidc-client-ts";
import { MissionDataProvider } from "@/lib/mission-data-context";
import { TokenSync } from "./token-sync";
import { AUTH_DISABLED } from "./use-app-auth";

const COGNITO_AUTHORITY = process.env.NEXT_PUBLIC_COGNITO_AUTHORITY ?? "";
const COGNITO_DOMAIN = process.env.NEXT_PUBLIC_COGNITO_DOMAIN ?? "";
const COGNITO_CLIENT_ID = process.env.NEXT_PUBLIC_COGNITO_CLIENT_ID ?? "";
const REDIRECT_URI =
  process.env.NEXT_PUBLIC_COGNITO_REDIRECT_URI ?? "http://localhost:3000/login/";
const POST_LOGOUT_URI =
  process.env.NEXT_PUBLIC_COGNITO_POST_LOGOUT_REDIRECT_URI ??
  "http://localhost:3000/login/";

// Explicit OIDC metadata so we point authorize/token/jwks at Cognito's
// Hosted UI domain rather than resolving the issuer's discovery document:
// avoids a network round-trip on every load and keeps /logout (Cognito's
// logout endpoint is a non-RFC redirect needing client_id + logout_uri)
// wired correctly.
const oidcConfig =
  AUTH_DISABLED || !COGNITO_AUTHORITY || !COGNITO_CLIENT_ID || !COGNITO_DOMAIN
    ? null
    : {
        authority: COGNITO_AUTHORITY,
        client_id: COGNITO_CLIENT_ID,
        redirect_uri: REDIRECT_URI,
        post_logout_redirect_uri: POST_LOGOUT_URI,
        response_type: "code",
        scope: "openid email profile",
        // Force the Hosted UI to prompt every sign-in, even with a cached
        // session cookie - otherwise a second tab's sign-in silently
        // completes as the first tab's user.
        extraQueryParams: { prompt: "login" },
        metadata: {
          issuer: COGNITO_AUTHORITY,
          authorization_endpoint: `${COGNITO_DOMAIN}/oauth2/authorize`,
          token_endpoint: `${COGNITO_DOMAIN}/oauth2/token`,
          userinfo_endpoint: `${COGNITO_DOMAIN}/oauth2/userInfo`,
          end_session_endpoint: `${COGNITO_DOMAIN}/logout`,
          jwks_uri: `${COGNITO_AUTHORITY}/.well-known/jwks.json`,
          revocation_endpoint: `${COGNITO_DOMAIN}/oauth2/revoke`,
        },
        // Per-tab token storage: sessionStorage (not localStorage) so
        // multiple tabs can carry different personas side by side.
        userStore:
          typeof window !== "undefined"
            ? new WebStorageStateStore({ store: window.sessionStorage })
            : undefined,
        stateStore:
          typeof window !== "undefined"
            ? new WebStorageStateStore({ store: window.sessionStorage })
            : undefined,
        onSigninCallback: () => {
          if (typeof window !== "undefined") {
            window.history.replaceState({}, document.title, window.location.pathname);
          }
        },
      };

export function Providers({ children }: { children: React.ReactNode }) {
  const inner = (
    <NuqsAdapter>
      <MissionDataProvider>{children}</MissionDataProvider>
    </NuqsAdapter>
  );

  if (AUTH_DISABLED || !oidcConfig) {
    // No AuthProvider context in demo mode - useAppAuth() falls back to the
    // sessionStorage-backed demo persona. TokenSync still runs so lib/api.ts
    // picks up the role/org_unit for the mock-mode RLS simulation.
    return (
      <>
        <TokenSync />
        {inner}
      </>
    );
  }

  return (
    <AuthProvider {...oidcConfig}>
      <TokenSync />
      {inner}
    </AuthProvider>
  );
}
