"use client";

import {
  ArrowUp,
  Bot,
  CheckCircle2,
  Copy,
  FileSearch,
  Lightbulb,
  Loader2,
  ShieldCheck,
  TriangleAlert,
  User,
} from "lucide-react";
import { FormEvent, KeyboardEvent, useMemo, useRef, useState } from "react";
import { api } from "@/lib/api";
import type { CopilotAnswer, CopilotCitation, ReportDocument } from "@/lib/types";

type Architecture = ReportDocument["architecture"];
type Message =
  | { id: string; role: "user"; text: string }
  | { id: string; role: "assistant"; text: string; result: CopilotAnswer };

const STARTERS = [
  "How does authentication probably work?",
  "What suggests this product uses optimistic updates?",
  "Show all billing-related endpoints.",
  "What parts of this architecture are uncertain?",
  "Generate a system-design interview explanation.",
  "What would I need to build a similar workflow?",
];

type LocalRecord = {
  section: string;
  title: string;
  detail: string;
  evidence: string;
  classification: "observed" | "inferred";
  confidence: number;
};

function localRecords(document?: ReportDocument, architecture?: Architecture): LocalRecord[] {
  const arch = document?.architecture ?? architecture;
  if (!arch) return [];
  const records: LocalRecord[] = [];
  arch.nodes.forEach((node) => records.push({
    section: "Architecture",
    title: node.label,
    detail: [node.role, ...(node.responsibilities ?? [])].filter(Boolean).join(" · "),
    evidence: node.evidence?.[0] ?? arch.evidence[0] ?? node.role ?? "Architecture model record",
    classification: node.classification ?? "inferred",
    confidence: node.confidence,
  }));
  arch.connections?.forEach((connection) => records.push({
    section: "Architecture",
    title: `${connection.from} → ${connection.to}`,
    detail: `${connection.label} over ${connection.protocol}`,
    evidence: connection.evidence[0] ?? connection.label,
    classification: connection.classification,
    confidence: connection.confidence,
  }));
  arch.request_flows?.forEach((flow) => records.push({
    section: "Request flow",
    title: flow.name,
    detail: `${flow.steps.join(" → ")} via ${flow.transport}`,
    evidence: flow.evidence[0] ?? flow.transport,
    classification: flow.classification,
    confidence: flow.confidence,
  }));
  arch.patterns?.forEach((pattern) => records.push({
    section: "Architecture pattern",
    title: pattern.title,
    detail: pattern.detail,
    evidence: pattern.evidence[0] ?? pattern.detail,
    classification: pattern.classification,
    confidence: pattern.confidence,
  }));
  arch.unknowns?.forEach((unknown) => records.push({
    section: "Architecture uncertainty",
    title: "Unresolved detail",
    detail: unknown,
    evidence: unknown,
    classification: "inferred",
    confidence: 25,
  }));
  document?.api.endpoints.forEach((endpoint) => records.push({
    section: "API",
    title: `${endpoint.method} ${endpoint.path}`,
    detail: endpoint.note,
    evidence: endpoint.note || endpoint.path,
    classification: "observed",
    confidence: endpoint.confidence,
  }));
  document?.features.items.forEach((feature) => records.push({
    section: "Feature",
    title: feature.name,
    detail: feature.description,
    evidence: feature.evidence[0] ?? feature.description,
    classification: feature.classification === "observed" ? "observed" : "inferred",
    confidence: feature.confidence,
  }));
  document?.insights.items.forEach((insight) => records.push({
    section: "Engineering insight",
    title: insight.title,
    detail: insight.detail,
    evidence: insight.detail,
    classification: insight.classification === "observed" ? "observed" : "inferred",
    confidence: insight.confidence,
  }));
  document?.integrations.items.forEach((integration) => records.push({
    section: "Integration",
    title: integration.name,
    detail: integration.category,
    evidence: integration.evidence[0] ?? integration.category,
    classification: "observed",
    confidence: integration.confidence,
  }));
  return records;
}

function selectRecords(records: LocalRecord[], query: string, limit = 5) {
  const terms = query.toLowerCase().match(/[a-z0-9][a-z0-9._/-]+/g) ?? [];
  return records
    .map((record) => ({
      record,
      score: terms.reduce((score, term) => score + (`${record.section} ${record.title} ${record.detail} ${record.evidence}`.toLowerCase().includes(term) ? 4 : 0), 0) + record.confidence / 25,
    }))
    .sort((a, b) => b.score - a.score)
    .slice(0, limit)
    .map(({ record }) => record);
}

function cite(records: LocalRecord[]) {
  return records.map<CopilotCitation>((record, index) => ({
    id: `E${index + 1}`,
    section: record.section,
    title: record.title,
    evidence: record.evidence,
    classification: record.classification,
    confidence: Math.round(record.confidence),
  }));
}

function localAnswer(question: string, document?: ReportDocument, architecture?: Architecture): CopilotAnswer {
  const all = localRecords(document, architecture);
  const lower = question.toLowerCase();
  let selected: LocalRecord[] = [];
  let answer = "";
  let followups: string[] = [];

  if (/(uncertain|uncertainty|unknown|not sure)/.test(lower)) {
    selected = all.filter((record) => record.section === "Architecture uncertainty" || record.classification === "inferred").sort((a, b) => a.confidence - b.confidence).slice(0, 6);
    answer = selected.length
      ? `The least certain parts are ${selected.map((record, index) => `${record.detail || record.title} [E${index + 1}]`).join(" ")}`
      : "This report contains no explicit uncertainty records. That does not prove the private architecture is fully known.";
    followups = ["What evidence would reduce these uncertainties?", "Show the inferred connections"];
  } else if (/(billing|payment|checkout|subscription|invoice)/.test(lower)) {
    selected = all.filter((record) => /(billing|payment|checkout|subscription|invoice|stripe)/i.test(`${record.title} ${record.detail} ${record.evidence}`)).slice(0, 6);
    const endpoints = selected.filter((record) => record.section === "API");
    answer = endpoints.length
      ? `The captured billing-related endpoints are ${endpoints.map((record) => `${record.title} [E${selected.indexOf(record) + 1}]`).join(", ")}.`
      : "No billing-specific endpoint path was directly captured. ";
    const signals = selected.filter((record) => record.section !== "API");
    if (signals.length) answer += ` Supporting signals include ${signals.map((record) => `${record.title} [E${selected.indexOf(record) + 1}]`).join(", ")}.`;
    if (!selected.length) answer = "No billing endpoints or provider signals were captured, so Orbit cannot responsibly infer a billing API.";
    followups = ["How does checkout probably work?", "What billing evidence is missing?"];
  } else if (/(system.?design|interview|explain.*architecture)/.test(lower)) {
    selected = selectRecords(all, "architecture request flow api realtime worker database", 6);
    answer = `For a system-design interview, describe the product from the outside in: ${selected.map((record, index) => `${record.title} — ${record.detail} [E${index + 1}]`).join(" ")} Keep observed protocols separate from inferred private services.`;
    followups = ["Turn this into a 60-second explanation", "What tradeoffs does the architecture imply?"];
  } else if (/\b(auth|authentication|login|identity|session)\b|\bsign[ -]?in\b/.test(lower)) {
    selected = all.filter((record) => /(auth|login|identity|session|oauth)/i.test(`${record.title} ${record.detail} ${record.evidence}`)).slice(0, 5);
    if (!selected.length) selected = selectRecords(all, "permissions identity architecture", 3);
    answer = "Authentication probably crosses a browser-to-identity trust boundary, but private token validation and session storage are not directly visible. " + selected.map((record, index) => `${record.classification === "observed" ? "Observed" : "Inferred"}: ${record.title} — ${record.detail} [E${index + 1}]`).join(" ");
    followups = ["Which authentication details remain uncertain?", "Explain the sign-in trust boundaries"];
  } else if (/(build|implement|similar workflow|recreate)/.test(lower)) {
    selected = selectRecords(all, `${question} workflow feature api`, 6);
    answer = `To build a similar workflow, begin with the cited product contract: ${selected.slice(0, 4).map((record, index) => `${record.title} — ${record.detail} [E${index + 1}]`).join(" ")} Implementation inference: model the core state and permissions, expose the required API operations, and add realtime or background processing only where the observed behavior needs it.`;
    followups = ["Draft the API contract", "List the core entities I would need"];
  } else {
    selected = selectRecords(all, question, 5);
    answer = selected.length
      ? `The strongest matching report evidence is ${selected.map((record, index) => `${record.title} — ${record.detail} [E${index + 1}]`).join(" ")}`
      : "This report does not contain enough evidence to answer that question.";
    followups = ["Which parts of that answer are inferred?", "Show the architecture evidence"];
  }

  const classifications = new Set(selected.map((record) => record.classification));
  const basis = selected.length === 0 ? "insufficient" : classifications.size > 1 ? "mixed" : selected[0].classification;
  return {
    answer,
    basis,
    confidence: selected.length ? Math.round(selected.reduce((sum, record) => sum + record.confidence, 0) / selected.length) : 0,
    citations: cite(selected),
    limitations: ["Observed means directly supported by this report. Inferred means a likely explanation, not a verified private implementation detail."],
    followups,
  };
}

function answerParagraphs(answer: string) {
  return answer.split(/(?<=\.)\s+(?=[A-Z])/).filter(Boolean);
}

export function AskOrbit({
  productName,
  reportId,
  document,
  architecture,
}: {
  productName: string;
  reportId?: string;
  document?: ReportDocument;
  architecture?: Architecture;
}) {
  const [question, setQuestion] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const suggestions = useMemo(() => {
    const last = [...messages].reverse().find((message): message is Extract<Message, { role: "assistant" }> => message.role === "assistant");
    return last?.result.followups.length ? last.result.followups : STARTERS;
  }, [messages]);

  const ask = async (prompt: string) => {
    const value = prompt.trim();
    if (!value || loading) return;
    const userMessage: Message = { id: `user-${Date.now()}`, role: "user", text: value };
    setMessages((current) => [...current, userMessage]);
    setQuestion("");
    setLoading(true);
    let result: CopilotAnswer;
    try {
      result = reportId ? await api.askReport(reportId, value) : localAnswer(value, document, architecture);
    } catch {
      result = localAnswer(value, document, architecture);
    }
    setMessages((current) => [...current, { id: `orbit-${Date.now()}`, role: "assistant", text: result.answer, result }]);
    setLoading(false);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    void ask(question);
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void ask(question);
    }
  };

  const copyAnswer = async (message: Extract<Message, { role: "assistant" }>) => {
    await navigator.clipboard.writeText(`${message.text}\n\n${message.result.citations.map((citation) => `[${citation.id}] ${citation.title}: ${citation.evidence}`).join("\n")}`);
    setCopied(message.id);
    window.setTimeout(() => setCopied(null), 1500);
  };

  return (
    <section className="ask-orbit-panel">
      <header className="ask-orbit-head">
        <div className="ask-orbit-mark"><Bot size={22} /></div>
        <div>
          <h2>Ask Orbit about {productName}</h2>
          <p>Answers cite this report’s evidence and label uncertainty.</p>
        </div>
      </header>

      {messages.length === 0 ? (
        <div className="ask-orbit-empty">
          <div className="ask-orbit-empty-copy">
            <FileSearch size={24} />
            <h3>Start with an engineering question</h3>
          </div>
          <div className="ask-orbit-starters">
            {STARTERS.map((starter) => <button key={starter} onClick={() => void ask(starter)}><Lightbulb size={14} /><span>{starter}</span><ArrowUp size={13} /></button>)}
          </div>
        </div>
      ) : (
        <div className="ask-orbit-thread" aria-live="polite">
          {messages.map((message) => message.role === "user" ? (
            <article className="ask-message user" key={message.id}><span><User size={14} /></span><p>{message.text}</p></article>
          ) : (
            <article className="ask-message orbit" key={message.id}>
              <div className="ask-message-avatar"><Bot size={15} /></div>
              <div className="ask-answer">
                <div className="ask-answer-meta"><span className={`ask-basis ${message.result.basis}`}><i />{message.result.basis}</span><b>{message.result.confidence}% answer confidence</b><button onClick={() => void copyAnswer(message)}>{copied === message.id ? <CheckCircle2 size={13} /> : <Copy size={13} />}{copied === message.id ? "Copied" : "Copy"}</button></div>
                <div className="ask-answer-copy">{answerParagraphs(message.text).map((paragraph, index) => <p key={index}>{paragraph}</p>)}</div>
                {!!message.result.citations.length && (
                  <div className="ask-citations">
                    <span>Evidence used</span>
                    {message.result.citations.map((citation) => (
                      <article key={citation.id}>
                        <b>{citation.id}</b>
                        <div><strong>{citation.title}</strong><small>{citation.section}</small><p>{citation.evidence}</p></div>
                        <em className={citation.classification}>{citation.classification} · {citation.confidence}%</em>
                      </article>
                    ))}
                  </div>
                )}
                {!!message.result.limitations.length && <div className="ask-limit"><TriangleAlert size={13} /><p>{message.result.limitations[0]}</p></div>}
              </div>
            </article>
          ))}
          {loading && <article className="ask-message orbit loading"><div className="ask-message-avatar"><Bot size={15} /></div><div><Loader2 className="spin" size={16} /><span>Tracing report evidence…</span></div></article>}
        </div>
      )}

      <div className="ask-orbit-compose-wrap">
        {messages.length > 0 && <div className="ask-followups">{suggestions.slice(0, 3).map((suggestion) => <button key={suggestion} onClick={() => void ask(suggestion)}>{suggestion}</button>)}</div>}
        <form className="ask-orbit-compose" onSubmit={submit}>
          <textarea ref={inputRef} value={question} onChange={(event) => setQuestion(event.target.value)} onKeyDown={onKeyDown} maxLength={600} rows={1} placeholder={`Ask about ${productName}'s architecture, flows, APIs, or evidence…`} />
          <div><span>{question.length}/600 · Shift+Enter for a new line</span><button type="submit" disabled={!question.trim() || loading} aria-label="Ask Orbit"><ArrowUp size={16} /></button></div>
        </form>
        <p className="ask-orbit-disclaimer"><ShieldCheck size={11} /> Answers are constrained to this report. Orbit will say when the evidence is insufficient.</p>
      </div>
    </section>
  );
}
