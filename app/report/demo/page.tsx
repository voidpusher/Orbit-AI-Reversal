"use client";

import {
  ArrowLeft,
  Bot,
  Boxes,
  Braces,
  ChevronRight,
  CircleUserRound,
  Database,
  Download,
  GitBranch,
  LayoutDashboard,
  Lightbulb,
  LockKeyhole,
  Network,
  ShieldCheck,
  Sparkles,
  Workflow,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArchitectureWorkspace } from "@/components/report/ArchitectureWorkspace";
import { AskOrbit } from "@/components/report/AskOrbit";
import { ConfidenceChip, ConfidenceGauge } from "@/components/report/primitives";
import { OrbitLogo } from "@/components/OrbitLogo";
import type { ReportDocument } from "@/lib/types";

const NAV_ITEMS = [
  ["Ask Orbit", Bot],
  ["Overview", LayoutDashboard],
  ["Architecture", Network],
  ["User flows", Workflow],
  ["Features", Sparkles],
  ["Entities", Boxes],
  ["Permissions", LockKeyhole],
  ["Database", Database],
  ["API", Braces],
  ["Tech stack", GitBranch],
  ["Insights", Lightbulb],
] as const;

const DEMO_ARCHITECTURE: ReportDocument["architecture"] = {
  summary:
    "A browser-delivered React application behind an edge network, with a GraphQL API, realtime updates, asynchronous workers, and managed data services.",
  confidence: 86,
  reasoning:
    "The model combines public network requests, loaded bundles, route behavior, response headers, and third-party SDK signatures. Server-side components are inferred only when the client contract or request flow requires them.",
  evidence: [
    "React and Next.js chunks are loaded from the application origin.",
    "GraphQL requests target /api/graphql and carry bearer authorization.",
    "A websocket upgrade is observed at /realtime.",
    "Stripe and analytics SDKs are present in production bundles.",
  ],
  edges: [],
  nodes: [
    {
      id: "browser",
      label: "Browser client",
      kind: "client",
      role: "User-facing runtime",
      confidence: 100,
      classification: "observed",
      responsibilities: ["Render the interface", "Manage navigation", "Send authenticated requests"],
      evidence: ["https://linear.app", "HTML document and JavaScript execution observed"],
    },
    {
      id: "edge",
      label: "Cloudflare edge",
      kind: "edge",
      role: "Delivery and traffic boundary",
      confidence: 96,
      classification: "observed",
      responsibilities: ["TLS termination", "Static asset caching", "Request routing"],
      evidence: ["Response header: server=cloudflare", "CF-Ray header present"],
    },
    {
      id: "frontend",
      label: "React frontend",
      kind: "frontend",
      role: "Application shell",
      confidence: 98,
      classification: "observed",
      responsibilities: ["Client routing", "Feature composition", "Optimistic UI state"],
      evidence: ["/_next/static/chunks/app.js", "React runtime markers found"],
    },
    {
      id: "api",
      label: "GraphQL API",
      kind: "api",
      role: "Product service boundary",
      confidence: 93,
      classification: "observed",
      responsibilities: ["Resolve product queries", "Authorize mutations", "Shape client contracts"],
      evidence: ["POST https://linear.app/api/graphql", "application/json GraphQL response"],
    },
    {
      id: "realtime",
      label: "Realtime gateway",
      kind: "realtime",
      role: "Live synchronization",
      confidence: 91,
      classification: "observed",
      responsibilities: ["Fan out workspace changes", "Maintain presence", "Reconnect clients"],
      evidence: ["wss://linear.app/realtime", "HTTP 101 protocol upgrade"],
    },
    {
      id: "worker",
      label: "Background workers",
      kind: "worker",
      role: "Asynchronous execution",
      confidence: 69,
      classification: "inferred",
      responsibilities: ["Process imports", "Generate exports", "Dispatch notifications"],
      evidence: ["Import operation returns a job identifier", "Export status is polled asynchronously"],
    },
    {
      id: "database",
      label: "PostgreSQL",
      kind: "database",
      role: "System of record",
      confidence: 68,
      classification: "inferred",
      responsibilities: ["Persist workspace state", "Maintain relational integrity", "Support transactional writes"],
      evidence: ["Relational identifiers and cursor pagination observed in API responses"],
    },
    {
      id: "storage",
      label: "Object storage",
      kind: "storage",
      role: "Binary asset storage",
      confidence: 88,
      classification: "observed",
      responsibilities: ["Store attachments", "Serve signed downloads", "Retain exports"],
      evidence: ["Signed object URLs observed on attachment downloads"],
    },
    {
      id: "auth",
      label: "Identity provider",
      kind: "auth",
      role: "Authentication service",
      confidence: 84,
      classification: "observed",
      responsibilities: ["Authenticate users", "Issue sessions", "Handle OAuth callbacks"],
      evidence: ["/oauth/callback route", "Session cookie and bearer token observed"],
    },
    {
      id: "stripe",
      label: "Stripe",
      kind: "payment",
      role: "Billing provider",
      confidence: 95,
      classification: "observed",
      responsibilities: ["Collect payment details", "Manage subscriptions"],
      evidence: ["https://js.stripe.com/v3", "Stripe publishable key pattern"],
    },
    {
      id: "analytics",
      label: "Product analytics",
      kind: "analytics",
      role: "Behavior telemetry",
      confidence: 89,
      classification: "observed",
      responsibilities: ["Capture product events", "Measure journeys"],
      evidence: ["Analytics event batch observed after navigation"],
    },
  ],
  connections: [
    { from: "browser", to: "edge", label: "Page and asset requests", protocol: "HTTPS", confidence: 100, classification: "observed", evidence: ["GET https://linear.app"] },
    { from: "edge", to: "frontend", label: "Application delivery", protocol: "HTTPS", confidence: 97, classification: "observed", evidence: ["Cached Next.js assets returned through edge"] },
    { from: "frontend", to: "api", label: "Queries and mutations", protocol: "GraphQL/HTTPS", confidence: 94, classification: "observed", evidence: ["POST /api/graphql"] },
    { from: "frontend", to: "realtime", label: "Workspace events", protocol: "WebSocket", confidence: 91, classification: "observed", evidence: ["wss://linear.app/realtime"] },
    { from: "frontend", to: "auth", label: "Sign-in and session", protocol: "OAuth 2.0", confidence: 84, classification: "observed", evidence: ["/oauth/callback"] },
    { from: "api", to: "worker", label: "Enqueue long-running work", protocol: "Job queue", confidence: 69, classification: "inferred", evidence: ["202 response includes jobId"] },
    { from: "api", to: "database", label: "Transactional reads and writes", protocol: "SQL", confidence: 68, classification: "inferred", evidence: ["Relational response shapes and transactional mutation behavior"] },
    { from: "api", to: "storage", label: "Attachment metadata", protocol: "HTTPS", confidence: 86, classification: "observed", evidence: ["Signed attachment URL returned by API"] },
    { from: "worker", to: "storage", label: "Export artifacts", protocol: "Object API", confidence: 67, classification: "inferred", evidence: ["Completed exports resolve to signed object URLs"] },
    { from: "frontend", to: "stripe", label: "Checkout session", protocol: "Stripe.js", confidence: 95, classification: "observed", evidence: ["Stripe.js loaded on billing route"] },
    { from: "frontend", to: "analytics", label: "Product events", protocol: "HTTPS", confidence: 89, classification: "observed", evidence: ["Analytics batch request"] },
  ],
  layers: [
    { name: "Client", node_ids: ["browser", "frontend"] },
    { name: "Delivery", node_ids: ["edge"] },
    { name: "Application", node_ids: ["api", "realtime", "worker"] },
    { name: "Data", node_ids: ["database", "storage"] },
    { name: "External services", node_ids: ["auth", "stripe", "analytics"] },
  ],
  request_flows: [
    { name: "Page delivery", steps: ["browser", "edge", "frontend"], transport: "HTTPS", confidence: 98, classification: "observed", evidence: ["Initial document and chunk waterfall"] },
    { name: "Issue query", steps: ["browser", "frontend", "api", "database"], transport: "GraphQL + SQL", confidence: 82, classification: "inferred", evidence: ["GraphQL request and relational response shape"] },
    { name: "Realtime update", steps: ["browser", "frontend", "realtime"], transport: "WebSocket", confidence: 91, classification: "observed", evidence: ["Live websocket messages"] },
    { name: "Export job", steps: ["frontend", "api", "worker", "storage"], transport: "HTTPS + queue", confidence: 68, classification: "inferred", evidence: ["Asynchronous export lifecycle"] },
    { name: "Checkout", steps: ["frontend", "stripe", "api"], transport: "Stripe.js + HTTPS", confidence: 90, classification: "observed", evidence: ["Billing journey network trace"] },
  ],
  trust_boundaries: [
    { name: "Public to authenticated application", between: ["edge", "api"], implication: "Session validation and authorization are required before product data is returned.", confidence: 91, evidence: ["Bearer authorization and session cookie observed"] },
    { name: "Application to managed providers", between: ["api", "stripe"], implication: "Provider credentials, webhooks, and signed payloads cross an external trust boundary.", confidence: 84, evidence: ["Stripe integration surface detected"] },
  ],
  patterns: [
    { title: "Edge-delivered SPA", detail: "A cached application shell calls a separate product API after hydration.", confidence: 94, classification: "observed", evidence: ["Next.js assets and post-load API requests"] },
    { title: "Event-driven background work", detail: "Long-running imports and exports appear to be handed off to asynchronous workers.", confidence: 69, classification: "inferred", evidence: ["Job identifiers and status polling"] },
  ],
  unknowns: [
    "The exact queue technology is not exposed by public evidence.",
    "PostgreSQL is inferred from relational behavior; the database vendor is not directly observable.",
  ],
};

export default function DemoReportPage() {
  const router = useRouter();
  const [active, setActive] = useState("Overview");

  return (
    <div className="report-app">
      <aside className="report-sidebar">
        <button className="brand" onClick={() => router.push("/")} aria-label="Go to Orbit home">
          <OrbitLogo />
          <b>Orbit</b>
        </button>
        <button className="crumb" onClick={() => router.push("/dashboard")}>
          <ArrowLeft size={13} /> All reports
        </button>
        <div className="report-summary-side">
          <span className="linear-logo">L</span>
          <div><b>Linear</b><small>linear.app</small></div>
          <ChevronRight size={13} />
        </div>
        <nav aria-label="Report sections">
          {NAV_ITEMS.map(([label, Icon]) => (
            <button key={label} className={active === label ? "active" : ""} onClick={() => setActive(label)}>
              <Icon size={14} /> {label}
            </button>
          ))}
          <button className="export-nav"><Download size={14} /> Export report</button>
        </nav>
      </aside>

      <main className="report-main">
        <header className="report-header">
          <div><span className="eyebrow">PRODUCT RECONSTRUCTION</span><h1>Linear</h1></div>
          <div className="report-header-actions">
            <button className="icon-button" aria-label="Report account"><CircleUserRound size={16} /></button>
            <button className="button secondary"><Download size={14} /> Export</button>
          </div>
        </header>

        {active === "Ask Orbit" ? (
          <AskOrbit productName="Linear" architecture={DEMO_ARCHITECTURE} />
        ) : active === "Architecture" ? (
          <DemoArchitecture />
        ) : (
          <DemoOverview onOpenArchitecture={() => setActive("Architecture")} />
        )}
      </main>
    </div>
  );
}

function DemoArchitecture() {
  return (
    <section className="section-panel">
      <div className="section-head">
        <div>
          <span className="eyebrow">SYSTEM MODEL</span>
          <h2>Reconstructed architecture</h2>
          <p>Explore the engineering model, isolate a journey or evidence class, and inspect why every component and connection exists.</p>
        </div>
        <ConfidenceChip score={DEMO_ARCHITECTURE.confidence} />
      </div>
      <div className="architecture-metrics">
        <article><b>{DEMO_ARCHITECTURE.nodes.length}</b><span>Components</span></article>
        <article><b>{DEMO_ARCHITECTURE.connections?.length ?? 0}</b><span>Connections</span></article>
        <article><b>{DEMO_ARCHITECTURE.request_flows?.length ?? 0}</b><span>Journeys</span></article>
        <article><b>{DEMO_ARCHITECTURE.nodes.filter((node) => node.classification === "observed").length}</b><span>Observed nodes</span></article>
      </div>
      <ArchitectureWorkspace arch={DEMO_ARCHITECTURE} productName="Linear" />
    </section>
  );
}

function DemoOverview({ onOpenArchitecture }: { onOpenArchitecture: () => void }) {
  return (
    <>
      <section className="report-hero-card">
        <div className="report-intro">
          <span className="eyebrow">EXECUTIVE SUMMARY</span>
          <h2>A fast, collaboration-first issue tracking product built around keyboard-driven workflows and realtime team state.</h2>
          <p>Reconstructed from public application behavior, network evidence, assets, and route structure.</p>
          <div className="hero-tags"><span><ShieldCheck size={12} /> Evidence-backed</span><span><Network size={12} /> 11 architecture components</span></div>
        </div>
        <ConfidenceGauge score={86} band="Strong evidence" />
      </section>

      <div className="metrics-row">
        <Metric value="42" label="Features found" sub="Across 8 workflows" />
        <Metric value="11" label="System components" sub="9 observed, 2 inferred" />
        <Metric value="16" label="Core entities" sub="With relationships" />
        <Metric value="94" label="Evidence records" sub="Across 12 pages" />
      </div>

      <div className="content-grid">
        <section className="content-card">
          <div className="card-title">
            <div><span className="eyebrow">SYSTEM SHAPE</span><h3>Observed architecture</h3></div>
            <button onClick={onOpenArchitecture}>Explore model <ChevronRight size={13} /></button>
          </div>
          <div className="arch-canvas" aria-label="Architecture preview">
            <div className="arch-node browser"><span>Browser</span><b>Observed</b></div>
            <div className="arch-node frontend"><span>React frontend</span><b>High</b></div>
            <div className="arch-node api"><span>GraphQL API</span><b>High</b></div>
            <div className="arch-node db"><span>Data services</span><b>Medium</b></div>
            <i className="arch-line l1" /><i className="arch-line l2" /><i className="arch-line l3" />
          </div>
          <p className="evidence-note"><ShieldCheck size={13} /> Select Architecture to open the zoomable evidence model.</p>
        </section>

        <section className="content-card signals">
          <div className="card-title"><div><span className="eyebrow">DETECTED</span><h3>Strong signals</h3></div></div>
          {[["N", "Next.js", "Frontend framework", "98%"], ["G", "GraphQL", "API contract", "93%"], ["W", "WebSocket", "Realtime transport", "91%"], ["S", "Stripe", "Billing provider", "95%"]].map(([mark, name, type, score]) => (
            <div className="signal-item" key={name}><span>{mark}</span><div><b>{name}</b><small>{type}</small></div><em>{score}</em></div>
          ))}
        </section>
      </div>

      <section className="insight-section">
        <div className="card-title"><div><span className="eyebrow">ENGINEERING READOUT</span><h3>What the evidence suggests</h3></div></div>
        <div className="insight-grid">
          <Insight icon={<Workflow size={14} />} title="Realtime collaboration" detail="A dedicated websocket path maintains live workspace state alongside API traffic." score="91%" />
          <Insight icon={<Database size={14} />} title="Asynchronous workloads" detail="Import and export flows return job identifiers, implying a worker and queue boundary." score="69%" />
          <Insight icon={<ShieldCheck size={14} />} title="Clear trust boundaries" detail="Authentication, billing, and storage cross explicit external provider boundaries." score="84%" />
        </div>
      </section>
    </>
  );
}

function Metric({ value, label, sub }: { value: string; label: string; sub: string }) {
  return <article className="metric"><strong>{value}</strong><div><b>{label}</b><small>{sub}</small></div></article>;
}

function Insight({ icon, title, detail, score }: { icon: React.ReactNode; title: string; detail: string; score: string }) {
  return <article className="insight"><span>{icon}</span><div><h4>{title}</h4><p>{detail}</p><b>{score} confidence</b></div></article>;
}
