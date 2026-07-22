"use client";

import {
  ArrowLeft, Boxes, Cloud, Code2, Cpu, Database, Download, FileText, Gauge, GitBranch, Globe2,
  Layers3, Loader2, Lock, Network, Plug, Search, Server, ShieldCheck, Sparkles, Star, TriangleAlert, Users, Waypoints,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { use, useState } from "react";
import { api } from "@/lib/api";
import type { ReportDetail, ReportDocument } from "@/lib/types";
import { ArchitectureDiagram, ERDiagram, FlowDiagram } from "@/components/report/diagrams";
import { ClassTag, ConfidenceChip, EvidenceList, ReasoningNote, SectionHead, UnableToDetermine } from "@/components/report/primitives";
import { FindingsList, GradeBadge, MetricsStrip } from "@/components/report/findings";
import { RequireAuth } from "@/components/RequireAuth";
import { OrbitLogo } from "@/components/OrbitLogo";

const NAV: [React.ComponentType<{ size?: number }>, string][] = [
  [Layers3, "Overview"], [Network, "Architecture"], [Waypoints, "User flows"], [Sparkles, "Features"],
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

  const { data: report, isLoading, error } = useQuery({
    queryKey: ["report", id],
    queryFn: () => api.getReport(id),
  });

  const favorite = useMutation({
    mutationFn: (value: boolean) => api.updateReport(id, { is_favorite: value }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["report", id] }),
  });

  const doExport = async (format: "json" | "markdown") => {
    const result = await api.exportReport(id, format);
    const blob = new Blob([result.content], { type: format === "json" ? "application/json" : "text/markdown" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = result.filename;
    anchor.click();
    URL.revokeObjectURL(url);
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
        <button className="export-nav" onClick={() => doExport("markdown")}>
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
            <button className={`icon-button ${report.is_favorite ? "starred" : ""}`} aria-label="Favorite" onClick={() => favorite.mutate(!report.is_favorite)}>
              <Star size={17} fill={report.is_favorite ? "currentColor" : "none"} />
            </button>
            <button className="button ghost" onClick={() => doExport("json")}><FileText size={15} /> JSON</button>
            <button className="button ghost" onClick={() => doExport("markdown")}><Download size={15} /> Markdown</button>
          </div>
        </header>

        {active === "Overview" && <Overview report={report} setActive={setActive} />}
        {active === "Architecture" && <ArchitectureSection doc={doc} />}
        {active === "User flows" && <FlowsSection doc={doc} />}
        {active === "Features" && <FeaturesSection doc={doc} />}
        {active === "Entities" && <EntitiesSection doc={doc} />}
        {active === "Permissions" && <PermissionsSection doc={doc} />}
        {active === "Database" && <DatabaseSection doc={doc} />}
        {active === "API" && <ApiSection doc={doc} />}
        {active === "Tech stack" && <TechSection doc={doc} />}
        {active === "Integrations" && <IntegrationsSection doc={doc} />}
        {active === "Performance" && <GradedSectionView eyebrow="Delivery & speed" title="Performance" section={doc.performance} />}
        {active === "SEO" && <GradedSectionView eyebrow="Discoverability" title="SEO & metadata" section={doc.seo} />}
        {active === "Privacy" && <GradedSectionView eyebrow="Data & trackers" title="Privacy" section={doc.privacy} />}
        {active === "Engineering insights" && <InsightsSection doc={doc} />}
        {active === "Rendering" && <RenderingSectionView doc={doc} />}
        {active === "Infrastructure" && <InfraSection doc={doc} />}
        {active === "Domain & email" && <GradedSectionView eyebrow="DNS, email & disclosure" title="Domain & email" section={doc.domain} />}
        {active === "Security" && <SecuritySection doc={doc} />}
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
          <span className="eyebrow">Software intelligence report</span>
          <h2>{doc.overview.headline}</h2>
          <p>{doc.overview.summary}</p>
          <div className="hero-tags">
            <span><Search size={14} /> {doc.meta.pages_explored} pages explored</span>
            <span><FileText size={14} /> {doc.meta.evidence_count} evidence points</span>
            <span><Sparkles size={14} /> {doc.meta.access_limited ? "Features unavailable" : `${doc.meta.features_count} features observed`}</span>
          </div>
        </div>
        <div className="overall-score">
          <div><b>{doc.meta.overall_confidence}</b><small>overall confidence</small></div>
          <span>{doc.meta.confidence_band}</span>
        </div>
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
            <div><span className="eyebrow">System shape</span><h3>Observed architecture</h3></div>
            <button onClick={() => setActive("Architecture")}>Explore →</button>
          </div>
          <ArchitectureDiagram arch={doc.architecture} />
          <p className="evidence-note"><ShieldCheck size={14} /> {doc.architecture.summary}</p>
        </article>
        <article className="content-card signals">
          <div className="card-title">
            <div><span className="eyebrow">Observed signals</span><h3>Technology profile</h3></div>
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
          <div><span className="eyebrow">Engineering insights</span><h3>How the product likely works</h3></div>
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

function Panel({ children }: { children: React.ReactNode }) {
  return <section className="section-panel">{children}</section>;
}

function ArchitectureSection({ doc }: { doc: ReportDocument }) {
  const arch = doc.architecture;
  const nodeById = new Map(arch.nodes.map((node) => [node.id, node]));
  const observed = arch.nodes.filter((node) => node.classification === "observed").length;
  const inferred = arch.nodes.filter((node) => node.classification === "inferred").length;
  return (
    <Panel>
      <SectionHead eyebrow="System reconstruction" title="Architecture" summary={arch.summary} confidence={arch.confidence} />
      <div className="architecture-metrics">
        <article><b>{arch.nodes.length}</b><span>components</span></article>
        <article><b>{arch.connections?.length ?? arch.edges.length}</b><span>connections</span></article>
        <article><b>{observed || arch.nodes.length}</b><span>observed</span></article>
        <article><b>{inferred}</b><span>inferred</span></article>
      </div>
      <div className="diagram-frame"><ArchitectureDiagram arch={arch} /></div>

      {!!arch.request_flows?.length && (
        <div className="architecture-block">
          <ArchitectureBlockHead eyebrow="Runtime paths" title="Reconstructed request flows" />
          <div className="arch-flow-grid">
            {arch.request_flows.map((flow) => (
              <article className="arch-flow-card" key={flow.name}>
                <div className="arch-flow-card-head">
                  <div><b>{flow.name}</b><small>{flow.transport}</small></div>
                  <ConfidenceChip score={flow.confidence} />
                </div>
                <div className="arch-path">
                  {flow.steps.map((step, index) => (
                    <span key={`${flow.name}-${step}`}>
                      <b>{nodeById.get(step)?.label ?? step}</b>
                      {index < flow.steps.length - 1 && <em>→</em>}
                    </span>
                  ))}
                </div>
                <div className="arch-flow-foot"><ClassTag value={flow.classification} /> {flow.evidence[0] && <code>{flow.evidence[0]}</code>}</div>
              </article>
            ))}
          </div>
        </div>
      )}

      {!!arch.connections?.length && (
        <div className="architecture-block">
          <ArchitectureBlockHead eyebrow="Dependency map" title="Component connections" />
          <div className="arch-connection-list">
            {arch.connections.map((connection, index) => (
              <article className="arch-connection" key={`${connection.from}-${connection.to}-${index}`}>
                <div className="arch-connection-route">
                  <b>{nodeById.get(connection.from)?.label ?? connection.from}</b>
                  <span><i />{connection.protocol}<i /></span>
                  <b>{nodeById.get(connection.to)?.label ?? connection.to}</b>
                </div>
                <div className="arch-connection-meta">
                  <p>{connection.label}</p>
                  <ClassTag value={connection.classification} />
                  <ConfidenceChip score={connection.confidence} />
                </div>
                {connection.evidence[0] && <code>{connection.evidence[0]}</code>}
              </article>
            ))}
          </div>
        </div>
      )}

      <div className="architecture-block">
        <ArchitectureBlockHead eyebrow="Component inventory" title="What each layer is responsible for" />
        <div className="arch-inventory">
          {arch.nodes.map((node) => (
            <article key={node.id}>
              <div className="arch-inventory-head">
                <span>{node.kind}</span><ClassTag value={node.classification ?? "inferred"} />
              </div>
              <h3>{node.label}</h3>
              <p>{node.role ?? "Role inferred from its position in the public request path."}</p>
              {!!node.responsibilities?.length && <ul>{node.responsibilities.map((item) => <li key={item}>{item}</li>)}</ul>}
              {!!node.evidence?.length && <code>{node.evidence[0]}</code>}
            </article>
          ))}
        </div>
      </div>

      <div className="architecture-two-col">
        {!!arch.trust_boundaries?.length && (
          <div className="architecture-block compact">
            <ArchitectureBlockHead eyebrow="Security model" title="Trust boundaries" />
            <div className="arch-detail-list">
              {arch.trust_boundaries.map((boundary) => (
                <article key={boundary.name}>
                  <div><b>{boundary.name}</b><ConfidenceChip score={boundary.confidence} /></div>
                  <small>{boundary.between.join(" → ")}</small>
                  <p>{boundary.implication}</p>
                </article>
              ))}
            </div>
          </div>
        )}
        {!!arch.patterns?.length && (
          <div className="architecture-block compact">
            <ArchitectureBlockHead eyebrow="Runtime behavior" title="Architecture patterns" />
            <div className="arch-detail-list">
              {arch.patterns.map((pattern) => (
                <article key={pattern.title}>
                  <div><b>{pattern.title}</b><ConfidenceChip score={pattern.confidence} /></div>
                  <p>{pattern.detail}</p>
                  {pattern.evidence[0] && <code>{pattern.evidence[0]}</code>}
                </article>
              ))}
            </div>
          </div>
        )}
      </div>

      {!!arch.unknowns?.length && (
        <div className="arch-unknowns">
          <span><TriangleAlert size={16} /> Not observable from the public surface</span>
          <ul>{arch.unknowns.map((item) => <li key={item}>{item}</li>)}</ul>
        </div>
      )}
      <ReasoningNote text={arch.reasoning} />
      <EvidenceList items={arch.evidence} />
    </Panel>
  );
}

function ArchitectureBlockHead({ eyebrow, title }: { eyebrow: string; title: string }) {
  return <div className="architecture-block-head"><span>{eyebrow}</span><h3>{title}</h3></div>;
}

function FlowsSection({ doc }: { doc: ReportDocument }) {
  const uf = doc.user_flows;
  return (
    <Panel>
      <SectionHead eyebrow="Product journeys" title="User flows" summary={uf.summary} confidence={uf.confidence} />
      {uf.flows.length === 0 ? (
        <UnableToDetermine reason={uf.reasoning} />
      ) : (
        <>
          <div className="flow-list">
            {uf.flows.map((flow) => (
              <div className="flow-card" key={flow.name}>
                <div className="flow-card-head"><b>{flow.name}</b><ConfidenceChip score={flow.confidence} /></div>
                <FlowDiagram steps={flow.steps} />
              </div>
            ))}
          </div>
          <ReasoningNote text={uf.reasoning} />
        </>
      )}
    </Panel>
  );
}

function FeaturesSection({ doc }: { doc: ReportDocument }) {
  return (
    <Panel>
      <SectionHead eyebrow="Product surface" title="Features" summary={doc.features.summary} confidence={doc.features.confidence} />
      {doc.features.items.length === 0 ? (
        <UnableToDetermine reason={doc.meta.access_limited
          ? "The target denied access before Orbit could inspect rendered product surfaces. Zero here means unavailable, not that the product has no features."
          : "No product capabilities were supported by the rendered text, navigation, metadata, or first-party network paths that Orbit observed."} />
      ) : <div className="rf-grid">
        {doc.features.items.map((feature) => (
          <article className="rf-card" key={feature.name}>
            <div className="rf-head"><b>{feature.name}</b><ConfidenceChip score={feature.confidence} /></div>
            <p>{feature.description}</p>
            <div className="rf-foot"><ClassTag value={feature.classification} /></div>
            <EvidenceList items={feature.evidence} />
          </article>
        ))}
      </div>}
    </Panel>
  );
}

function EntitiesSection({ doc }: { doc: ReportDocument }) {
  const e = doc.entities;
  return (
    <Panel>
      <SectionHead eyebrow="Data model" title="Entities" summary={e.summary} confidence={e.confidence} />
      {e.items.length === 0 ? (
        <UnableToDetermine reason={e.reasoning} />
      ) : (
        <>
          <ERDiagram entities={e.items} relationships={e.relationships} />
          <ReasoningNote text={e.reasoning} />
        </>
      )}
    </Panel>
  );
}

function DatabaseSection({ doc }: { doc: ReportDocument }) {
  const db = doc.database;
  return (
    <Panel>
      <SectionHead eyebrow="Inferred schema" title="Database" summary={db.summary} confidence={db.confidence} />
      {db.items.length === 0 ? (
        <UnableToDetermine reason={db.reasoning} />
      ) : (
        <>
          <ERDiagram entities={db.items} relationships={db.relationships} />
          <ReasoningNote text={db.reasoning} />
        </>
      )}
    </Panel>
  );
}

function PermissionsSection({ doc }: { doc: ReportDocument }) {
  const perms = doc.permissions;
  return (
    <Panel>
      <SectionHead eyebrow="Access model" title="Permissions" summary={perms.summary} confidence={perms.confidence} />
      {perms.roles.length === 0 ? (
        <UnableToDetermine reason={perms.reasoning} />
      ) : (
        <>
          <div className="role-grid">
            {perms.roles.map((role) => (
              <article className="role-card" key={role.name}>
                <b>{role.name}</b>
                <ul>{role.capabilities.map((cap) => <li key={cap}>{cap}</li>)}</ul>
              </article>
            ))}
          </div>
          <ReasoningNote text={perms.reasoning} />
        </>
      )}
    </Panel>
  );
}

function ApiSection({ doc }: { doc: ReportDocument }) {
  const api = doc.api;
  return (
    <Panel>
      <SectionHead eyebrow="Interface" title="API" summary={api.summary} confidence={api.confidence} />
      <div className="api-style">
        <span className="eyebrow">Detected style</span>
        <b>{api.style}</b>
      </div>
      {api.spec && (
        <div className="api-spec">
          <span className="spec-badge">OpenAPI</span>
          <div>
            <b>{api.spec.title ?? "API specification"}{api.spec.version ? ` · v${api.spec.version}` : ""}</b>
            <small>{api.spec.path_count} documented path{api.spec.path_count === 1 ? "" : "s"}</small>
          </div>
        </div>
      )}
      {api.findings && api.findings.length > 0 && <FindingsList findings={api.findings} />}
      <div className="endpoint-list">
        {api.endpoints.map((ep, index) => (
          <div className="endpoint-row" key={index}>
            <span className={`method ${ep.method.toLowerCase()}`}>{ep.method}</span>
            <code>{ep.path}</code>
            <small>{ep.note}</small>
            <em>{ep.confidence}%</em>
          </div>
        ))}
      </div>
      <EvidenceList items={api.evidence} />
    </Panel>
  );
}

function TechSection({ doc }: { doc: ReportDocument }) {
  const byCat = groupBy(doc.tech_stack.items, (t) => t.category);
  return (
    <Panel>
      <SectionHead eyebrow="Observed stack" title="Tech stack" summary={doc.tech_stack.summary} confidence={doc.tech_stack.confidence} />
      {Object.entries(byCat).map(([category, items]) => (
        <div className="tech-group" key={category}>
          <span className="eyebrow">{category}</span>
          <div className="tech-list">
            {items.map((tech) => (
              <div className="tech-item" key={tech.name}>
                <span className="tech-logo">{tech.name[0]}</span>
                <div className="tech-meta"><b>{tech.name}</b><small>{tech.evidence[0] ?? "Observed signal"}</small></div>
                <ConfidenceChip score={tech.confidence} />
              </div>
            ))}
          </div>
        </div>
      ))}
      {doc.tech_stack.items.length === 0 && <p className="empty-note">No third-party technologies were clearly observed on the public surface.</p>}
    </Panel>
  );
}

function IntegrationsSection({ doc }: { doc: ReportDocument }) {
  return (
    <Panel>
      <SectionHead eyebrow="Third-party services" title="Integrations" summary={doc.integrations.summary} confidence={doc.integrations.confidence} />
      <div className="tech-list">
        {doc.integrations.items.map((item) => (
          <div className="tech-item" key={item.name}>
            <span className="tech-logo">{item.name[0]}</span>
            <div className="tech-meta"><b>{item.name}</b><small>{item.category}</small></div>
            <ConfidenceChip score={item.confidence} />
          </div>
        ))}
      </div>
      {doc.integrations.items.length === 0 && <p className="empty-note">No third-party integrations were clearly observed.</p>}
    </Panel>
  );
}

function InsightsSection({ doc }: { doc: ReportDocument }) {
  return (
    <Panel>
      <SectionHead eyebrow="Engineering insights" title="Engineering insights" summary={doc.insights.summary} confidence={doc.insights.confidence} />
      <div className="insight-grid wide">
        {doc.insights.items.map((insight) => (
          <article className="insight" key={insight.title}>
            <span><Sparkles size={17} /></span>
            <div>
              <div className="insight-head"><h4>{insight.title}</h4><ClassTag value={insight.classification} /></div>
              <p>{insight.detail}</p>
              <b>{insight.confidence}% confidence</b>
            </div>
          </article>
        ))}
      </div>
      <ReasoningNote text={doc.insights.reasoning} />
    </Panel>
  );
}

function InfraSection({ doc }: { doc: ReportDocument }) {
  return (
    <Panel>
      <SectionHead eyebrow="Platform" title="Infrastructure" summary={doc.infrastructure.summary} confidence={doc.infrastructure.confidence} />
      <div className="stack-list">
        {doc.infrastructure.items.map((item) => (
          <div className="stack-row" key={item.title}>
            <div><b>{item.title}</b><small>{item.detail}</small></div>
            <ConfidenceChip score={item.confidence} />
          </div>
        ))}
      </div>
    </Panel>
  );
}

function SecuritySection({ doc }: { doc: ReportDocument }) {
  const sec = doc.security;
  // Deep reports carry graded findings; legacy reports carry `items`.
  if (!sec.findings && sec.items) {
    return (
      <Panel>
        <SectionHead eyebrow="Posture" title="Security" summary={sec.summary} confidence={sec.confidence} />
        <div className="stack-list">
          {sec.items.map((item) => (
            <div className="stack-row" key={item.title}>
              <div><b>{item.title}</b><small>{item.detail}</small></div>
              <ConfidenceChip score={item.confidence} />
            </div>
          ))}
        </div>
      </Panel>
    );
  }
  return <GradedSectionView eyebrow="Posture" title="Security" section={sec} />;
}

function GradedSectionView({
  eyebrow, title, section,
}: {
  eyebrow: string;
  title: string;
  section?: { summary: string; confidence: number; grade?: string; score?: number; findings: import("@/lib/types").Finding[]; metrics?: import("@/lib/types").SectionMetric[] };
}) {
  if (!section) {
    return (
      <Panel>
        <SectionHead eyebrow={eyebrow} title={title} summary="This section isn't available for this report." />
        <p className="empty-note">Re-run the analysis to generate this section.</p>
      </Panel>
    );
  }
  return (
    <Panel>
      <div className="graded-head">
        <SectionHead eyebrow={eyebrow} title={title} summary={section.summary} confidence={section.grade ? undefined : section.confidence} />
        <GradeBadge grade={section.grade} score={section.score} />
      </div>
      <MetricsStrip metrics={section.metrics} />
      <FindingsList findings={section.findings} />
    </Panel>
  );
}

function RenderingSectionView({ doc }: { doc: ReportDocument }) {
  const section = doc.rendering;
  if (!section) {
    return (
      <Panel>
        <SectionHead eyebrow="Delivery" title="Rendering" summary="This section isn't available for this report." />
        <p className="empty-note">Re-run the analysis to generate this section.</p>
      </Panel>
    );
  }
  return (
    <Panel>
      <SectionHead eyebrow="Delivery strategy" title="Rendering & deployment" summary={section.summary} confidence={section.confidence} />
      <MetricsStrip metrics={section.metrics} />
      <FindingsList findings={section.findings} />
    </Panel>
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

function groupBy<T>(items: T[], key: (item: T) => string): Record<string, T[]> {
  return items.reduce<Record<string, T[]>>((acc, item) => {
    const k = key(item);
    (acc[k] ??= []).push(item);
    return acc;
  }, {});
}
