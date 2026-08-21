export type PublicOperationsAuthState = "waiting" | "ready" | "unavailable";

export const PUBLIC_OPERATIONS_AUTH_ERROR =
  "Protected public evidence is unavailable until authentication provides a bearer token.";

export function publicOperationsAuthState(auth: {
  isLoading: boolean;
  idToken: string | null;
}): PublicOperationsAuthState {
  if (auth.idToken?.trim()) return "ready";
  return auth.isLoading ? "waiting" : "unavailable";
}
