"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useAppAuth, type AppRole } from "@/lib/auth/use-app-auth";

type Props = {
  expected: "signed-in" | "signed-out";
  /** If set, additionally require the signed-in user to hold one of these roles. */
  requireRole?: AppRole[];
  redirectTo?: string;
  children: React.ReactNode;
};

export function AuthGuard({ expected, requireRole, redirectTo, children }: Props) {
  const router = useRouter();
  const auth = useAppAuth();

  const lacksRequiredRole =
    !!requireRole &&
    requireRole.length > 0 &&
    (!auth.role || !requireRole.includes(auth.role));

  useEffect(() => {
    if (auth.isLoading) return;
    if (expected === "signed-in" && !auth.isAuthenticated) {
      router.replace(redirectTo ?? "/login/");
      return;
    }
    if (expected === "signed-out" && auth.isAuthenticated) {
      router.replace(redirectTo ?? "/dashboard/");
      return;
    }
    if (expected === "signed-in" && auth.isAuthenticated && lacksRequiredRole) {
      router.replace("/dashboard/");
    }
  }, [auth.isLoading, auth.isAuthenticated, lacksRequiredRole, expected, redirectTo, router]);

  if (auth.isLoading) {
    return (
      <div className="grid min-h-screen place-items-center bg-bg">
        <div className="skeleton h-6 w-40 rounded" aria-label="Loading authentication state" />
      </div>
    );
  }

  if (expected === "signed-in" && !auth.isAuthenticated) return null;
  if (expected === "signed-out" && auth.isAuthenticated) return null;
  if (expected === "signed-in" && lacksRequiredRole) return null;

  return <>{children}</>;
}
