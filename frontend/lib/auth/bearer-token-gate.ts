/**
 * Synchronizes live API requests with OIDC token publication.
 *
 * AuthProvider restores its user asynchronously. On a direct page load, a
 * child data effect can run before TokenSync publishes the restored ID token.
 * The gate gives that short hydration window one chance to complete instead
 * of sending an unauthenticated request that the JWT authorizer must reject.
 */
export class BearerTokenGate {
  private token: string | null = null;
  private readonly waiters = new Set<(token: string) => void>();

  publish(token: string | null): void {
    this.token = token?.trim() || null;
    if (!this.token) return;

    for (const resolve of this.waiters) resolve(this.token);
    this.waiters.clear();
  }

  async wait(timeoutMs: number): Promise<string | null> {
    if (this.token) return this.token;
    if (timeoutMs <= 0) return null;

    return new Promise((resolve) => {
      let settled = false;
      let timer: ReturnType<typeof setTimeout>;

      const finish = (token: string | null) => {
        if (settled) return;
        settled = true;
        clearTimeout(timer);
        if (token) this.waiters.delete(finish);
        resolve(token);
      };

      timer = setTimeout(() => {
        this.waiters.delete(finish);
        finish(null);
      }, timeoutMs);
      this.waiters.add(finish);
    });
  }
}
