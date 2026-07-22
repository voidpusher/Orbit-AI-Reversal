"use client";

import { ArrowRight, CheckCircle2, ChevronLeft, Clock3, FileSearch, Globe2, Network, ScanSearch, Sparkles } from "lucide-react";
import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { OrbitLogo } from "@/components/OrbitLogo";

const steps = [
  [Globe2, "Opening browser", "Establishing an isolated exploration session"],
  [FileSearch, "Discovering pages", "Found 24 navigable product surfaces"],
  [ScanSearch, "Exploring navigation", "Mapping key journeys and capabilities"],
  [Network, "Recording signals", "Normalizing observable network metadata"],
  [Sparkles, "Building report", "Inferring the system behind the experience"],
];

export default function AnalysisProgress() {
  const router = useRouter(); const [active, setActive] = useState(0);
  useEffect(() => { const interval = setInterval(() => setActive((value) => Math.min(value + 1, steps.length - 1)), 850); return () => clearInterval(interval); }, []);
  const progress = ((active + 1) / steps.length) * 100;
  return <main className="app-shell"><header className="app-header"><button className="brand button-reset" onClick={() => router.push("/")}><OrbitLogo />orbit</button><div className="header-context"><span>Analysis in progress</span><button className="avatar">SC</button></div></header><div className="progress-page"><button className="back-link" onClick={() => router.push("/dashboard")}><ChevronLeft size={16} /> Back to dashboard</button><div className="progress-hero"><div className="scanning-mark"><span /><span /><span /></div><span className="eyebrow"><i className="pulse-dot" /> Browser agent working</span><h1>Exploring Linear.</h1><p>Orbit is following the observable product surface and connecting the evidence.</p></div><section className="progress-layout"><div className="progress-card"><div className="progress-meta"><span>Exploration progress</span><b>{Math.round(progress)}%</b></div><div className="progress-track"><i style={{ width: `${progress}%` }} /></div><div className="eta"><Clock3 size={15} /> Estimated time remaining <b>{active < 4 ? "~ 1 min" : "Finishing up"}</b></div><div className="step-list">{steps.map(([Icon, title, detail], index) => <div className={`progress-step ${index < active ? "done" : index === active ? "current" : ""}`} key={title as string}><span>{index < active ? <CheckCircle2 size={18} /> : <Icon size={18} />}</span><div><strong>{title as string}</strong><p>{detail as string}</p></div>{index === active && <i className="working">Working</i>}</div>)}</div><button className="button primary full" onClick={() => router.push("/report/demo")}>View completed report <ArrowRight size={16} /></button></div><aside className="log-card"><div className="log-heading"><span><i /> Live signals</span><b>UTC +05:30</b></div><div className="logs"><p><time>14:32:01</time> Browser context ready</p><p><time>14:32:04</time> <em>GET</em> linear.app</p><p><time>14:32:06</time> Navigation model discovered</p><p><time>14:32:11</time> 7 public routes queued</p><p><time>14:32:16</time> <em>WS</em> Realtime signal observed</p><p><time>14:32:22</time> Building evidence graph</p><p className="latest"><time>now</time> {active >= 4 ? "Synthesizing engineering insights" : "Exploration in progress"}</p></div></aside></section></div></main>;
}
