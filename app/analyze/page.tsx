"use client";

import {
  ArrowLeft, ArrowRight, Check, FileUp, Globe2, Loader2, LockKeyhole,
  Network, Settings2, ShieldCheck, TriangleAlert, X,
} from "lucide-react";
import { useRouter, useSearchParams } from "next/navigation";
import { useMutation } from "@tanstack/react-query";
import { ChangeEvent, DragEvent, Suspense, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { ParsedHar, parseAndSanitizeHar } from "@/lib/har";
import { RequireAuth } from "@/components/RequireAuth";
import { OrbitLogo } from "@/components/OrbitLogo";

type AnalysisMode = "live" | "har";

function AnalyzeInner() {
  const router = useRouter();
  const params = useSearchParams();
  const fileInput = useRef<HTMLInputElement>(null);
  const [mode, setMode] = useState<AnalysisMode>("live");
  const [url, setUrl] = useState(params.get("url") ?? "");
  const [deep, setDeep] = useState(false);
  const [network, setNetwork] = useState(true);
  const [pages, setPages] = useState("20");
  const [har, setHar] = useState<ParsedHar | null>(null);
  const [harError, setHarError] = useState<string | null>(null);
  const [readingHar, setReadingHar] = useState(false);
  const [dragging, setDragging] = useState(false);

  const mutation = useMutation({
    mutationFn: () => mode === "har" && har
      ? api.importHarAnalysis(har.payload)
      : api.createAnalysis(normalize(url), {
          deep_crawl: deep,
          max_pages: Number(pages),
          capture_network_requests: network,
        }),
    onSuccess: (analysis) => router.push(`/analysis/${analysis.id}`),
  });

  const canSubmit = mode === "har" ? Boolean(har) : Boolean(url.trim());
  const submit = () => {
    if (!canSubmit || mutation.isPending || readingHar) return;
    mutation.mutate();
  };

  const loadHar = async (file?: File) => {
    if (!file) return;
    setReadingHar(true);
    setHarError(null);
    try {
      setHar(await parseAndSanitizeHar(file));
    } catch (error) {
      setHar(null);
      setHarError(error instanceof Error ? error.message : "The HAR file could not be read.");
    } finally {
      setReadingHar(false);
    }
  };

  const onFile = (event: ChangeEvent<HTMLInputElement>) => loadHar(event.target.files?.[0]);
  const onDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setDragging(false);
    loadHar(event.dataTransfer.files?.[0]);
  };

  const requestError = mutation.error instanceof ApiError
    ? mutation.error.message
    : mutation.error ? "Something went wrong. Please try again." : null;
  const error = harError || requestError;

  return (
    <main className="app-shell">
      <header className="app-header">
        <button className="brand button-reset" onClick={() => router.push("/")}>
          <OrbitLogo />orbit
        </button>
        <div className="header-context">
          <span>New analysis</span>
          <button className="avatar" aria-label="Account menu" onClick={() => router.push("/settings")}>SC</button>
        </div>
      </header>
      <div className="setup-page">
        <button className="back-link" onClick={() => router.push("/dashboard")}><ArrowLeft size={16} /> Dashboard</button>
        <div className="setup-copy">
          <span className="eyebrow">New exploration</span>
          <h1>What software should<br />Orbit understand?</h1>
          <p>Analyze a public URL live, or import a browser session when authentication and bot protection hide the real product surface.</p>
        </div>

        <div className="analysis-mode-tabs" role="tablist" aria-label="Evidence source">
          <button role="tab" aria-selected={mode === "live"} className={mode === "live" ? "active" : ""} onClick={() => setMode("live")}>
            <Globe2 size={16} /><span><b>Live URL</b><small>Public product surface</small></span>
          </button>
          <button role="tab" aria-selected={mode === "har"} className={mode === "har" ? "active" : ""} onClick={() => setMode("har")}>
            <Network size={16} /><span><b>Browser HAR</b><small>Authenticated product evidence</small></span>
          </button>
        </div>

        {mode === "live" ? (
          <section className="setup-card">
            <label className="field-label" htmlFor="url">Software URL</label>
            <div className="url-field">
              <Globe2 size={19} />
              <input id="url" autoFocus value={url} onChange={(e) => setUrl(e.target.value)} onKeyDown={(e) => e.key === "Enter" && submit()} placeholder="https://linear.app" />
              <SubmitButton pending={mutation.isPending} disabled={!canSubmit} onClick={submit} />
            </div>
            <div className="example-links">
              <span>Try an example</span>
              {["https://linear.app", "https://supabase.com", "https://stripe.com"].map((sample) => (
                <button key={sample} onClick={() => setUrl(sample)}>{sample.replace("https://", "")}</button>
              ))}
            </div>
            {error && <div className="form-error"><TriangleAlert size={15} /> {error}</div>}
          </section>
        ) : (
          <section className="setup-card har-card">
            <div className="har-card-head">
              <div><span className="field-label">Browser session</span><p>Upload a HAR exported after using the product normally.</p></div>
              <span className="local-processing"><ShieldCheck size={13} /> Sanitized locally</span>
            </div>
            <input ref={fileInput} type="file" accept=".har,application/json" onChange={onFile} hidden />
            {har ? (
              <div className="har-file-ready">
                <div className="har-file-icon"><Network size={20} /></div>
                <div><b>{har.filename}</b><span>{har.payload.entries.length} safe entries from {har.originalEntries} requests · {new URL(har.payload.target_url).host}</span></div>
                <button aria-label="Remove HAR" onClick={() => { setHar(null); if (fileInput.current) fileInput.current.value = ""; }}><X size={16} /></button>
              </div>
            ) : (
              <div
                className={`har-dropzone ${dragging ? "dragging" : ""}`}
                onDragOver={(event) => { event.preventDefault(); setDragging(true); }}
                onDragLeave={() => setDragging(false)}
                onDrop={onDrop}
                onClick={() => fileInput.current?.click()}
              >
                {readingHar ? <Loader2 size={25} className="spin" /> : <FileUp size={25} />}
                <b>{readingHar ? "Removing sensitive data…" : "Drop your .har file here"}</b>
                <span>or click to browse · up to 100 MB</span>
              </div>
            )}
            <div className="har-privacy-note">
              <LockKeyhole size={17} />
              <p><b>Your raw HAR never leaves this browser.</b> Orbit discards cookies, authorization headers, query strings, form data, and all request/response bodies before upload.</p>
            </div>
            {error && <div className="form-error"><TriangleAlert size={15} /> {error}</div>}
            <SubmitButton pending={mutation.isPending} disabled={!canSubmit || readingHar} onClick={submit} wide label="Analyze browser evidence" />
          </section>
        )}

        {mode === "live" ? (
          <section className="options-card">
            <div className="options-heading"><div><span className="eyebrow">Exploration settings</span><h2>Fine-tune the scope</h2></div><Settings2 size={19} /></div>
            <div className="option-list">
              <Toggle title="Deep crawl" detail="Follow primary navigation and linked product pages." checked={deep} onChange={setDeep} />
              <label className="select-option"><div><strong>Maximum pages</strong><span>Bound the browser agent&rsquo;s exploration budget.</span></div><select value={pages} onChange={(e) => setPages(e.target.value)}><option>5</option><option>10</option><option>20</option><option>50</option></select></label>
              <Toggle title="Capture network requests" detail="Record sanitized request metadata as report evidence." checked={network} onChange={setNetwork} />
              <div className="disabled-option"><div><LockKeyhole size={18} /><div><strong>Direct authentication</strong><span>Use Browser HAR for authenticated products today.</span></div></div></div>
            </div>
          </section>
        ) : (
          <section className="har-instructions">
            <div><span className="eyebrow">Chrome / Edge</span><h2>Capture the useful part</h2></div>
            <ol><li><b>1</b><span>Open DevTools → Network and enable <strong>Preserve log</strong>.</span></li><li><b>2</b><span>Use the product and visit the features you want Orbit to reconstruct.</span></li><li><b>3</b><span>Export the network log as HAR, then upload it above.</span></li></ol>
          </section>
        )}
        <div className="consent-line"><Check size={15} /> You confirm you&rsquo;re authorized to analyze this product surface and agree to Orbit&rsquo;s exploration policy.</div>
      </div>
    </main>
  );
}

function SubmitButton({ pending, disabled, onClick, wide = false, label = "Start analysis" }: { pending: boolean; disabled: boolean; onClick: () => void; wide?: boolean; label?: string }) {
  return <button className={`button primary ${wide ? "full har-submit" : ""}`} onClick={onClick} disabled={pending || disabled}>{pending ? <><Loader2 size={16} className="spin" /> Starting…</> : <>{label} <ArrowRight size={16} /></>}</button>;
}

export default function AnalyzePage() {
  return <RequireAuth><Suspense fallback={null}><AnalyzeInner /></Suspense></RequireAuth>;
}

function normalize(value: string): string {
  const trimmed = value.trim();
  return /^https?:\/\//i.test(trimmed) ? trimmed : `https://${trimmed}`;
}

function Toggle({ title, detail, checked, onChange }: { title: string; detail: string; checked: boolean; onChange: (value: boolean) => void }) {
  return <div className="toggle-option"><div><strong>{title}</strong><span>{detail}</span></div><button aria-label={title} aria-pressed={checked} className={`toggle ${checked ? "on" : ""}`} onClick={() => onChange(!checked)}><i /></button></div>;
}
