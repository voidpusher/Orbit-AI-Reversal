"use client";

import { ArrowRight, ArrowUpRight, Braces, Code2, Database, Globe2, Layers3, Network, Waypoints } from "lucide-react";
import { motion, useReducedMotion } from "framer-motion";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { OrbitLogo } from "@/components/OrbitLogo";

const capabilities = [
  [Network, "Architecture, uncovered.", "Explore an interactive model of the product’s visible systems, services, and connections."],
  [Waypoints, "Follow every signal.", "Reconstruct journeys from captured behaviour and connect each step to its evidence."],
  [Braces, "A conversation with context.", "Ask your report a question. Get an explanation with citations and labelled uncertainty."],
] as const;

export default function LandingPage() {
  const router = useRouter();
  const reduced = useReducedMotion();
  const [url, setUrl] = useState("");
  const start = () => router.push(`/analyze${url.trim() ? `?url=${encodeURIComponent(url.trim())}` : ""}`);

  return (
    <main className="landing atelier-landing">
      <section id="top" className="landscape-hero">
        <img className="landscape-art" src="/orbit-landscape.webp" alt="" aria-hidden="true" fetchPriority="high" />
        <div className="landscape-wash" />
        <div className="landscape-grain" />
        <nav className="atelier-nav" aria-label="Main navigation">
          <a className="brand nav-glass" href="#top"><OrbitLogo />orbit</a>
          <div className="atelier-nav-links nav-glass"><a href="#product">The product</a><a href="#how-it-works">How it works</a><a href="#reports">Explore</a></div>
          <button className="nav-glass nav-login" onClick={() => router.push("/login")}>Your workspace <ArrowUpRight size={16} /></button>
        </nav>
        <motion.div className="landscape-copy" initial={reduced ? false : { opacity:0,y:16 }} animate={{ opacity:1,y:0 }} transition={{ duration:.7,ease:"easeOut" }}>
          <h1>There’s a world<br />beneath the <em>interface.</em></h1>
          <p>Discover the architecture, workflows, and decisions<br className="desktop-break" /> behind the products you’re curious about.</p>
          <form className="landscape-command" onSubmit={(event) => { event.preventDefault(); start(); }}>
            <Globe2 size={17} /><input aria-label="Product URL" placeholder="Enter a product URL" value={url} onChange={(event) => setUrl(event.target.value)} />
            <button type="submit">Explore <ArrowUpRight size={17} /></button>
          </form>
          <button className="landscape-demo" onClick={() => router.push("/report/demo")}>Take a look inside <ArrowRight size={14} /></button>
        </motion.div>
      </section>

      <section className="atelier-intro container" id="product">
        <div className="atelier-heading"><h2>Software has a story.<br /><em>Learn how it works.</em></h2><p>Orbit follows observable signals and turns them into something you can explore. Every connection has context. Every inference is marked.</p></div>
        <div className="atelier-capabilities">{capabilities.map(([Icon,title,description],index) => <motion.article key={title} initial={reduced ? false : {opacity:0,y:18}} whileInView={{opacity:1,y:0}} viewport={{once:true}} transition={{duration:.45,delay:index*.08}}><Icon size={23} strokeWidth={1.3} /><h3>{title}</h3><p>{description}</p></motion.article>)}</div>
      </section>

      <section className="atelier-product container" id="reports">
        <div className="atelier-product-layout">
          <div className="atelier-product-copy"><h2>A different lens<br />on every product.</h2><p>Move from a high-level view to the evidence behind it. Explore the system, inspect the journey, or ask Orbit to connect the dots.</p><button className="button primary" onClick={() => router.push("/report/demo")}>Open the interactive demo <ArrowUpRight size={16} /></button></div>
          <div className="atelier-report-preview">
            <div className="preview-chrome"><OrbitLogo /><span>orbit</span><span className="preview-live">Demo</span></div>
            <div className="preview-report-heading"><h3>From interface<br />to understanding.</h3></div>
            <div className="preview-system-map"><svg viewBox="0 0 500 230" aria-hidden="true"><path d="M108 115C145 115 145 65 216 65M283 65C350 65 350 115 398 115M250 87V165" /></svg><div className="preview-node node-browser"><Globe2 size={16} /><span>Browser</span></div><div className="preview-node node-frontend"><Code2 size={16} /><span>Frontend</span></div><div className="preview-node node-api"><Network size={16} /><span>API layer</span></div><div className="preview-node node-data"><Database size={16} /><span>Data model</span></div></div>
            <div className="preview-tab-row"><span><Layers3 size={12} /> Architecture</span><span><Waypoints size={12} /> Workflows</span><span><Braces size={12} /> Ask Orbit</span></div>
          </div>
        </div>
      </section>

      <section className="atelier-process container" id="how-it-works"><h2>One question.<br /><em>A deeper understanding.</em></h2><div className="atelier-steps">{[["Choose a product","Start with a public URL, or import an authorized browser capture."],["Connect the evidence","Orbit maps pages, request patterns, journeys, and technology signals."],["Explore what’s underneath","Inspect architecture, interrogate findings, and compile supported workflows."]].map(([title,copy]) => <article key={title}><h3>{title}</h3><p>{copy}</p></article>)}</div></section>

      <section className="atelier-final"><div className="landscape-grain" /><h2>What will you<br /><em>discover next?</em></h2><button className="button primary" onClick={start}>Start exploring <ArrowUpRight size={17} /></button></section>
      <footer className="atelier-footer container"><a className="brand" href="#top"><OrbitLogo />orbit</a><button onClick={() => router.push("/login")}>Open workspace <ArrowUpRight size={14} /></button></footer>
    </main>
  );
}
