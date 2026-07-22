"use client";

import {
  ArrowRight, CheckCircle2, ChevronLeft, CircleSlash, Clock3, Cpu, Database, FileSearch,
  Globe2, Layers3, Loader2, Network, ScanSearch, Sparkles, TriangleAlert, XCircle,
} from "lucide-react";
import { useRouter } from "next/navigation";
import { use, useMemo } from "react";
import { api } from "@/lib/api";
import { useAnalysisStream } from "@/lib/useAnalysisStream";
import type { AnalysisEvent } from "@/lib/types";
import { RequireAuth } from "@/components/RequireAuth";
import { OrbitLogo } from "@/components/OrbitLogo";

const PIPELINE: { icon: React.ComponentType<{ size?: number }>; title: string; detail: string; at: number }[] = [
  { icon: Globe2, title: "Opening browser", detail: "Establishing an isolated exploration session", at: 4 },
  { icon: FileSearch, title: "Discovering pages", detail: "Mapping navigable product surfaces", at: 12 },
  { icon: ScanSearch, title: "Exploring navigation", detail: "Following key journeys and capabilities", at: 30 },
  { icon: Network, title: "Recording signals", detail: "Normalizing observable network metadata", at: 60 },
  { icon: Sparkles, title: "Detecting features", detail: "Identifying capabilities from behavior", at: 85 },
  { icon: Layers3, title: "Building knowledge graph", detail: "Connecting evidence into structure", at: 90 },
  { icon: Cpu, title: "Generating architecture", detail: "Inferring the system behind the experience", at: 92 },
  { icon: Database, title: "Writing report", detail: "Synthesizing the engineering report", at: 96 },
];

export default function AnalysisProgress({ params }: { params: Promise<{ id: string }> }) {
  return (
    <RequireAuth>
      <AnalysisProgressInner params={params} />
    </RequireAuth>
  );
}

function AnalysisProgressInner({ params }: { params: Promise<{ id: string }> }) {
  const { id } = use(params);
  const router = useRouter();
  const { events, analysis, connected, error } = useAnalysisStream(id);

  const progress = analysis?.progress ?? 0;
  const status = analysis?.status ?? "queued";
  const isTerminal = ["completed", "failed", "cancelled"].includes(status);
  const activeIndex = useMemo(() => {
    if (status === "completed") return PIPELINE.length;
    const idx = PIPELINE.filter((s) => progress >= s.at).length - 1;
    return Math.max(0, idx);
  }, [progress, status]);

  const reportId =
    analysis?.report_id ??
    (events.find((e) => e.kind === "report.ready")?.payload?.report_id as string | undefined) ??
    null;

  const host = analysis ? new URL(analysis.target_url).hostname : "…";
  const product = host.replace(/^www\./, "").split(".")[0];
  const productLabel = product ? product[0].toUpperCase() + product.slice(1) : "software";

  return (
    <main className="app-shell">
      <header className="app-header">
        <button className="brand button-reset" onClick={() => router.push("/")}>
          <OrbitLogo />orbit
        </button>
        <div className="header-context">
          <span>{statusLabel(status)}</span>
          <button className="avatar" onClick={() => router.push("/settings")}>SC</button>
        </div>
      </header>
      <div className="progress-page">
        <button className="back-link" onClick={() => router.push("/dashboard")}>
          <ChevronLeft size={16} /> Back to dashboard
        </button>
        <div className="progress-hero">
          <div className={`scanning-mark ${isTerminal ? "still" : ""}`}><span /><span /><span /></div>
          <span className="eyebrow">
            {status === "failed" ? <TriangleAlert size={14} /> : <i className="pulse-dot" />}{" "}
            {status === "completed" ? "Analysis complete" : status === "failed" ? "Analysis failed" : status === "cancelled" ? "Analysis cancelled" : "Browser agent working"}
          </span>
          <h1>{status === "completed" ? `${productLabel} understood.` : `Exploring ${productLabel}.`}</h1>
          <p>{analysis?.target_url ?? "Preparing exploration…"}</p>
        </div>

        {error && !analysis && (
          <div className="form-error big"><TriangleAlert size={16} /> {error}</div>
        )}

        <section className="progress-layout">
          <div className="progress-card">
            <div className="progress-meta">
              <span>Exploration progress</span>
              <b>{Math.round(progress)}%</b>
            </div>
            <div className="progress-track"><i style={{ width: `${progress}%` }} className={status === "failed" ? "failed" : ""} /></div>
            <div className="eta">
              <Clock3 size={15} /> {isTerminal ? "Finished" : "Estimated time remaining"}{" "}
              <b>{isTerminal ? statusLabel(status) : progress < 85 ? "~ 1 min" : "Finishing up"}</b>
            </div>
            <div className="step-list">
              {PIPELINE.map((step, index) => {
                const state = index < activeIndex ? "done" : index === activeIndex && !isTerminal ? "current" : index < activeIndex || status === "completed" ? "done" : "";
                const Icon = step.icon;
                return (
                  <div className={`progress-step ${status === "completed" ? "done" : state}`} key={step.title}>
                    <span>{status === "completed" || index < activeIndex ? <CheckCircle2 size={18} /> : status === "failed" && index === activeIndex ? <XCircle size={18} /> : <Icon size={18} />}</span>
                    <div><strong>{step.title}</strong><p>{step.detail}</p></div>
                    {index === activeIndex && !isTerminal && <i className="working">Working</i>}
                  </div>
                );
              })}
            </div>

            {status === "completed" && reportId && (
              <button className="button primary full" onClick={() => router.push(`/report/${reportId}`)}>
                View completed report <ArrowRight size={16} />
              </button>
            )}
            {status === "failed" && (
              <button className="button primary full" onClick={() => router.push("/analyze")}>
                Try another analysis <ArrowRight size={16} />
              </button>
            )}
            {!isTerminal && (
              <button className="button ghost full" onClick={() => api.cancelAnalysis(id)}>
                <CircleSlash size={15} /> Cancel analysis
              </button>
            )}
          </div>

          <aside className="log-card">
            <div className="log-heading">
              <span><i className={connected ? "" : "off"} /> Live signals</span>
              <b>{connected ? "Streaming" : "Reconnecting…"}</b>
            </div>
            <div className="logs">
              {events.length === 0 && <p><Loader2 size={13} className="spin" /> Waiting for the first signal…</p>}
              {events.slice(-14).map((event) => (
                <LogLine key={event.sequence} event={event} />
              ))}
            </div>
          </aside>
        </section>
      </div>
    </main>
  );
}

function LogLine({ event }: { event: AnalysisEvent }) {
  const time = new Date(event.occurred_at).toLocaleTimeString([], { hour12: false });
  const tag = event.kind.split(".")[0].toUpperCase();
  return (
    <p className={event.kind === "report.ready" || event.kind === "analysis.completed" ? "latest" : ""}>
      <time>{time}</time> <em>{tag}</em> {event.message}
    </p>
  );
}

function statusLabel(status: string): string {
  return {
    queued: "Queued",
    running: "Running",
    generating_report: "Generating report",
    completed: "Complete",
    failed: "Failed",
    cancelled: "Cancelled",
  }[status] ?? status;
}
