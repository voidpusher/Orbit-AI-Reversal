"use client";

import { ArrowRight, ArrowUpRight, ChevronRight, FileText, Globe2, Loader2, Plus, ShieldCheck, Sparkles } from "lucide-react";
import { useState } from "react";
import { useRouter } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { AppSidebar } from "@/components/AppSidebar";
import { RequireAuth } from "@/components/RequireAuth";
import type { ReportListItem } from "@/lib/types";

export default function DashboardPage() {
  return (
    <RequireAuth>
      <DashboardInner />
    </RequireAuth>
  );
}

function DashboardInner() {
  const router = useRouter();
  const { data: me } = useQuery({ queryKey: ["me"], queryFn: api.me, staleTime: Infinity });
  const { data: stats } = useQuery({ queryKey: ["stats"], queryFn: api.stats });
  const { data: reports, isLoading } = useQuery({ queryKey: ["reports", { recent: true }], queryFn: () => api.listReports() });

  const recent = reports?.items.slice(0, 6) ?? [];
  const firstName = me?.name?.split(" ")[0] ?? "there";
  const [url, setUrl] = useState("");
  const investigate = () => router.push(`/analyze${url.trim() ? `?url=${encodeURIComponent(url.trim())}` : ""}`);

  return (
    <main className="dashboard future-dashboard">
      <AppSidebar active="Dashboard" />
      <section className="dashboard-main">
        <header className="dash-header">
          <div>
            <h1>{greeting()}, {firstName}.</h1>
          </div>
          <div>
            <button className="button ghost" onClick={() => router.push("/report/demo")}>Explore demo <ArrowUpRight size={16} /></button>
          </div>
        </header>

        <section className="investigation-stage">
          <div className="investigation-command">
            <h2>Go beneath<br />the <em>interface.</em></h2>
            <p>Explore a product’s architecture and workflows.</p>
            <form className="investigation-input" onSubmit={(event) => { event.preventDefault(); investigate(); }}>
              <Globe2 size={18} />
              <input aria-label="Product URL to investigate" value={url} onChange={(event) => setUrl(event.target.value)} placeholder="Paste a product URL" />
              <button type="submit" aria-label="Start investigation"><ArrowUpRight size={22} /></button>
            </form>
          </div>
          <div className="system-sculpture" aria-hidden="true">
            <svg viewBox="0 0 440 320" className="sculpture-lines">
              <ellipse cx="220" cy="160" rx="165" ry="62" transform="rotate(-30 220 160)" />
              <ellipse cx="220" cy="160" rx="165" ry="62" transform="rotate(30 220 160)" />
              <circle cx="220" cy="160" r="100" />
              <path d="M40 160H400M220 20V300" className="sculpture-guides" />
              <circle cx="220" cy="160" r="35" className="sculpture-core" />
              <circle cx="220" cy="160" r="6" className="sculpture-dot" />
              <circle cx="98" cy="104" r="4" className="sculpture-dot" />
              <circle cx="346" cy="214" r="4" className="sculpture-dot" />
            </svg>
          </div>
        </section>

        <section className="stat-grid">
          <Stat icon={<FileText size={18} />} value={String(stats?.completed_reports ?? "—")} label="Reports generated" />
          <Stat icon={<ShieldCheck size={18} />} value={stats ? `${stats.average_confidence}%` : "—"} label="Avg. confidence" />
          <Stat icon={<Sparkles size={18} />} value={String(stats?.favorites ?? "—")} label="Favorites" />
        </section>

        <section className="recent-section">
          <div className="subhead">
            <div><h2>Recent reports</h2></div>
            <button className="text-action" onClick={() => router.push("/reports")}>View all <ArrowRight size={15} /></button>
          </div>

          {isLoading ? (
            <div className="table-loading"><Loader2 size={18} className="spin" /> Loading reports…</div>
          ) : recent.length === 0 ? (
            <EmptyState onStart={() => router.push("/analyze")} />
          ) : (
            <div className="report-table">
              <div className="table-head"><span>PRODUCT</span><span>ANALYZED</span><span>CONFIDENCE</span><span>STATUS</span><span /></div>
              {recent.map((report) => (
                <ReportRow key={report.id} report={report} onOpen={() => router.push(`/report/${report.id}`)} />
              ))}
            </div>
          )}
        </section>
      </section>
    </main>
  );
}

function ReportRow({ report, onOpen }: { report: ReportListItem; onOpen: () => void }) {
  return (
    <button className="table-row" onClick={onOpen}>
      <span className="product-cell">
        <i>{report.product_name[0]?.toUpperCase()}</i>
        <b>{report.product_name}<small>{new URL(report.target_url).hostname}</small></b>
      </span>
      <span>{new Date(report.published_at).toLocaleDateString()}</span>
      <span><b className="confidence-text">{report.overall_confidence}%</b></span>
      <span><em className="complete-dot" /> Complete</span>
      <ChevronRight size={16} />
    </button>
  );
}

function EmptyState({ onStart }: { onStart: () => void }) {
  return (
    <div className="empty-state">
      <div className="empty-mark"><Sparkles size={22} /></div>
      <h3>No reports yet</h3>
      <p>Analyze your first SaaS product to generate an evidence-backed engineering report.</p>
      <button className="button primary" onClick={onStart}><Plus size={16} /> New analysis</button>
    </div>
  );
}

function Stat({ icon, value, label }: { icon: React.ReactNode; value: string; label: string }) {
  return (
    <article className="stat-card">
      <span>{icon}</span>
      <strong>{value}</strong>
      <b>{label}</b>
    </article>
  );
}

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}
