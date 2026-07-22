"use client";

import { useEffect } from "react";
import { OrbitLogo } from "@/components/OrbitLogo";
import { captureException } from "@/lib/observability";

export default function GlobalError({ error, reset }: { error: Error & { digest?: string }; reset: () => void }) {
  useEffect(() => {
    captureException(error, { digest: error.digest });
  }, [error]);

  return (
    <main className="crash-page">
      <section className="crash-card" aria-labelledby="error-title">
        <a className="brand" href="/"><OrbitLogo />orbit</a>
        <span className="crash-mark" aria-hidden="true">!</span>
        <h1 id="error-title">Something went wrong</h1>
        <p>Orbit could not finish loading this view. You can retry safely or return home.</p>
        <div className="crash-actions">
          <button className="button primary" onClick={reset}>Try again</button>
          <a className="button ghost" href="/">Go home</a>
        </div>
      </section>
    </main>
  );
}
