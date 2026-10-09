import type { Metadata, Viewport } from "next";
import "reactflow/dist/style.css";
import "./globals.css";
import "./orbit-atelier.css";
import "./workspace-glass.css";
import { Providers } from "./providers";

const siteUrl =
  process.env.NEXT_PUBLIC_SITE_URL ??
  (process.env.VERCEL_PROJECT_PRODUCTION_URL
    ? `https://${process.env.VERCEL_PROJECT_PRODUCTION_URL}`
    : "http://localhost:3000");

export const metadata: Metadata = {
  metadataBase: new URL(siteUrl),
  applicationName: "Orbit",
  title: {
    default: "Orbit — Understand Any Software",
    template: "%s | Orbit",
  },
  description: "Evidence-backed software intelligence reports generated from observable product behavior.",
  keywords: ["software intelligence", "architecture analysis", "product research", "technology detection"],
  alternates: { canonical: "/" },
  manifest: "/manifest.webmanifest",
  openGraph: {
    type: "website",
    url: "/",
    siteName: "Orbit",
    title: "Orbit — Understand Any Software",
    description: "Evidence-backed software intelligence from observable product behavior.",
  },
  twitter: {
    card: "summary",
    title: "Orbit — Understand Any Software",
    description: "Evidence-backed software intelligence from observable product behavior.",
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  colorScheme: "light",
  themeColor: "#f4f2e9",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <svg className="atelier-optical-definitions" aria-hidden="true" focusable="false">
          <defs>
            <filter id="orbit-crystal" x="-10%" y="-10%" width="120%" height="120%" colorInterpolationFilters="sRGB">
              <feTurbulence type="fractalNoise" baseFrequency="0.012 0.028" numOctaves="2" seed="7" result="lens" />
              <feGaussianBlur in="lens" stdDeviation="2" result="smoothLens" />
              <feDisplacementMap in="SourceGraphic" in2="smoothLens" scale="3" xChannelSelector="R" yChannelSelector="G" />
            </filter>
          </defs>
        </svg>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
