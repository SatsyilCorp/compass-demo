import type { Metadata } from "next";
import { Public_Sans, Source_Code_Pro } from "next/font/google";

import "./globals.css";

import { Providers } from "@/lib/auth/providers";

/**
 * Compass type system - the federal USWDS stack (Public Sans), Navy-branded.
 *
 *   Public Sans     → --font-public-sans   (body, UI, headings, display)
 *   Source Code Pro → --font-mono-compass  (grant numbers, run ids, figures)
 */
const publicSans = Public_Sans({
  subsets: ["latin"],
  variable: "--font-public-sans",
  weight: ["400", "500", "600", "700"],
  display: "swap",
});

const sourceCodePro = Source_Code_Pro({
  subsets: ["latin"],
  variable: "--font-mono-compass",
  weight: ["400", "500", "600"],
  display: "swap",
});

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
    <html lang="en" className={`${publicSans.variable} ${sourceCodePro.variable}`}>
      <body className="bg-bg text-text antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
