"use client";

import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import type { Finding, SectionMetric } from "@/lib/types";

const STATUS_ICON = {
  good: CheckCircle2,
  warn: AlertTriangle,
  bad: XCircle,
  info: Info,
} as const;

export function GradeBadge({ grade, score }: { grade?: string; score?: number }) {
  if (!grade) return null;
  const tone = grade === "A" ? "a" : grade === "B" ? "b" : grade === "C" ? "c" : grade === "D" ? "d" : "f";
  return (
    <div className={`grade-badge ${tone}`}>
      <b>{grade}</b>
      {score !== undefined && <small>{score}/100</small>}
    </div>
  );
}

export function MetricsStrip({ metrics }: { metrics?: SectionMetric[] }) {
  if (!metrics?.length) return null;
  return (
    <div className="metrics-strip">
      {metrics.map((m) => (
        <div className="metric-tile" key={m.label}>
          <strong>{m.value}</strong>
          <small>{m.label}</small>
        </div>
      ))}
    </div>
  );
}

export function FindingRow({ finding }: { finding: Finding }) {
  const Icon = STATUS_ICON[finding.status] ?? Info;
  return (
    <div className={`finding-row ${finding.status}`}>
      <span className="finding-icon"><Icon size={16} /></span>
      <div className="finding-body">
        <b>{finding.title}</b>
        <p>{finding.detail}</p>
        {finding.evidence && <code className="finding-evidence">{finding.evidence}</code>}
      </div>
    </div>
  );
}

export function FindingsList({ findings }: { findings: Finding[] }) {
  return (
    <div className="findings-list">
      {findings.map((f, i) => (
        <FindingRow key={`${f.title}-${i}`} finding={f} />
      ))}
    </div>
  );
}
