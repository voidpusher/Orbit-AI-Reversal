"use client";

import {
  ArrowLeft, Bot, Boxes, Cloud, Code2, Cpu, Database, Download, FileText, Gauge, GitBranch, Globe2,
  Layers3, Loader2, Lock, Network, Plug, Search, Server, ShieldCheck, Sparkles, Star, TriangleAlert, Users, Waypoints,
  Workflow as WorkflowIcon,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { use, useState } from "react";
import { api } from "@/lib/api";
import type { ReportDetail, ReportDocument } from "@/lib/types";
import { ArchitectureDiagram } from "@/components/report/diagrams";
import { AskOrbit } from "@/components/report/AskOrbit";
import { WorkflowStudio } from "@/components/report/WorkflowStudio";
import { ConfidenceGauge } from "@/components/report/primitives";
import { ReportSection } from "@/components/report/ReportSections";
import { RequireAuth } from "@/components/RequireAuth";
import { OrbitLogo } from "@/components/OrbitLogo";
import { downloadText } from "@/lib/download";

const NAV: [React.ComponentType<{ size?: number }>, string][] = [
  [WorkflowIcon, "Workflow Lab"], [Bot, "Ask Orbit"], [Layers3, "Overview"], [Network, "Architecture"], [Waypoints, "User flows"], [Sparkles, "Features"],
  [Boxes, "Entities"], [Users, "Permissions"], [Database, "Database"], [GitBranch, "API"],
  [Globe2, "Tech stack"], [Plug, "Integrations"], [Gauge, "Performance"], [Search, "SEO"],
  [Lock, "Privacy"], [Code2, "Engineering insights"], [Cpu, "Rendering"], [Cloud, "Infrastructure"],
  [Server, "Domain & email"], [ShieldCheck, "Security"],
];

export default function ReportViewer({ params }: { params: Promise<{ id: string }> }) {
  return (
    <RequireAuth>
      <ReportViewerInner params={params} />
    </RequireAuth>
  );
}

function ReportViewerInner({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const qc = useQueryClient();
  const [active, setActive] = useState("Overview");
  const [exportError, setExportError] = useState("");
  const [exporting, setExporting] = useState(false);

  const { data: report, isLoading, error } = useQuery({
    queryKey: ["report", id],
    queryFn: () => api.getReport(id),
  });

  const favorite = useMutation({
    mutationFn: (value: boolean) => api.updateReport(id, { is_favorite: value }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["report", id] }),
  });

  const doExport = async (format: "json" | "markdown") => {
    setExportError("");
    setExporting(true);
    try {
      const result = await api.exportReport(id, format);
      downloadText(result.filename, result.content, format === "json" ? "application/json" : "text/markdown");
    } catch (error) {
      setExportError(error instanceof Error ? error.message : "The export failed. Please try again.");
    } finally {
      setExporting(false);
    }
  };

  if (isLoading) return <ReportSkeleton />;
  if (error || !report)
    return (
      <div className="report-error">
        <TriangleAlert size={22} />
        <h2>Report unavailable</h2>
        <p>{error instanceof Error ? error.message : "This report could not be loaded."}</p>
        <button className="button primary" onClick={() => router.push("/reports")}>Back to reports</button>
      </div>
    );

  const doc = report.document;
  const initial = report.product_name[0]?.toUpperCase() ?? "?";

  return (
    <main className="report-app">
      <aside className="report-sidebar">
        <button className="brand button-reset" onClick={() => router.push("/")}>
          <OrbitLogo />orbit
        </button>
        <button className="crumb" onClick={() => router.push("/reports")}>
          <ArrowLeft size={15} /> Reports
        </button>
        <div className="report-summary-side">
          <span className="linear-logo">{initial}</span>
          <div><b>{report.product_name}</b><small>{doc.meta.host}</small></div>
        </div>
        <nav>
          {NAV.map(([Icon, name]) => (
            <button key={name} className={active === name ? "active" : ""} onClick={() => setActive(name)}>
              <Icon size={16} /> {name}
            </button>
          ))}
        </nav>
        <button className="export-nav" disabled={exporting} onClick={() => doExport("markdown")}>
          <Download size={16} /> Export report
        </button>
      </aside>

      <section className="report-main">
        <header className="report-header">
          <div>
            <span className="eyebrow"><i className="complete-dot" /> Analyzed {new Date(report.published_at).toLocaleDateString()}</span>
            <h1>{active}</h1>
          </div>
          <div className="report-header-actions">
            {active !== "Ask Orbit" && <button className="button ask-orbit-header-button" onClick={() => setActive("Ask Orbit")}><Bot size={15} /> Ask Orbit</button>}
            <button className={`icon-button ${report.is_favorite ? "starred" : ""}`} aria-label="Favorite" onClick={() => favorite.mutate(!report.is_favorite)}>
              <Star size={17} fill={report.is_favorite ? "currentColor" : "none"} />
            </button>
            <button className="button ghost" disabled={exporting} onClick={() => doExport("json")}><FileText size={15} /> JSON</button>
            <button className="button ghost" disabled={exporting} onClick={() => doExport("markdown")}><Download size={15} /> Markdown</button>
          </div>
        </header>
        {exportError && <p className="form-error" role="alert">{exportError}</p>}

        {active === "Ask Orbit" && <AskOrbit reportId={id} productName={report.product_name} document={doc} />}
        {active === "Workflow Lab" && <WorkflowStudio reportId={id} productName={report.product_name} document={doc} />}
        {active === "Overview" && <Overview report={report} setActive={setActive} />}
        {!["Overview", "Ask Orbit", "Workflow Lab"].includes(active) && <ReportSection active={active} doc={doc} />}
      </section>
    </main>
  );
}

function Overview({ report, setActive }: { report: ReportDetail; setActive: (s: string) => void }) {
  const doc = report.document;
  return (
    <>
      <section className="report-hero-card">
        <div className="report-intro">
          <h2>{doc.overview.headline}</h2>
          <p>{doc.overview.summary}</p>
          <div className="hero-tags">
            <span><Search size={14} /> {doc.meta.pages_explored} pages explored</span>
            <span><FileText size={14} /> {doc.meta.evidence_count} evidence points</span>
            <span><Sparkles size={14} /> {doc.meta.access_limited ? "Features unavailable" : `${doc.meta.features_count} features observed`}</span>
          </div>
        </div>
        <ConfidenceGauge score={doc.meta.overall_confidence} band={doc.meta.confidence_band} />
      </section>

      {doc.meta.access_limited && (
        <section className="access-limited-banner">
          <TriangleAlert size={18} />
          <div>
            <b>Target blocked architecture inspection</b>
            <p>
              Orbit received HTTP {doc.meta.access_statuses?.join(", ") || "access-denied"} responses.
              Confidence is capped because product routes, APIs, and runtime network calls were not observable.
            </p>
          </div>
        </section>
      )}

      <section className="metrics-row">
        {doc.overview.metrics.map((m) => (
          <article className="metric" key={m.label}>
            <strong>{m.value}</strong>
            <div><b>{m.label}</b><small>{m.sub}</small></div>
          </article>
        ))}
      </section>

      <section className="content-grid">
        <article className="content-card architecture">
          <div className="card-title">
            <div><h3>Architecture</h3></div>
            <button onClick={() => setActive("Architecture")}>Explore →</button>
          </div>
          <ArchitectureDiagram arch={doc.architecture} />
          <p className="evidence-note"><ShieldCheck size={14} /> {doc.architecture.summary}</p>
        </article>
        <article className="content-card signals">
          <div className="card-title">
            <div><h3>Technology profile</h3></div>
            <button onClick={() => setActive("Tech stack")}>View all →</button>
          </div>
          {doc.tech_stack.items.slice(0, 5).map((tech) => (
            <div className="signal-item" key={tech.name}>
              <span>{tech.name[0]}</span>
              <div><b>{tech.name}</b><small>{tech.category}</small></div>
              <em>{tech.confidence}%</em>
            </div>
          ))}
          {doc.tech_stack.items.length === 0 && <p className="empty-note">No third-party technologies were clearly observed.</p>}
        </article>
      </section>

      <section className="insight-section">
        <div className="card-title">
          <div><h3>Engineering insights</h3></div>
          <button onClick={() => setActive("Engineering insights")}>All insights →</button>
        </div>
        <div className="insight-grid">
          {doc.insights.items.slice(0, 3).map((insight) => (
            <article className="insight" key={insight.title}>
              <span><Sparkles size={17} /></span>
              <div>
                <h4>{insight.title}</h4>
                <p>{insight.detail}</p>
                <b>{insight.confidence}% confidence · {insight.classification}</b>
              </div>
            </article>
          ))}
        </div>
      </section>
    </>
  );
}

function ReportSkeleton() {
  return (
    <main className="report-app">
      <aside className="report-sidebar"><div className="skeleton-brand" /><div className="skeleton-nav">{Array.from({ length: 8 }).map((_, i) => <span key={i} className="skeleton-line" />)}</div></aside>
      <section className="report-main">
        <div className="report-loading"><Loader2 size={22} className="spin" /> Loading report…</div>
      </section>
    </main>
  );
}
