import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { OpticalGlassRuntime } from "@/components/OpticalGlassRuntime";

export const metadata: Metadata = {
  title: "Orbit — Understand Any Software",
  description: "AI-powered software intelligence reports for engineering teams."
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
