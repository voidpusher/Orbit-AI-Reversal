"use client";

import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  Position,
  ReactFlow,
  useEdgesState,
  useNodesState,
  type Edge,
  type Node,
  type NodeProps,
  type ReactFlowInstance,
} from "reactflow";
import {
  Boxes,
  ChevronDown,
  Cloud,
  Code2,
  Database,
  Download,
  Eye,
  FileJson,
  FileType2,
  Globe2,
  HardDrive,
  Image as ImageIcon,
  Layers3,
  Network,
  Radio,
  RotateCcw,
  Server,
  ShieldCheck,
  Workflow,
  X,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import type { ArchConnection, ArchNode, ReportDocument } from "@/lib/types";

type Architecture = ReportDocument["architecture"];
type Classification = "observed" | "inferred";

type ArchitectureNodeData = {
  node: ArchNode;
  accent: string;
};

const NODE_WIDTH = 214;
const NODE_HEIGHT = 112;

const KIND_COLORS: Record<string, string> = {
  client: "#7ab8ff",
  browser: "#7ab8ff",
  edge: "#4aa6e8",
  frontend: "#6ee7ff",
  api: "#e6c15c",
  realtime: "#5ee0c0",
  worker: "#c7a7ff",
  data: "#6ec4f0",
  database: "#6ec4f0",
  storage: "#66b8ff",
  infra: "#9a9aa4",
  auth: "#9ecdff",
  payment: "#f4c86b",
  analytics: "#72b8ff",
  monitoring: "#fa8f71",
  search: "#9ecdff",
  cms: "#75d4e8",
  commerce: "#e6c15c",
  experimentation: "#7ab8ff",
  support: "#5ee0c0",
  email: "#5ee0c0",
  marketing: "#5ee0c0",
};

const CORE_X: Record<string, number> = {
  client: 0,
  browser: 0,
  edge: 290,
  frontend: 580,
  api: 870,
  data: 1160,
  database: 1160,
};

function kindIcon(kind: string) {
  const size = 17;
  if (kind === "client" || kind === "browser") return <Globe2 size={size} />;
  if (kind === "edge" || kind === "infra") return <Cloud size={size} />;
  if (kind === "frontend") return <Code2 size={size} />;
  if (kind === "api") return <Network size={size} />;
  if (kind === "realtime") return <Radio size={size} />;
  if (kind === "worker") return <Workflow size={size} />;
  if (kind === "data" || kind === "database") return <Database size={size} />;
  if (kind === "storage") return <HardDrive size={size} />;
  if (kind === "auth") return <ShieldCheck size={size} />;
  return <Boxes size={size} />;
}

function ArchitectureNodeCard({ data, selected }: NodeProps<ArchitectureNodeData>) {
  const { node, accent } = data;
  const classification = node.classification ?? "inferred";
  return (
    <div className={`architecture-flow-node ${classification}${selected ? " selected" : ""}`} style={{ "--node-accent": accent } as React.CSSProperties}>
      <Handle type="target" position={Position.Left} />
      <Handle type="source" position={Position.Right} />
      <Handle id="top" type="target" position={Position.Top} />
      <Handle id="bottom" type="source" position={Position.Bottom} />
      <div className="architecture-flow-node-top">
        <span className="architecture-flow-node-icon">{kindIcon(node.kind)}</span>
        <span className={`architecture-flow-class ${classification}`}><i />{classification}</span>
        <b>{Math.round(node.confidence)}%</b>
      </div>
      <strong>{node.label}</strong>
      <small>{node.role ?? `${node.kind} component`}</small>
    </div>
  );
}

const nodeTypes = { architecture: ArchitectureNodeCard };

function layoutNodes(nodes: ArchNode[]): Node<ArchitectureNodeData>[] {
  const auxiliary = nodes.filter((node) => !(node.kind in CORE_X) && node.kind !== "realtime" && node.kind !== "worker" && node.kind !== "infra");
  let auxiliaryIndex = 0;

  return nodes.map((node) => {
    let position = { x: CORE_X[node.kind] ?? 580, y: 40 };
    if (node.kind === "realtime") position = { x: 870, y: 235 };
    if (node.kind === "worker") position = { x: 870, y: 430 };
    if (node.kind === "infra") position = { x: 580, y: -155 };
    if (auxiliary.includes(node)) {
      const column = auxiliaryIndex % 3;
      const row = Math.floor(auxiliaryIndex / 3);
      position = { x: 580 + column * 290, y: 625 + row * 165 };
      auxiliaryIndex += 1;
    }
    return {
      id: node.id,
      type: "architecture",
      position,
      data: { node, accent: KIND_COLORS[node.kind] ?? "#8aa3b7" },
      style: { width: NODE_WIDTH, height: NODE_HEIGHT },
    };
  });
}

function normalizedConnections(arch: Architecture): ArchConnection[] {
  if (arch.connections?.length) return arch.connections;
  return arch.edges.map(([from, to]) => ({
    from,
    to,
    label: "Observed relationship",
    protocol: "Unknown",
    confidence: Math.min(
      arch.nodes.find((node) => node.id === from)?.confidence ?? 60,
      arch.nodes.find((node) => node.id === to)?.confidence ?? 60,
    ),
    classification: "inferred" as const,
    evidence: [],
  }));
}

function flowEdges(arch: Architecture): Edge[] {
  return normalizedConnections(arch).map((connection, index) => {
    const inferred = connection.classification === "inferred";
    return {
      id: `${connection.from}-${connection.to}-${index}`,
      source: connection.from,
      target: connection.to,
      type: "smoothstep",
      label: connection.protocol,
      markerEnd: { type: MarkerType.ArrowClosed, color: inferred ? "var(--diagram-inferred)" : "var(--diagram-observed)", width: 16, height: 16 },
      className: `architecture-flow-edge ${connection.classification}`,
      style: {
        stroke: inferred ? "var(--diagram-inferred)" : "var(--diagram-observed)",
        strokeWidth: inferred ? 1.25 : 1.8,
        strokeDasharray: inferred ? "7 6" : undefined,
      },
      labelStyle: { fill: "var(--text)", fontSize: 11, fontFamily: "DM Mono" },
      labelBgStyle: { fill: "var(--diagram-label-surface)", fillOpacity: 0.96 },
      labelBgPadding: [6, 4] as [number, number],
      labelBgBorderRadius: 5,
      data: { connection },
    };
  });
}

function evidenceUrls(arch: Architecture): string[] {
  const evidence = [
    ...arch.evidence,
    ...arch.nodes.flatMap((node) => node.evidence ?? []),
    ...normalizedConnections(arch).flatMap((connection) => connection.evidence),
  ];
  const urls = evidence.flatMap((item) => item.match(/https?:\/\/[^\s),]+/g) ?? []);
  return [...new Set(urls)].slice(0, 20);
}

function downloadFile(filename: string, type: string, content: string | Blob) {
  const blob = content instanceof Blob ? content : new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

function safeName(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "orbit-architecture";
}

function pageLabel(value: string) {
  try {
    const url = new URL(value);
    return url.pathname === "/" ? url.hostname : url.pathname;
  } catch {
    return value;
  }
}

function escapeXml(value: string) {
  return value.replace(/[<>&"']/g, (character) => ({ "<": "&lt;", ">": "&gt;", "&": "&amp;", '"': "&quot;", "'": "&apos;" })[character] ?? character);
}

function escapeMermaid(value: string) {
  return value.replace(/"/g, "'").replace(/[\[\]{}]/g, "");
}

function architectureSvg(nodes: Node<ArchitectureNodeData>[], edges: Edge[]) {
  if (!nodes.length) return "";
  const padding = 70;
  const minX = Math.min(...nodes.map((node) => node.position.x));
  const minY = Math.min(...nodes.map((node) => node.position.y));
  const maxX = Math.max(...nodes.map((node) => node.position.x + NODE_WIDTH));
  const maxY = Math.max(...nodes.map((node) => node.position.y + NODE_HEIGHT));
  const width = maxX - minX + padding * 2;
  const height = maxY - minY + padding * 2;
  const nodeById = new Map(nodes.map((node) => [node.id, node]));
  const x = (value: number) => value - minX + padding;
  const y = (value: number) => value - minY + padding;
  const edgeMarkup = edges.map((edge) => {
    const source = nodeById.get(edge.source);
    const target = nodeById.get(edge.target);
    if (!source || !target) return "";
    const sx = x(source.position.x + NODE_WIDTH);
    const sy = y(source.position.y + NODE_HEIGHT / 2);
    const tx = x(target.position.x);
    const ty = y(target.position.y + NODE_HEIGHT / 2);
    const mid = (sx + tx) / 2;
    const connection = edge.data?.connection as ArchConnection | undefined;
    const inferred = connection?.classification === "inferred";
    return `<path d="M ${sx} ${sy} C ${mid} ${sy}, ${mid} ${ty}, ${tx} ${ty}" fill="none" stroke="${inferred ? "#8292a3" : "#6ee7ff"}" stroke-width="${inferred ? 1.5 : 2}" ${inferred ? 'stroke-dasharray="7 6"' : ""} marker-end="url(#${inferred ? "arrow-inferred" : "arrow-observed"})"/>`;
  }).join("");
  const nodeMarkup = nodes.map(({ position, data }) => {
    const node = data.node;
    const classification = node.classification ?? "inferred";
    return `<g transform="translate(${x(position.x)} ${y(position.y)})">
      <rect width="${NODE_WIDTH}" height="${NODE_HEIGHT}" rx="14" fill="#10161d" stroke="${data.accent}" stroke-opacity=".68"/>
      <rect x="14" y="14" width="42" height="18" rx="9" fill="${data.accent}" fill-opacity=".12"/>
      <text x="35" y="27" text-anchor="middle" fill="${data.accent}" font-family="Arial" font-size="8" font-weight="700">${escapeXml(node.kind.toUpperCase())}</text>
      <text x="198" y="27" text-anchor="end" fill="#a9b4bf" font-family="Arial" font-size="10">${Math.round(node.confidence)}%</text>
      <text x="16" y="61" fill="#f4f6f8" font-family="Arial" font-size="15" font-weight="700">${escapeXml(node.label.slice(0, 26))}</text>
      <text x="16" y="83" fill="#8e9aa6" font-family="Arial" font-size="10">${escapeXml((node.role ?? classification).slice(0, 35))}</text>
      <circle cx="18" cy="98" r="3" fill="${classification === "observed" ? "#7fe3a6" : "#9ecdff"}"/>
      <text x="27" y="101" fill="#7f8b96" font-family="Arial" font-size="8">${classification.toUpperCase()}</text>
    </g>`;
  }).join("");
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}" viewBox="0 0 ${width} ${height}">
    <defs>
      <pattern id="grid" width="22" height="22" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="1" fill="#52606d" fill-opacity=".28"/></pattern>
      <marker id="arrow-observed" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#6ee7ff"/></marker>
      <marker id="arrow-inferred" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse"><path d="M 0 0 L 10 5 L 0 10 z" fill="#8292a3"/></marker>
    </defs>
    <rect width="100%" height="100%" rx="18" fill="#080c11"/>
    <rect width="100%" height="100%" rx="18" fill="url(#grid)"/>
    ${edgeMarkup}${nodeMarkup}
  </svg>`;
}

export function ArchitectureWorkspace({ arch, productName }: { arch: Architecture; productName: string }) {
  const [nodes, setNodes, onNodesChange] = useNodesState<ArchitectureNodeData>(layoutNodes(arch.nodes));
  const [edges, setEdges, onEdgesChange] = useEdgesState(flowEdges(arch));
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(arch.nodes[0]?.id ?? null);
  const [classification, setClassification] = useState<"all" | Classification>("all");
  const [page, setPage] = useState("all");
  const [journey, setJourney] = useState("all");
  const [technology, setTechnology] = useState("all");
  const [minimumConfidence, setMinimumConfidence] = useState(0);
  const [showExport, setShowExport] = useState(false);
  const instanceRef = useRef<ReactFlowInstance | null>(null);
  const pages = useMemo(() => evidenceUrls(arch), [arch]);
  const technologies = useMemo(() => arch.nodes.filter((node) => node.kind !== "client").map((node) => node.id), [arch.nodes]);
  const connections = useMemo(() => normalizedConnections(arch), [arch]);

  useEffect(() => {
    setNodes(layoutNodes(arch.nodes));
    setEdges(flowEdges(arch));
    setSelectedNodeId(arch.nodes[0]?.id ?? null);
  }, [arch, setEdges, setNodes]);

  const includedIds = useMemo(() => {
    let ids = new Set(arch.nodes.map((node) => node.id));
    if (classification !== "all") ids = new Set(arch.nodes.filter((node) => (node.classification ?? "inferred") === classification).map((node) => node.id));
    ids = new Set([...ids].filter((id) => (arch.nodes.find((node) => node.id === id)?.confidence ?? 0) >= minimumConfidence));

    const focusWithContext = (focus: Set<string>) => {
      const expanded = new Set(focus);
      connections.forEach((connection) => {
        if (focus.has(connection.from)) expanded.add(connection.to);
        if (focus.has(connection.to)) expanded.add(connection.from);
      });
      return expanded;
    };

    if (technology !== "all") ids = new Set([...ids].filter((id) => focusWithContext(new Set([technology])).has(id)));
    if (journey !== "all") {
      const flow = arch.request_flows?.find((item) => item.name === journey);
      if (flow) ids = new Set([...ids].filter((id) => new Set(flow.steps).has(id)));
    }
    if (page !== "all") {
      const matches = new Set(arch.nodes.filter((node) => node.evidence?.some((item) => item.includes(page))).map((node) => node.id));
      connections.forEach((connection) => {
        if (connection.evidence.some((item) => item.includes(page))) {
          matches.add(connection.from);
          matches.add(connection.to);
        }
      });
      ids = new Set([...ids].filter((id) => focusWithContext(matches).has(id)));
    }
    return ids;
  }, [arch.nodes, arch.request_flows, classification, connections, journey, minimumConfidence, page, technology]);

  const visibleNodes = useMemo(() => nodes.map((node) => ({ ...node, hidden: !includedIds.has(node.id) })), [includedIds, nodes]);
  const visibleEdges = useMemo(() => edges.map((edge) => ({ ...edge, hidden: !includedIds.has(edge.source) || !includedIds.has(edge.target) })), [edges, includedIds]);
  const exportNodes = visibleNodes.filter((node) => !node.hidden);
  const exportEdges = visibleEdges.filter((edge) => !edge.hidden);
  const selectedNode = arch.nodes.find((node) => node.id === selectedNodeId) ?? null;
  const selectedConnections = selectedNode ? connections.filter((connection) => connection.from === selectedNode.id || connection.to === selectedNode.id) : [];
  const filename = safeName(productName);

  useEffect(() => {
    if (selectedNodeId && !includedIds.has(selectedNodeId)) {
      setSelectedNodeId(includedIds.values().next().value ?? null);
    }
  }, [includedIds, selectedNodeId]);

  useEffect(() => {
    const frame = requestAnimationFrame(() => instanceRef.current?.fitView({ padding: 0.15, minZoom: 0.75, maxZoom: 1, duration: 250, includeHiddenNodes: false }));
    return () => cancelAnimationFrame(frame);
  }, [classification, journey, minimumConfidence, page, technology]);

  const resetFilters = () => {
    setClassification("all");
    setPage("all");
    setJourney("all");
    setTechnology("all");
    setMinimumConfidence(0);
  };

  const exportJson = () => {
    const payload = {
      schema: "orbit.architecture.v1",
      product: productName,
      exported_at: new Date().toISOString(),
      nodes: exportNodes.map((node) => ({ ...node.data.node, position: node.position })),
      connections: exportEdges.map((edge) => edge.data?.connection),
      request_flows: arch.request_flows ?? [],
      trust_boundaries: arch.trust_boundaries ?? [],
      unknowns: arch.unknowns ?? [],
    };
    downloadFile(`${filename}-architecture.json`, "application/json", JSON.stringify(payload, null, 2));
  };

  const exportMermaid = () => {
    const lines = ["flowchart LR"];
    exportNodes.forEach((node) => lines.push(`  ${safeName(node.id).replace(/-/g, "_")}[\"${escapeMermaid(node.data.node.label)}\"]`));
    exportEdges.forEach((edge) => {
      const connection = edge.data?.connection as ArchConnection | undefined;
      const from = safeName(edge.source).replace(/-/g, "_");
      const to = safeName(edge.target).replace(/-/g, "_");
      const arrow = connection?.classification === "inferred" ? "-.->" : "-->";
      lines.push(`  ${from} ${arrow}|${escapeMermaid(connection?.protocol ?? "connection")}| ${to}`);
    });
    downloadFile(`${filename}-architecture.mmd`, "text/plain", lines.join("\n"));
  };

  const exportSvg = () => {
    downloadFile(`${filename}-architecture.svg`, "image/svg+xml", architectureSvg(exportNodes, exportEdges));
  };

  const exportPng = () => {
    const svg = architectureSvg(exportNodes, exportEdges);
    const blob = new Blob([svg], { type: "image/svg+xml;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const image = new Image();
    image.onload = () => {
      const canvas = document.createElement("canvas");
      const scale = 2;
      canvas.width = image.width * scale;
      canvas.height = image.height * scale;
      const context = canvas.getContext("2d");
      if (!context) {
        URL.revokeObjectURL(url);
        return;
      }
      context.scale(scale, scale);
      context.drawImage(image, 0, 0);
      canvas.toBlob((png) => png && downloadFile(`${filename}-architecture.png`, "image/png", png), "image/png");
      URL.revokeObjectURL(url);
    };
    image.onerror = () => URL.revokeObjectURL(url);
    image.src = url;
  };

  return (
    <section className="architecture-workspace">
      <header className="architecture-workspace-head">
        <div>
          <h3>System topology</h3>
          <p>Select a component to inspect its evidence.</p>
        </div>
        <div className="architecture-export-wrap">
          <button className="architecture-export-button" disabled={!exportNodes.length} onClick={() => setShowExport((value) => !value)} aria-expanded={showExport}>
            <Download size={15} /> Export <ChevronDown size={13} />
          </button>
          {showExport && (
            <div className="architecture-export-menu">
              <button onClick={exportMermaid}><Workflow size={15} /><span><b>Mermaid</b><small>Editable diagram source</small></span></button>
              <button onClick={exportPng}><ImageIcon size={15} /><span><b>PNG</b><small>High-resolution image</small></span></button>
              <button onClick={exportSvg}><FileType2 size={15} /><span><b>SVG</b><small>Scalable vector</small></span></button>
              <button onClick={exportJson}><FileJson size={15} /><span><b>JSON</b><small>Editable graph data</small></span></button>
            </div>
          )}
        </div>
      </header>

      <div className="architecture-filters" aria-label="Architecture filters">
        <label><span>Page</span><select value={page} onChange={(event) => setPage(event.target.value)}><option value="all">All pages</option>{pages.map((url) => <option value={url} key={url}>{pageLabel(url)}</option>)}</select></label>
        <label><span>Journey</span><select value={journey} onChange={(event) => setJourney(event.target.value)}><option value="all">All journeys</option>{arch.request_flows?.map((flow) => <option value={flow.name} key={flow.name}>{flow.name}</option>)}</select></label>
        <label><span>Technology</span><select value={technology} onChange={(event) => setTechnology(event.target.value)}><option value="all">All components</option>{technologies.map((id) => { const node = arch.nodes.find((item) => item.id === id)!; return <option value={id} key={id}>{node.label}</option>; })}</select></label>
        <label><span>Evidence</span><select value={classification} onChange={(event) => setClassification(event.target.value as "all" | Classification)}><option value="all">Observed + inferred</option><option value="observed">Observed only</option><option value="inferred">Inferred only</option></select></label>
        <label><span>Confidence</span><select value={minimumConfidence} onChange={(event) => setMinimumConfidence(Number(event.target.value))}><option value={0}>Any confidence</option><option value={60}>60% and above</option><option value={75}>75% and above</option><option value={90}>90% and above</option></select></label>
        <button className="architecture-reset" onClick={resetFilters}><RotateCcw size={13} /> Reset</button>
      </div>

      <div className={`architecture-canvas-shell${selectedNode ? " has-inspector" : ""}`}>
        <div className="architecture-react-flow">
          <ReactFlow
            nodes={visibleNodes}
            edges={visibleEdges}
            nodeTypes={nodeTypes}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onInit={(instance) => { instanceRef.current = instance; }}
            onNodeClick={(_, node) => setSelectedNodeId(node.id)}
            onPaneClick={() => setSelectedNodeId(null)}
            fitView
            fitViewOptions={{ padding: 0.15, minZoom: 0.75, maxZoom: 1 }}
            minZoom={0.25}
            maxZoom={1.8}
            nodesConnectable={false}
            proOptions={{ hideAttribution: true }}
          >
            <Background variant={BackgroundVariant.Dots} gap={22} size={1} color="rgba(137,160,180,.25)" />
            <Controls position="bottom-left" showInteractive={false} fitViewOptions={{ padding: 0.15 }} />
            <MiniMap
              position="bottom-right"
              pannable
              zoomable
              nodeColor={(node) => (node.data as ArchitectureNodeData).accent}
              maskColor="rgba(231,237,219,.72)"
            />
            <div className="architecture-legend">
              <span><i className="observed" />Observed</span>
              <span><i className="inferred" />Inferred</span>
              <em>{exportNodes.length} of {nodes.length} components</em>
            </div>
            {!exportNodes.length && <div className="architecture-empty-state"><p>No components match these filters.</p><button className="button secondary" onClick={resetFilters}>Reset filters</button></div>}
          </ReactFlow>
        </div>

        {selectedNode && (
          <aside className="architecture-inspector">
            <button className="architecture-inspector-close" onClick={() => setSelectedNodeId(null)} aria-label="Close component inspector"><X size={16} /></button>
            <div className="architecture-inspector-kicker"><span style={{ background: KIND_COLORS[selectedNode.kind] ?? "#8aa3b7" }}>{kindIcon(selectedNode.kind)}</span>{selectedNode.kind}</div>
            <h4>{selectedNode.label}</h4>
            <p>{selectedNode.role ?? "Role inferred from its position in the observed request path."}</p>
            <div className="architecture-inspector-meta">
              <span className={`architecture-flow-class ${selectedNode.classification ?? "inferred"}`}><i />{selectedNode.classification ?? "inferred"}</span>
              <b>{selectedNode.confidence}% confidence</b>
            </div>

            {!!selectedNode.responsibilities?.length && <div className="architecture-inspector-section"><span>Responsibilities</span><ul>{selectedNode.responsibilities.map((item) => <li key={item}>{item}</li>)}</ul></div>}
            <div className="architecture-inspector-section"><span>Reasoning</span><p>{selectedNode.classification === "observed" ? "This component is directly supported by captured product, network, header, or provider signals." : "This component is inferred from the surrounding request path and supporting technology signals; it was not directly observable."}</p></div>
            {!!selectedNode.evidence?.length && <div className="architecture-inspector-section"><span><Eye size={12} /> Evidence</span><ul className="architecture-evidence-list">{selectedNode.evidence.map((item) => <li key={item}><code>{item}</code></li>)}</ul></div>}
            {!!selectedConnections.length && <div className="architecture-inspector-section"><span>Connections</span><ul className="architecture-connection-summary">{selectedConnections.map((connection, index) => <li key={`${connection.from}-${connection.to}-${index}`}><b>{connection.from === selectedNode.id ? "Sends to" : "Receives from"}</b><em>{arch.nodes.find((node) => node.id === (connection.from === selectedNode.id ? connection.to : connection.from))?.label}</em><small>{connection.protocol} · {connection.confidence}%</small></li>)}</ul></div>}
          </aside>
        )}
      </div>
    </section>
  );
}
