"use client";

/**
 * Single-mode presentation: /rehearsal/* routes redirect to their live
 * counterparts (client-side - a static export on S3+CloudFront has no
 * middleware or server redirects). Flag off, this layout is a passthrough
 * and the rehearsal tree behaves exactly as before.
 */
import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

import { SINGLE_LIVE_MODE } from "@/lib/evidence-mode";

function liveCounterpart(pathname: string): string {
  if (pathname === "/rehearsal" || pathname === "/rehearsal/") return "/";
  const stripped = pathname.replace(/^\/rehearsal/, "");
  return stripped.startsWith("/") ? stripped : `/${stripped}`;
}

function RedirectToLive() {
  const router = useRouter();
  const pathname = usePathname() ?? "/rehearsal/";

  useEffect(() => {
    const target =
      liveCounterpart(pathname) +
      (typeof window !== "undefined" ? window.location.search + window.location.hash : "");
    router.replace(target);
  }, [pathname, router]);

  return (
    <div className="grid min-h-screen place-items-center bg-bg">
      <div className="text-center">
        <p className="animate-pulse text-[12px] font-semibold text-text-muted">Opening the live workspace…</p>
        <noscript>
          <p className="mt-3 text-[12px]">
            <a className="font-semibold text-gov-primary underline" href="/">
              Continue to the live workspace
            </a>
          </p>
        </noscript>
      </div>
    </div>
  );
}

export default function RehearsalLayout({ children }: { children: React.ReactNode }) {
  if (SINGLE_LIVE_MODE) return <RedirectToLive />;
  return <>{children}</>;
}
