import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Static export → S3/CloudFront (see docs/CONTRACTS.md "Frontend").
  output: "export",
  images: { unoptimized: true },
  trailingSlash: true,
  reactStrictMode: true,
  // Element pages land incrementally from parallel agents; don't let a
  // missing eslint config (or a lint warning in someone else's page) block
  // `next build` from producing `frontend/out`.
  eslint: { ignoreDuringBuilds: true },
};

export default nextConfig;
