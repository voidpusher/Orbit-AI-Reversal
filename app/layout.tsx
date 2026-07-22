import type { Metadata, Viewport } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { OpticalGlassRuntime } from "@/components/OpticalGlassRuntime";

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
  colorScheme: "dark",
  themeColor: "#07111a",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <OpticalGlassRuntime />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
