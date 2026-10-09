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
import { AskOrbit } from "@/components/report/AskOrbit";
import { WorkflowStudio } from "@/components/report/WorkflowStudio";
import { ConfidenceGauge } from "@/components/report/primitives";
import { OrbitLogo } from "@/components/OrbitLogo";
import { DEMO_COMPILED_WORKFLOW, DEMO_REPORT } from "@/lib/demo-report";
import { ReportSection } from "@/components/report/ReportSections";
import { downloadText } from "@/lib/download";

const NAV_ITEMS = [
  ["Workflow Lab", Workflow],
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

export default function DemoReportPage() {
  const router = useRouter();
  const [active, setActive] = useState("Overview");
  const exportDemo = () => downloadText("orbit-linear-demo.json", JSON.stringify({ sample: true, document: DEMO_REPORT }, null, 2), "application/json");

  return (
    <div className="report-app">
      <aside className="report-sidebar">
        <button className="brand button-reset" onClick={() => router.push("/")} aria-label="Go to Orbit home">
          <OrbitLogo />
          <b>Orbit</b>
        </button>
        <button className="crumb" onClick={() => router.push("/reports")}>
          <ArrowLeft size={13} /> All reports
        </button>
        <div className="report-summary-side">
          <span className="linear-logo">L</span>
          <div><b>Linear</b><small>linear.app</small></div>
          <ChevronRight size={13} />
        </div>
        <nav aria-label="Report sections">
          {NAV_ITEMS.map(([label, Icon]) => (
            <button key={label} className={active === label ? "active" : ""} onClick={() => setActive(label)} aria-current={active === label ? "page" : undefined}>
              <Icon size={14} /> {label}
            </button>
          ))}
          <button className="export-nav" onClick={exportDemo}><Download size={14} /> Export report</button>
        </nav>
      </aside>

      <main className="report-main">
        <header className="report-header">
          <div><h1>{active === "Overview" ? "Linear" : active}</h1></div>
          <div className="report-header-actions">
            <button className="icon-button" aria-label="Report account" onClick={() => router.push("/settings")}><CircleUserRound size={16} /></button>
            <button className="button secondary" onClick={exportDemo}><Download size={14} /> Export</button>
          </div>
        </header>

        <p className="demo-report-notice">Sample report · Illustrative data, not a verified audit of Linear.</p>
        {active === "Workflow Lab" ? (
          <WorkflowStudio reportId="demo" productName="Linear" document={DEMO_REPORT} demoResult={DEMO_COMPILED_WORKFLOW} />
        ) : active === "Ask Orbit" ? (
          <AskOrbit productName="Linear" document={DEMO_REPORT} />
        ) : active === "Overview" ? (
          <DemoOverview onOpenArchitecture={() => setActive("Architecture")} />
        ) : (
          <ReportSection active={active} doc={DEMO_REPORT} />
        )}
      </main>
    </div>
  );
}

function DemoOverview({ onOpenArchitecture }: { onOpenArchitecture: () => void }) {
  return (
    <>
      <section className="report-hero-card">
        <div className="report-intro">
          <h2>A fast, collaboration-first issue tracking product built around keyboard-driven workflows and realtime team state.</h2>
          <p>Reconstructed from public application behavior, network evidence, assets, and route structure.</p>
        </div>
        <ConfidenceGauge score={86} band="Strong evidence" />
      </section>

      <div className="metrics-row">
        {DEMO_REPORT.overview.metrics.map((metric) => <Metric key={metric.label} value={metric.value} label={metric.label} sub={metric.sub} />)}
      </div>

      <div className="content-grid">
        <section className="content-card">
          <div className="card-title">
            <div><h3>Architecture</h3></div>
            <button onClick={onOpenArchitecture}>Explore model <ChevronRight size={13} /></button>
          </div>
          <div className="arch-canvas" aria-label="Architecture preview">
            <div className="arch-node browser"><span>Browser</span><b>Observed</b></div>
            <div className="arch-node frontend"><span>React frontend</span><b>High</b></div>
            <div className="arch-node api"><span>GraphQL API</span><b>High</b></div>
            <div className="arch-node db"><span>Data services</span><b>Medium</b></div>
            <i className="arch-line l1" /><i className="arch-line l2" /><i className="arch-line l3" />
          </div>
        </section>

        <section className="content-card signals">
          <div className="card-title"><div><h3>Technology signals</h3></div></div>
          {[["N", "Next.js", "Frontend framework", "98%"], ["G", "GraphQL", "API contract", "93%"], ["W", "WebSocket", "Realtime transport", "91%"], ["S", "Stripe", "Billing provider", "95%"]].map(([mark, name, type, score]) => (
            <div className="signal-item" key={name}><span>{mark}</span><div><b>{name}</b><small>{type}</small></div><em>{score}</em></div>
          ))}
        </section>
      </div>

      <section className="insight-section">
        <div className="card-title"><div><h3>Engineering insights</h3></div></div>
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
