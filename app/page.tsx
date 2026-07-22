"use client";

import { ArrowRight, Bot, Boxes, Braces, Check, ChevronRight, CirclePlay, Code2, Database, Eye, Github, Globe2, Layers3, Network, Search, ShieldCheck, Sparkles, Waypoints } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { OrbitLogo } from "@/components/OrbitLogo";

const features = [
  [Eye, "Feature detection", "Map product capabilities from observable behavior."],
  [Network, "Architecture mapping", "Turn web signals into an evidence-backed system view."],
  [Waypoints, "User flow discovery", "Follow key journeys from entry point to outcome."],
  [Braces, "API detection", "Surface public request patterns and integration boundaries."],
  [Database, "Database inference", "Explore likely entities and relationships with confidence."],
  [Code2, "Engineering insights", "Understand the choices behind a product’s experience."],
];

const DEMO_URL = "https://linear.app";
const DEMO_LOGS: [string, string][] = [
  ["00:01", "GET / 200 · document parsed"],
  ["00:03", "graphql · IssueBoard query observed"],
  ["00:05", "ws wss://sync.linear.app · realtime open"],
  ["00:08", "42 modules mapped · React fingerprint"],
];

function HeroDemo() {
  const reduced = useReducedMotion();
  const [now, setNow] = useState(0);
  useEffect(() => {
    if (reduced) return;
    const started = Date.now();
    const id = setInterval(() => setNow(((Date.now() - started) % 13000) / 13000), 90);
    return () => clearInterval(id);
  }, [reduced]);

  const t = reduced ? 1 : now;
  const typed = DEMO_URL.slice(0, Math.ceil(Math.min(t / 0.13, 1) * DEMO_URL.length));
  const scan = Math.max(0, Math.min((t - 0.14) / 0.42, 1));
  const scanning = t >= 0.14 && t < 0.84;
  const done = t >= 0.84;
  const conf = Math.round(Math.max(0, Math.min((t - 0.6) / 0.24, 1)) * 94);
  const nodeOn = (index: number) => t > 0.48 + index * 0.07;
  const sigOn = (index: number) => t > 0.74 + index * 0.03;
  const logOn = (index: number) => t > 0.17 + index * 0.09;

  return (
    <div className="window-body">
      <aside className="mini-sidebar"><span className="mini-logo">o</span><span className="mini-active"><Layers3 size={16} /></span><span><Network size={16} /></span><span><Database size={16} /></span><span><Boxes size={16} /></span></aside>
      <div className="report-preview">
        <div className="demo-url"><Search size={13} /><b>{typed}</b>{t < 0.14 && <span className="demo-caret" />}<span className="demo-go">{done ? "DONE" : scanning ? "EXPLORING" : "ANALYZE"}</span></div>
        <div className="preview-top"><div><span className="report-kicker">{done ? "REPORT OVERVIEW" : "LIVE EXPLORATION"}</span><h3 className={`demo-pop${t > 0.14 ? " on" : ""}`}>Linear</h3></div><span className={`confidence demo-pop${t > 0.62 ? " on" : ""}`}>{conf}% confidence</span></div>
        <div className="preview-metrics">
          <div><strong>{Math.round(scan * 24)}</strong><span>pages explored</span></div>
          <div><strong>{Math.round(scan * 17)}</strong><span>features found</span></div>
          <div><strong>{Math.round(scan * 126)}</strong><span>evidence points</span></div>
        </div>
        <div className="architecture-card"><div className="card-heading"><span>Observed architecture</span><ChevronRight size={15} /></div>
          <div className="node-flow"><b className={`demo-dim${nodeOn(0) ? " on" : ""}`}><Globe2 size={15} /> Browser</b><i /><b className={`demo-dim${nodeOn(1) ? " on" : ""}`}><Code2 size={15} /> Frontend</b><i /><b className={`demo-dim${nodeOn(2) ? " on" : ""}`}><Network size={15} /> API</b></div>
          <div className="node-flow lower"><b className={`demo-dim${nodeOn(3) ? " on" : ""}`}><Database size={15} /> Postgres</b><i /><b className={`demo-dim${nodeOn(4) ? " on" : ""}`}><Sparkles size={15} /> Realtime</b></div>
        </div>
        <div className="demo-log" aria-hidden>{DEMO_LOGS.map(([time, line], index) => <p className={`demo-pop${logOn(index) ? " on" : ""}`} key={time}><time>{time}</time>{line.split(" · ")[0]} <em>· {line.split(" · ")[1]}</em></p>)}</div>
        <div className="signal-row"><span className="signal-title">Strong signals</span>{["React", "GraphQL", "WebSockets", "Stripe"].map((signal, index) => <span className={`demo-pop${sigOn(index) ? " on" : ""}`} key={signal}>{signal}</span>)}</div>
      </div>
    </div>
  );
}

const reports = [
  ["Linear", "Product operations", "94%", "#5E6AD2"],
  ["Notion", "Collaborative workspace", "91%", "#E0E0E0"],
  ["Stripe", "Payments infrastructure", "97%", "#635BFF"],
  ["Supabase", "Developer platform", "93%", "#3ECF8E"],
];

const HERO_FALLBACK = "https://images.unsplash.com/photo-1506905925346-21bda4d32df4?auto=format&fit=crop&w=1920&q=70";

export default function LandingPage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const [heroSrc, setHeroSrc] = useState(HERO_FALLBACK);
  useEffect(() => {
    const probe = new Image();
    probe.onload = () => setHeroSrc("/hero.jpg");
    probe.src = "/hero.jpg";
  }, []);
  const start = () => router.push(`/analyze${url ? `?url=${encodeURIComponent(url)}` : ""}`);

  return (
    <main className="landing">
      <nav className="site-nav">
        <a className="brand" href="#top" aria-label="Orbit home"><OrbitLogo />orbit</a>
        <div className="nav-links"><a href="#product">Product</a><a href="#how-it-works">How it works</a><a href="#reports">Reports</a><a href="#pricing">Pricing</a></div>
        <div className="nav-actions"><button className="link-button" onClick={() => router.push("/login")}>Sign in</button><button className="button primary small" onClick={start}>Start analyzing <ArrowRight size={15} /></button></div>
      </nav>

      <section id="top" className="hero-cinema">
        <img className="hero-video" src={heroSrc} alt="" aria-hidden />
        <div className="hero-veil" />
        <div className="hero shell-grid">
          <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .55 }} className="hero-copy hero-glass">
            <div className="eyebrow"><span className="status-dot" /> Software intelligence, made visible</div>
            <h1>Understand any<br /><em>software.</em></h1>
            <p>Orbit autonomously explores SaaS products and turns observable behavior into interactive engineering reports.</p>
            <div className="hero-input">
              <Globe2 size={18} /><input value={url} onChange={(event) => setUrl(event.target.value)} onKeyDown={(event) => event.key === "Enter" && start()} placeholder="https://linear.app" aria-label="Software URL" />
              <button className="button primary" onClick={start}>Analyze <ArrowRight size={16} /></button>
            </div>
            <div className="trust-line"><ShieldCheck size={15} /> Public surfaces only. Evidence-backed by design.</div>
          </motion.div>
          <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .7, delay: .12 }} className="product-window">
            <div className="window-bar"><div className="window-dots"><i /><i /><i /></div><span>orbit / report / linear</span><span className="window-live"><b /> Live analysis</span></div>
            <HeroDemo />
          </motion.div>
        </div>
      </section>

      <section id="product" className="section container">
        <div className="section-heading"><div><span className="eyebrow">Product intelligence</span><h2>See the system behind<br />the interface.</h2></div><p>Orbit makes the observable layers of modern software legible — without guessing, cloning, or hand-waving.</p></div>
        <div className="feature-grid">{features.map(([Icon, title, text], index) => <motion.article initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ delay: index * .05 }} className="feature-card" key={title as string}><span className="feature-icon"><Icon size={19} /></span><h3>{title as string}</h3><p>{text as string}</p><span className="card-arrow"><ArrowRight size={16} /></span></motion.article>)}</div>
      </section>

      <section id="how-it-works" className="section process-section">
        <div className="container"><div className="section-heading centered"><span className="eyebrow">How it works</span><h2>One URL. A clearer picture.</h2></div><div className="process-line"><span /><span /><span /></div><div className="process-grid">
          {[["01", "Paste a URL", "Tell Orbit which public product you want to understand."], ["02", "Explore software", "A controlled browser agent maps pages, flows, and observable signals."], ["03", "Review the report", "Navigate evidence-backed architecture, features, entities, and insights."]].map(([n,t,d]) => <article className="process-card" key={n}><span>{n}</span><h3>{t}</h3><p>{d}</p></article>)}
        </div></div>
      </section>

      <section id="reports" className="section container reports-section"><div className="section-heading"><div><span className="eyebrow">Example intelligence</span><h2>Reports built for<br />technical curiosity.</h2></div><button className="button ghost" onClick={() => router.push("/report/demo")}>Explore demo <ArrowRight size={16} /></button></div><div className="reports-grid">{reports.map(([name, descriptor, score, color]) => <button onClick={() => router.push("/report/demo")} className="example-report" key={name}><div className="report-logo" style={{ background: color as string }}>{(name as string).slice(0,1)}</div><div><strong>{name}</strong><span>{descriptor}</span></div><div className="report-score"><b>{score}</b><span>confidence</span></div><ChevronRight size={17} /></button>)}</div></section>

      <section id="pricing" className="section container pricing"><div className="pricing-copy"><span className="eyebrow">Simple pricing</span><h2>Start with a question.</h2><p>Explore with a free report. Upgrade when software intelligence becomes part of your team's operating system.</p></div><div className="plan-card"><div><span className="plan-label">FOR INDIVIDUALS</span><h3>Free</h3><p>Understand your next product.</p></div><div className="price"><strong>$0</strong><span> / month</span></div><ul><li><Check size={15} /> 3 reports per month</li><li><Check size={15} /> Interactive report viewer</li><li><Check size={15} /> Public URL exploration</li></ul><button className="button primary" onClick={start}>Get started <ArrowRight size={16} /></button></div></section>

      <footer className="footer container"><a className="brand" href="#top"><OrbitLogo />orbit</a><span>© 2026 Orbit Intelligence, Inc.</span><div><a href="#">Documentation</a><a href="#">Privacy</a><a href="#"><Github size={16} /></a></div></footer>
    </main>
  );
}
