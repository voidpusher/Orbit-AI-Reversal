"use client";

import { ArrowRight } from "lucide-react";
import type { ArchNode, Entity, ReportDocument } from "@/lib/types";

const NODE_TONE: Record<string, string> = {
  client: "browser",
  edge: "edge",
  frontend: "frontend",
  api: "api",
  realtime: "realtime",
  data: "db",
  infra: "infra",
  auth: "auth",
  payment: "payment",
  analytics: "analytics",
  monitoring: "monitoring",
  search: "search",
  storage: "storage",
  cms: "cms",
  commerce: "commerce",
  experimentation: "experimentation",
  support: "support",
  email: "email",
  marketing: "marketing",
};

const CORE_KINDS = new Set(["client", "edge", "frontend", "api", "data"]);

export function ArchitectureDiagram({ arch }: { arch: ReportDocument["architecture"] }) {
  const linear = arch.nodes.filter((node) => CORE_KINDS.has(node.kind));
  const branches = arch.nodes.filter((node) => !CORE_KINDS.has(node.kind));
  return (
    <div className="arch-flow">
      <div className="arch-column">
        {linear.map((node, index) => (
          <div className="arch-stage" key={node.id}>
            <ArchCard node={node} />
            {index < linear.length - 1 && <span className="arch-connector" aria-hidden />}
          </div>
        ))}
      </div>
      {branches.length > 0 && (
        <div className="arch-branches">
          <span className="arch-branches-label">Connected services</span>
          {branches.map((node) => (
            <ArchCard key={node.id} node={node} branch />
          ))}
        </div>
      )}
    </div>
  );
}

function ArchCard({ node, branch }: { node: ArchNode; branch?: boolean }) {
  return (
    <div className={`arch-card ${NODE_TONE[node.kind] ?? "frontend"} ${branch ? "branch" : ""}`}>
      <div className="arch-card-top">
        <span className="arch-kind">{node.kind}</span>
        <span className={`arch-class ${node.classification ?? "inferred"}`}>{node.classification ?? "inferred"}</span>
        <em>{node.confidence}%</em>
      </div>
      <b>{node.label}</b>
      {node.role && <small>{node.role}</small>}
    </div>
  );
}

export function FlowDiagram({ steps }: { steps: string[] }) {
  return (
    <div className="flow-track">
      {steps.map((step, index) => (
        <div className="flow-node" key={`${step}-${index}`}>
          <span className="flow-pill">
            <span className="flow-index">{index + 1}</span>
            <b>{step}</b>
          </span>
          {index < steps.length - 1 && <ArrowRight size={15} className="flow-arrow" />}
        </div>
      ))}
    </div>
  );
}

export function ERDiagram({
  entities,
  relationships,
}: {
  entities: Entity[];
  relationships: { from: string; to: string; kind: string }[];
}) {
  return (
    <div className="er-wrap">
      <div className="er-grid">
        {entities.map((entity) => (
          <div className="er-card" key={entity.name}>
            <div className="er-title">
              <b>{entity.name}</b>
              <em>{entity.confidence}%</em>
            </div>
            <ul>
              {entity.fields.map((field) => (
                <li key={field}>
                  <span className={field === "id" || field.endsWith("_id") ? "key" : ""}>{field}</span>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
      {relationships.length > 0 && (
        <div className="er-rels">
          <span className="eyebrow">Relationships</span>
          <div className="rel-list">
            {relationships.map((rel, index) => (
              <span className="rel-chip" key={index}>
                {rel.from} <i>{rel.kind}</i> {rel.to}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
