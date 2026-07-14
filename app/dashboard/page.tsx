"use client";

import { ArrowRight, Bell, ChevronRight, Clock3, FileText, Globe2, Loader2, Plus, ShieldCheck, Sparkles } from "lucide-react";
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

  return (
    <main className="dashboard">
      <AppSidebar active="Dashboard" />
      <section className="dashboard-main">
        <header className="dash-header">
          <div>
            <span className="eyebrow">{greeting()}, {firstName}</span>
            <h1>Your software intelligence.</h1>
          </div>
          <div>
            <button className="icon-button"><Bell size={18} /></button>
            <button className="button primary" onClick={() => router.push("/analyze")}><Plus size={16} /> New analysis</button>
          </div>
        </header>

        <section className="quick-analyze">
          <div><span className="eyebrow">Quick analyze</span><h2>Start with a public URL.</h2></div>
          <button onClick={() => router.push("/analyze")} className="url-ghost">
            <Globe2 size={18} /><span>https://your-product.com</span><ArrowRight size={17} />
          </button>
        </section>

        <section className="stat-grid">
          <Stat icon={<FileText size={18} />} value={String(stats?.completed_reports ?? "—")} label="Reports generated" note={`${stats?.total_analyses ?? 0} analyses run`} />
          <Stat icon={<ShieldCheck size={18} />} value={stats ? `${stats.average_confidence}%` : "—"} label="Avg. confidence" note="Across all reports" />
          <Stat icon={<Sparkles size={18} />} value={String(stats?.favorites ?? "—")} label="Favorites" note="Saved for later" />
        </section>

        <section className="recent-section">
          <div className="subhead">
            <div><span className="eyebrow">Recent reports</span><h2>Keep exploring.</h2></div>
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

function Stat({ icon, value, label, note }: { icon: React.ReactNode; value: string; label: string; note: string }) {
  return (
    <article className="stat-card">
      <span>{icon}</span>
      <strong>{value}</strong>
      <b>{label}</b>
      <small>{note}</small>
    </article>
  );
}

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 12) return "Good morning";
  if (hour < 18) return "Good afternoon";
  return "Good evening";
}
