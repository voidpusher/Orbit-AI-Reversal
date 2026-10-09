"use client";

import { Sparkles, TriangleAlert } from "lucide-react";
import type { ReportDocument } from "@/lib/types";
import { ERDiagram, FlowDiagram } from "./diagrams";
import { ArchitectureWorkspace } from "./ArchitectureWorkspace";
import { ClassTag, ConfidenceChip, EvidenceList, ReasoningNote, SectionHead, UnableToDetermine } from "./primitives";
import { FindingsList, GradeBadge, MetricsStrip } from "./findings";

export function ReportSection({ active, doc }: { active: string; doc: ReportDocument }) {
  switch (active) {
    case "Architecture": return <ArchitectureSection doc={doc} />;
    case "User flows": return <FlowsSection doc={doc} />;
    case "Features": return <FeaturesSection doc={doc} />;
    case "Entities": return <EntitiesSection doc={doc} />;
    case "Permissions": return <PermissionsSection doc={doc} />;
    case "Database": return <DatabaseSection doc={doc} />;
    case "API": return <ApiSection doc={doc} />;
    case "Tech stack": return <TechSection doc={doc} />;
    case "Integrations": return <IntegrationsSection doc={doc} />;
    case "Insights":
    case "Engineering insights": return <InsightsSection doc={doc} />;
    case "Infrastructure": return <InfraSection doc={doc} />;
    case "Security": return <SecuritySection doc={doc} />;
    case "Rendering": return <RenderingSectionView doc={doc} />;
    case "Performance": return <GradedSectionView title="Performance" section={doc.performance} />;
    case "SEO": return <GradedSectionView title="SEO & metadata" section={doc.seo} />;
    case "Privacy": return <GradedSectionView title="Privacy" section={doc.privacy} />;
    case "Domain & email": return <GradedSectionView title="Domain & email" section={doc.domain} />;
    default: return <section className="section-panel"><UnableToDetermine reason="This section is not available in this report." /></section>;
  }
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
      <SectionHead title="Architecture" summary={arch.summary} confidence={arch.confidence} />
      <div className="architecture-metrics">
        <article><b>{arch.nodes.length}</b><span>components</span></article>
        <article><b>{arch.connections?.length ?? arch.edges.length}</b><span>connections</span></article>
        <article><b>{observed}</b><span>observed</span></article>
        <article><b>{inferred}</b><span>inferred</span></article>
      </div>
      <ArchitectureWorkspace arch={arch} productName={doc.meta.product_name} />

      {!!arch.request_flows?.length && (
        <div className="architecture-block">
          <ArchitectureBlockHead title="Reconstructed request flows" />
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
          <ArchitectureBlockHead title="Component connections" />
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
        <ArchitectureBlockHead title="What each layer is responsible for" />
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
            <ArchitectureBlockHead title="Trust boundaries" />
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
            <ArchitectureBlockHead title="Architecture patterns" />
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

function ArchitectureBlockHead({ title }: { title: string }) {
  return <div className="architecture-block-head"><h3>{title}</h3></div>;
}

function FlowsSection({ doc }: { doc: ReportDocument }) {
  const uf = doc.user_flows;
  return (
    <Panel>
      <SectionHead title="User flows" summary={uf.summary} confidence={uf.confidence} />
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
      <SectionHead title="Features" summary={doc.features.summary} confidence={doc.features.confidence} />
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
      <SectionHead title="Entities" summary={e.summary} confidence={e.confidence} />
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
      <SectionHead title="Database" summary={db.summary} confidence={db.confidence} />
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
      <SectionHead title="Permissions" summary={perms.summary} confidence={perms.confidence} />
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
      <SectionHead title="API" summary={api.summary} confidence={api.confidence} />
      <div className="api-style" aria-label="API style">
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
      <SectionHead title="Tech stack" summary={doc.tech_stack.summary} confidence={doc.tech_stack.confidence} />
      {Object.entries(byCat).map(([category, items]) => (
        <div className="tech-group" key={category}>
          <h3 className="content-group-title">{category}</h3>
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
      <SectionHead title="Integrations" summary={doc.integrations.summary} confidence={doc.integrations.confidence} />
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
      <SectionHead title="Engineering insights" summary={doc.insights.summary} confidence={doc.insights.confidence} />
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
      <SectionHead title="Infrastructure" summary={doc.infrastructure.summary} confidence={doc.infrastructure.confidence} />
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
        <SectionHead title="Security" summary={sec.summary} confidence={sec.confidence} />
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
  return <GradedSectionView title="Security" section={sec} />;
}

function GradedSectionView({
  title, section,
}: {
  title: string;
  section?: { summary: string; confidence: number; grade?: string; score?: number; findings: import("@/lib/types").Finding[]; metrics?: import("@/lib/types").SectionMetric[] };
}) {
  if (!section) {
    return (
      <Panel>
        <SectionHead title={title} summary="This section isn't available for this report." />
        <p className="empty-note">Re-run the analysis to generate this section.</p>
      </Panel>
    );
  }
  return (
    <Panel>
      <div className="graded-head">
        <SectionHead title={title} summary={section.summary} confidence={section.grade ? undefined : section.confidence} />
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
        <SectionHead title="Rendering" summary="This section isn't available for this report." />
        <p className="empty-note">Re-run the analysis to generate this section.</p>
      </Panel>
    );
  }
  return (
    <Panel>
      <SectionHead title="Rendering & deployment" summary={section.summary} confidence={section.confidence} />
      <MetricsStrip metrics={section.metrics} />
      <FindingsList findings={section.findings} />
    </Panel>
  );
}

function groupBy<T>(items: T[], key: (item: T) => string): Record<string, T[]> {
  return items.reduce<Record<string, T[]>>((acc, item) => {
    const k = key(item);
    (acc[k] ??= []).push(item);
    return acc;
  }, {});
}


