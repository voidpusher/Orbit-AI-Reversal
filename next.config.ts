import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  serverExternalPackages: ["@sparticuz/chromium", "puppeteer-core"],
  outputFileTracingIncludes: {
    "/api/browser-capture": ["./node_modules/@sparticuz/chromium/bin/**/*"],
  },
};

export default nextConfig;
