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
    "Compass - a Navy/ONR S&T Portfolio Intelligence prototype: ingest, quality-gate, catalog/lineage, topic-model analytics, and an executive dashboard over a research-grant portfolio. Synthetic data; not a production system.",
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
