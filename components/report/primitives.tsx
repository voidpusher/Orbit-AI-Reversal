"use client";

import { ShieldCheck } from "lucide-react";

export function confidenceBand(score: number): string {
  if (score >= 88) return "Strong";
  if (score >= 74) return "Good";
  if (score >= 60) return "Moderate";
  return "Weak";
}

export function ConfidenceChip({ score }: { score: number }) {
  const tone = score >= 88 ? "strong" : score >= 74 ? "good" : score >= 60 ? "moderate" : "weak";
  return (
    <span className={`confidence-chip ${tone}`}>
      <i />
      {score}% · {confidenceBand(score)}
    </span>
  );
}

export function ConfidenceGauge({ score, band }: { score: number; band?: string }) {
  const normalizedScore = Math.max(0, Math.min(100, Math.round(score)));
  const tone = normalizedScore >= 88 ? "strong" : normalizedScore >= 74 ? "good" : normalizedScore >= 60 ? "moderate" : "weak";
  const evidenceBand = band ?? `${confidenceBand(normalizedScore)} evidence`;

  return (
    <div
      className={`overall-score ${tone}`}
      role="img"
      aria-label={`${normalizedScore}% overall confidence, ${evidenceBand}`}
    >
      <div className="confidence-dial">
        <svg viewBox="0 0 160 160" aria-hidden="true">
          <circle className="confidence-track" cx="80" cy="80" r="68" pathLength="100" />
          <circle
            className="confidence-value"
            cx="80"
            cy="80"
            r="68"
            pathLength="100"
            strokeDasharray="100"
            strokeDashoffset={100 - normalizedScore}
          />
        </svg>
        <div className="confidence-score">
          <b>{normalizedScore}<sup>%</sup></b>
        </div>
      </div>
      <span className="confidence-label">Overall confidence</span>
      <span className="confidence-band"><i />{evidenceBand}</span>
    </div>
  );
}

export function SectionHead({
  title,
  summary,
  confidence,
}: {
  title: string;
  summary: string;
  confidence?: number;
}) {
  return (
    <div className="section-head">
      <div>
        <h2>{title}</h2>
        <p>{summary}</p>
      </div>
      {confidence !== undefined && <ConfidenceChip score={confidence} />}
    </div>
  );
}

export function EvidenceList({ items }: { items: string[] }) {
  if (!items?.length) return null;
  return (
    <div className="evidence-block">
      <span className="evidence-label"><ShieldCheck size={13} /> Evidence</span>
      <ul>
        {items.map((item, index) => (
          <li key={index}>{item}</li>
        ))}
      </ul>
    </div>
  );
}

export function ClassTag({ value }: { value: string }) {
  return <span className={`class-tag ${value}`}>{value}</span>;
}

export function ReasoningNote({ text }: { text?: string }) {
  if (!text) return null;
  return (
    <p className="reasoning-note">
      <span className="reasoning-label">Reasoning</span>
      {text}
    </p>
  );
}

export function UnableToDetermine({ reason }: { reason?: string }) {
  return (
    <div className="unable-note">
      <b>Unable to determine</b>
      <p>{reason ?? "The observed public evidence is insufficient to reach a conclusion for this section."}</p>
    </div>
  );
}
