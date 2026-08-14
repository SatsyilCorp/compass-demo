import type { Metadata } from "next";

import "./globals.css";

import { Providers } from "@/lib/auth/providers";

/**
 * Compass uses deterministic system font stacks so production builds do not
 * depend on a third-party font host. The primary sans stack is aligned with
 * the federal USWDS typography profile, with native monospace for evidence.
 */

export const metadata: Metadata = {
  title: {
    default: "Compass - S&T Portfolio Intelligence",
    template: "%s · Compass",
  },
  description:
    "Compass is an AWS-hosted Navy and ONR S&T portfolio intelligence proving prototype. It continuously acquires bounded public evidence, preserves quality and lineage receipts, executes governed models, and presents cited decision support. Synthetic data is available only in an explicitly selected rehearsal workspace. This commercial deployment is not an accredited production system.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="bg-bg text-text antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
