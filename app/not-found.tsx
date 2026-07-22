import { OrbitLogo } from "@/components/OrbitLogo";

export default function NotFound() {
  return (
    <main className="crash-page">
      <section className="crash-card" aria-labelledby="not-found-title">
        <a className="brand" href="/"><OrbitLogo />orbit</a>
        <span className="eyebrow">404 · Route not found</span>
        <h1 id="not-found-title">This page is outside the orbit.</h1>
        <p>The address may have changed, or the page may no longer exist.</p>
        <a className="button primary" href="/">Return home</a>
      </section>
    </main>
  );
}
