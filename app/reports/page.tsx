"use client";

import { ChevronRight, GitCompareArrows, Loader2, Plus, Search, Sparkles, Star, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "@/lib/api";
import { AppSidebar } from "@/components/AppSidebar";
import { RequireAuth } from "@/components/RequireAuth";
import type { ReportListItem } from "@/lib/types";

export default function ReportsPage() {
  return (
    <RequireAuth>
      <ReportsInner />
    </RequireAuth>
  );
}

function ReportsInner() {
  const router = useRouter();
  const qc = useQueryClient();
  const [q, setQ] = useState("");
  const [favorite, setFavorite] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["reports", { q, favorite }],
    queryFn: () => api.listReports({ q: q || undefined, favorite }),
  });

  const toggleFavorite = useMutation({
    mutationFn: ({ id, value }: { id: string; value: boolean }) => api.updateReport(id, { is_favorite: value }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["reports"] }),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api.deleteReport(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["reports"] });
      qc.invalidateQueries({ queryKey: ["stats"] });
    },
  });

  const items = data?.items ?? [];

  return (
    <main className="dashboard">
      <AppSidebar active="Reports" />
      <section className="dashboard-main">
        <header className="dash-header">
          <div><span className="eyebrow">Saved reports</span><h1>Reports.</h1></div>
          <button className="button primary" onClick={() => router.push("/analyze")}><Plus size={16} /> New analysis</button>
        </header>

        <div className="reports-toolbar">
          <div className="search-field">
            <Search size={17} />
            <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search by product, URL, or headline…" />
          </div>
          <button className={`filter-chip ${favorite ? "on" : ""}`} onClick={() => setFavorite((v) => !v)}>
            <Star size={15} fill={favorite ? "currentColor" : "none"} /> Favorites
          </button>
          {items.length >= 2 && (
            <button className="filter-chip" onClick={() => router.push("/compare")}>
              <GitCompareArrows size={15} /> Compare
            </button>
          )}
        </div>

        {isLoading ? (
          <div className="table-loading"><Loader2 size={18} className="spin" /> Loading reports…</div>
        ) : items.length === 0 ? (
          <div className="empty-state">
            <div className="empty-mark"><Sparkles size={22} /></div>
            <h3>{q || favorite ? "No matching reports" : "No reports yet"}</h3>
            <p>{q || favorite ? "Try a different search or clear your filters." : "Analyze a product to generate your first report."}</p>
            <button className="button primary" onClick={() => router.push("/analyze")}><Plus size={16} /> New analysis</button>
          </div>
        ) : (
          <div className="saved-reports-grid">
            {items.map((report) => (
              <ReportCard
                key={report.id}
                report={report}
                onOpen={() => router.push(`/report/${report.id}`)}
                onFavorite={() => toggleFavorite.mutate({ id: report.id, value: !report.is_favorite })}
                onDelete={() => remove.mutate(report.id)}
              />
            ))}
          </div>
        )}
      </section>
    </main>
  );
}

function ReportCard({
  report, onOpen, onFavorite, onDelete,
}: {
  report: ReportListItem;
  onOpen: () => void;
  onFavorite: () => void;
  onDelete: () => void;
}) {
  return (
    <article className="report-card-lg">
      <div className="report-card-top">
        <span className="product-badge">{report.product_name[0]?.toUpperCase()}</span>
        <div className="report-card-actions">
          <button className={`icon-button sm ${report.is_favorite ? "starred" : ""}`} aria-label="Favorite" onClick={onFavorite}>
            <Star size={15} fill={report.is_favorite ? "currentColor" : "none"} />
          </button>
          <button className="icon-button sm" aria-label="Delete" onClick={onDelete}><Trash2 size={15} /></button>
        </div>
      </div>
      <button className="report-card-body button-reset" onClick={onOpen}>
        <b>{report.product_name}</b>
        <small>{new URL(report.target_url).hostname}</small>
        <p>{report.headline}</p>
      </button>
      <div className="report-card-foot">
        <span className="confidence-text">{report.overall_confidence}% confidence</span>
        <button className="text-action sm" onClick={onOpen}>Open <ChevronRight size={14} /></button>
      </div>
    </article>
  );
}
