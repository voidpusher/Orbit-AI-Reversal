"use client";

import { ArrowRight, GitCompareArrows, Layers3, Loader2, Plus, Sparkles, TriangleAlert } from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { Suspense, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { AppSidebar } from "@/components/AppSidebar";
import { RequireAuth } from "@/components/RequireAuth";
import type { CompareSide, Comparison, TechDiffItem } from "@/lib/types";

function CompareInner() {
  const router = useRouter();
  const params = useSearchParams();
  const [a, setA] = useState(params.get("a") ?? "");
  const [b, setB] = useState(params.get("b") ?? "");

  const { data: reports } = useQuery({ queryKey: ["reports", {}], queryFn: () => api.listReports() });
  const options = reports?.items ?? [];

  // Default to the two most recent reports when arriving without a selection.
  useEffect(() => {
    if (!a && !b && options.length >= 2) {
      setA(options[0].id);
      setB(options[1].id);
    }
  }, [options, a, b]);

  const ready = a && b && a !== b;
  const { data, isLoading, error } = useQuery({
    queryKey: ["compare", a, b],
    queryFn: () => api.compare(a, b),
    enabled: Boolean(ready),
  });

  return (
    <main className="dashboard">
      <AppSidebar active="Compare" />
      <section className="dashboard-main">
        <header className="dash-header">
          <div><span className="eyebrow">Compare mode</span><h1>Compare software.</h1></div>
          <button className="button primary" onClick={() => router.push("/analyze")}><Plus size={16} /> New analysis</button>
        </header>

        {options.length < 2 ? (
          <div className="empty-state" style={{ marginTop: 32 }}>
            <div className="empty-mark"><GitCompareArrows size={22} /></div>
            <h3>Analyze at least two products</h3>
            <p>Compare mode contrasts the technology, features, and architecture of two reports side by side.</p>
            <button className="button primary" onClick={() => router.push("/analyze")}><Plus size={16} /> New analysis</button>
          </div>
        ) : (
          <>
            <div className="compare-pickers">
              <Picker label="Product A" value={a} onChange={setA} options={options} tone="a" />
              <span className="compare-vs"><GitCompareArrows size={18} /></span>
              <Picker label="Product B" value={b} onChange={setB} options={options} tone="b" />
            </div>

            {a === b && a && <div className="form-error big"><TriangleAlert size={15} /> Choose two different reports to compare.</div>}
            {isLoading && ready && <div className="table-loading"><Loader2 size={18} className="spin" /> Building comparison…</div>}
            {error && <div className="form-error big"><TriangleAlert size={15} /> {error instanceof Error ? error.message : "Comparison failed"}</div>}
            {data && ready && <ComparisonView data={data} />}
          </>
        )}
      </section>
    </main>
  );
}

function ComparisonView({ data }: { data: Comparison }) {
  return (
    <>
      <div className="compare-banner">
        <Sparkles size={16} />
        <p>{data.headline}</p>
        <div className="similarity-pill"><b>{data.similarity}%</b><span>similarity</span></div>
      </div>

      <div className="compare-heads">
        <SideCard side={data.a} tone="a" />
        <div className="compare-delta">
          <span className="eyebrow">Confidence Δ</span>
          <b className={data.confidence_delta >= 0 ? "pos" : "neg"}>
            {data.confidence_delta > 0 ? "+" : ""}{data.confidence_delta}
          </b>
        </div>
        <SideCard side={data.b} tone="b" />
      </div>

      <DiffBlock
        title="Technology stack"
        icon={<Layers3 size={15} />}
        onlyA={data.only_a_tech.map(techLabel)}
        shared={data.shared_tech.map(techLabel)}
        onlyB={data.only_b_tech.map(techLabel)}
        nameA={data.a.product_name}
        nameB={data.b.product_name}
      />
      <DiffBlock
        title="Feature surface"
        icon={<Sparkles size={15} />}
        onlyA={data.only_a_features}
        shared={data.shared_features}
        onlyB={data.only_b_features}
        nameA={data.a.product_name}
        nameB={data.b.product_name}
      />

      <div className="compare-arch">
        <div className="section-head" style={{ marginBottom: 18 }}>
          <div><span className="eyebrow">System shape</span><h2>Architecture</h2></div>
        </div>
        <div className="compare-arch-grid">
          <ArchRow name={data.a.product_name} nodes={data.architecture_a} tone="a" />
          <ArchRow name={data.b.product_name} nodes={data.architecture_b} tone="b" />
        </div>
      </div>

      {data.shared_insights.length > 0 && (
        <div className="compare-insights">
          <span className="eyebrow">Shared engineering insights</span>
          <div className="rel-list" style={{ marginTop: 12 }}>
            {data.shared_insights.map((insight) => (
              <span className="rel-chip" key={insight}>{insight}</span>
            ))}
          </div>
        </div>
      )}
    </>
  );
}

function techLabel(item: TechDiffItem): string {
  return `${item.name} · ${item.confidence}%`;
}

function Picker({
  label, value, onChange, options, tone,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: { id: string; product_name: string; target_url: string }[];
  tone: "a" | "b";
}) {
  return (
    <label className={`compare-picker ${tone}`}>
      <span className="eyebrow">{label}</span>
      <select value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">Select a report…</option>
        {options.map((opt) => (
          <option key={opt.id} value={opt.id}>{opt.product_name} — {new URL(opt.target_url).hostname}</option>
        ))}
      </select>
    </label>
  );
}

function SideCard({ side, tone }: { side: CompareSide; tone: "a" | "b" }) {
  return (
    <article className={`compare-side ${tone}`}>
      <div className="compare-side-top">
        <span className="product-badge">{side.product_name[0]?.toUpperCase()}</span>
        <div><b>{side.product_name}</b><small>{side.host}</small></div>
      </div>
      <div className="compare-side-metrics">
        <Metric value={`${side.overall_confidence}%`} label="Confidence" />
        <Metric value={String(side.technologies_count)} label="Tech" />
        <Metric value={String(side.features_count)} label="Features" />
        <Metric value={String(side.pages_explored)} label="Pages" />
      </div>
    </article>
  );
}

function Metric({ value, label }: { value: string; label: string }) {
  return <div className="compare-metric"><strong>{value}</strong><small>{label}</small></div>;
}

function DiffBlock({
  title, icon, onlyA, shared, onlyB, nameA, nameB,
}: {
  title: string;
  icon: React.ReactNode;
  onlyA: string[];
  shared: string[];
  onlyB: string[];
  nameA: string;
  nameB: string;
}) {
  return (
    <div className="diff-block">
      <div className="diff-block-head">{icon} <b>{title}</b></div>
      <div className="diff-columns">
        <DiffColumn heading={`Only ${nameA}`} items={onlyA} tone="a" />
        <DiffColumn heading="Shared" items={shared} tone="shared" />
        <DiffColumn heading={`Only ${nameB}`} items={onlyB} tone="b" />
      </div>
    </div>
  );
}

function DiffColumn({ heading, items, tone }: { heading: string; items: string[]; tone: string }) {
  return (
    <div className={`diff-column ${tone}`}>
      <span className="diff-column-head">{heading} <em>{items.length}</em></span>
      <div className="diff-chips">
        {items.length === 0 ? <span className="diff-empty">—</span> : items.map((item) => <span className="diff-chip" key={item}>{item}</span>)}
      </div>
    </div>
  );
}

function ArchRow({ name, nodes, tone }: { name: string; nodes: string[]; tone: "a" | "b" }) {
  return (
    <div className={`arch-row ${tone}`}>
      <span className="arch-row-name">{name}</span>
      <div className="arch-row-nodes">
        {nodes.map((node, index) => (
          <span className="arch-row-node" key={node}>
            {node}
            {index < nodes.length - 1 && <ArrowRight size={13} />}
          </span>
        ))}
      </div>
    </div>
  );
}

export default function ComparePage() {
  return (
    <RequireAuth>
      <Suspense fallback={null}>
        <CompareInner />
      </Suspense>
    </RequireAuth>
  );
}
