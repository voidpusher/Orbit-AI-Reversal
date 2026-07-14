"use client";

import { ArrowRight, Bot, Boxes, Braces, Check, ChevronRight, CirclePlay, Code2, Database, Eye, Github, Globe2, Layers3, Network, Search, ShieldCheck, Sparkles, Waypoints } from "lucide-react";
import { motion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useState } from "react";

const features = [
  [Eye, "Feature detection", "Map product capabilities from observable behavior."],
  [Network, "Architecture mapping", "Turn web signals into an evidence-backed system view."],
  [Waypoints, "User flow discovery", "Follow key journeys from entry point to outcome."],
  [Braces, "API detection", "Surface public request patterns and integration boundaries."],
  [Database, "Database inference", "Explore likely entities and relationships with confidence."],
  [Code2, "Engineering insights", "Understand the choices behind a product’s experience."],
];

const reports = [
  ["Linear", "Product operations", "94%", "#5E6AD2"],
  ["Notion", "Collaborative workspace", "91%", "#E0E0E0"],
  ["Stripe", "Payments infrastructure", "97%", "#635BFF"],
  ["Supabase", "Developer platform", "93%", "#3ECF8E"],
];

export default function LandingPage() {
  const router = useRouter();
  const [url, setUrl] = useState("");
  const start = () => router.push(`/analyze${url ? `?url=${encodeURIComponent(url)}` : ""}`);

  return (
    <main>
      <nav className="site-nav">
        <a className="brand" href="#top" aria-label="Orbit home"><span className="brand-mark"><span /></span>orbit</a>
        <div className="nav-links"><a href="#product">Product</a><a href="#how-it-works">How it works</a><a href="#reports">Reports</a><a href="#pricing">Pricing</a></div>
        <div className="nav-actions"><button className="link-button" onClick={() => router.push("/login")}>Sign in</button><button className="button primary small" onClick={start}>Start analyzing <ArrowRight size={15} /></button></div>
      </nav>

      <section id="top" className="hero shell-grid">
        <div className="orb orb-one" /><div className="orb orb-two" />
        <motion.div initial={{ opacity: 0, y: 18 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: .55 }} className="hero-copy">
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
          <div className="window-bar"><div className="window-dots"><i /><i /><i /></div><span>orbit / report / linear</span><span className="window-live"><b /> Analysis complete</span></div>
          <div className="window-body">
            <aside className="mini-sidebar"><span className="mini-logo">o</span><span className="mini-active"><Layers3 size={16} /></span><span><Network size={16} /></span><span><Database size={16} /></span><span><Boxes size={16} /></span></aside>
            <div className="report-preview">
              <div className="preview-top"><div><span className="report-kicker">REPORT OVERVIEW</span><h3>Linear</h3></div><span className="confidence">94% confidence</span></div>
              <div className="preview-metrics"><div><strong>24</strong><span>pages explored</span></div><div><strong>17</strong><span>features found</span></div><div><strong>126</strong><span>evidence points</span></div></div>
              <div className="architecture-card"><div className="card-heading"><span>Observed architecture</span><ChevronRight size={15} /></div><div className="node-flow"><b><Globe2 size={15} /> Browser</b><i /><b><Code2 size={15} /> Frontend</b><i /><b><Network size={15} /> API</b></div><div className="node-flow lower"><b><Database size={15} /> Postgres</b><i /><b><Sparkles size={15} /> Realtime</b></div></div>
              <div className="signal-row"><span className="signal-title">Strong signals</span><span>React</span><span>GraphQL</span><span>WebSockets</span><span>Stripe</span></div>
            </div>
          </div>
        </motion.div>
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

      <footer className="footer container"><a className="brand" href="#top"><span className="brand-mark"><span /></span>orbit</a><span>© 2026 Orbit Intelligence, Inc.</span><div><a href="#">Documentation</a><a href="#">Privacy</a><a href="#"><Github size={16} /></a></div></footer>
    </main>
  );
}
