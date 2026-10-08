"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import {
  Activity,
  AlertTriangle,
  ArrowRight,
  Braces,
  Bell,
  Check,
  Copy,
  Download,
  Eye,
  FileCode2,
  Loader2,
  LockKeyhole,
  Play,
  Radio,
  RotateCcw,
  Route,
  Save,
  ShieldCheck,
  Trash2,
  Wrench,
  Workflow,
} from "lucide-react";
import { useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { CompiledWorkflow, ReportDocument, SavedWorkflow, WorkflowRun } from "@/lib/types";

type ExportKind = "json" | "playwright";

function saveText(filename: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }));
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function fileSafe(value: string) {
  return value.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "workflow";
}

export function WorkflowStudio({
  reportId,
  productName,
  document,
  demoResult,
}: {
  reportId: string;
  productName: string;
  document: ReportDocument;
  demoResult?: CompiledWorkflow;
}) {
  const workflows = document.user_flows?.flows ?? [];
  const [selected, setSelected] = useState(workflows[0]?.name ?? "");
  const [compiled, setCompiled] = useState<CompiledWorkflow | null>(null);
  const [artifact, setArtifact] = useState<ExportKind>("playwright");
  const [copied, setCopied] = useState(false);
  const [schedule, setSchedule] = useState<"manual" | "daily" | "weekly">("manual");
  const [savedOverride, setSavedOverride] = useState<SavedWorkflow | null>(null);
  const [runtimeInputs, setRuntimeInputs] = useState<Record<string, string>>({});

  const savedWorkflows = useQuery({
    queryKey: ["saved-workflows", reportId],
    queryFn: () => api.listSavedWorkflows(reportId),
    enabled: !demoResult,
  });

  const selectedFlow = useMemo(
    () => workflows.find((flow) => flow.name === selected) ?? workflows[0],
    [selected, workflows],
  );

  const saved = useMemo(() => {
    if (!compiled) return null;
    if (savedOverride?.contract.id === compiled.contract.id) return savedOverride;
    return savedWorkflows.data?.items.find((item) => item.contract.id === compiled.contract.id) ?? null;
  }, [compiled, savedOverride, savedWorkflows.data]);

  const runs = useQuery({
    queryKey: ["workflow-runs", reportId, saved?.id],
    queryFn: () => api.listWorkflowRuns(reportId, saved!.id),
    enabled: Boolean(saved && !demoResult),
  });

  const compile = useMutation({
    mutationFn: () => demoResult ? Promise.resolve(demoResult) : api.compileWorkflow(reportId, selected),
    onSuccess: (result) => {
      setCompiled(result);
      setArtifact("playwright");
      setSavedOverride(null);
      setRuntimeInputs({});
    },
  });

  const save = useMutation({
    mutationFn: () => api.saveWorkflow(reportId, compiled!.contract, schedule),
    onSuccess: (result) => {
      setSavedOverride(result);
      void savedWorkflows.refetch();
    },
  });

  const run = useMutation({
    mutationFn: () => api.runWorkflow(reportId, saved!.id, runtimeInputs),
    onSuccess: () => void runs.refetch(),
  });

  const copyArtifact = async () => {
    if (!compiled) return;
    await navigator.clipboard.writeText(artifact === "json" ? compiled.contract_json : compiled.playwright);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  };

  const downloadArtifact = () => {
    if (!compiled) return;
    const slug = fileSafe(compiled.contract.name);
    if (artifact === "json") {
      saveText(`orbit-${slug}.workflow.json`, compiled.contract_json, "application/json");
    } else {
      saveText(`${slug}.spec.ts`, compiled.playwright, "text/typescript");
    }
  };

  if (!workflows.length) {
    return (
      <section className="workflow-studio workflow-empty">
        <div className="workflow-empty-mark"><Workflow size={28} /></div>
        <span className="eyebrow">Orbit Workflow</span>
        <h2>No defensible workflow can be compiled yet.</h2>
        <p>
          This report does not contain a supported product journey. Import an authenticated HAR capture
          from a workflow you are authorized to inspect; Orbit will correlate its actions and requests
          without storing cookies or sensitive payloads.
        </p>
        <a className="button primary" href="/analyze"><Radio size={15} /> Capture a workflow</a>
      </section>
    );
  }

  return (
    <section className="workflow-studio">
      <header className="workflow-studio-head">
        <div className="workflow-title-mark"><Workflow size={21} /></div>
        <div>
          <span className="eyebrow">Executable product intelligence</span>
          <h2>Compile a product journey</h2>
          <p>Convert report evidence into an inspectable workflow contract and automation starter.</p>
        </div>
        <div className="workflow-safety"><ShieldCheck size={15} /><span><b>Evidence locked</b><small>No invented selectors or payloads</small></span></div>
      </header>

      <div className="workflow-picker">
        <div>
          <span className="eyebrow">01 · Select journey</span>
          <h3>What should Orbit make executable?</h3>
        </div>
        <div className="workflow-choice-list">
          {workflows.map((flow) => (
            <button
              key={flow.name}
              className={selected === flow.name ? "selected" : ""}
              onClick={() => { setSelected(flow.name); setCompiled(null); setSavedOverride(null); }}
            >
              <span className="workflow-radio"><i /></span>
              <span><b>{flow.name}</b><small>{flow.steps.length} actions · {flow.confidence}% evidence confidence</small></span>
              <ArrowRight size={15} />
            </button>
          ))}
        </div>
        {selectedFlow && (
          <div className="workflow-preview-path">
            {selectedFlow.steps.map((step, index) => (
              <span key={`${step}-${index}`}><i>{index + 1}</i>{step}{index < selectedFlow.steps.length - 1 && <ArrowRight size={12} />}</span>
            ))}
          </div>
        )}
        <button className="button primary workflow-compile" disabled={!selected || compile.isPending} onClick={() => compile.mutate()}>
          {compile.isPending ? <Loader2 className="spin" size={15} /> : <Play size={14} />}
          {compile.isPending ? "Correlating evidence…" : "Compile workflow"}
        </button>
        {compile.error && <p className="workflow-error"><AlertTriangle size={14} /> {compile.error.message}</p>}
      </div>

      {compiled && <CompiledWorkspace
        reportId={reportId}
        compiled={compiled}
        productName={productName}
        artifact={artifact}
        setArtifact={setArtifact}
        copied={copied}
        copyArtifact={copyArtifact}
        downloadArtifact={downloadArtifact}
        demoMode={Boolean(demoResult)}
        schedule={schedule}
        setSchedule={setSchedule}
        saved={saved}
        saving={save.isPending}
        saveError={save.error?.message}
        onSave={() => save.mutate()}
        running={run.isPending}
        runError={run.error?.message}
        onRun={() => run.mutate()}
        runtimeInputs={runtimeInputs}
        setRuntimeInput={(key, value) => setRuntimeInputs((current) => ({ ...current, [key]: value }))}
        runHistory={runs.data?.items ?? (run.data ? [run.data] : [])}
      />}
    </section>
  );
}

function CompiledWorkspace({
  reportId,
  compiled,
  productName,
  artifact,
  setArtifact,
  copied,
  copyArtifact,
  downloadArtifact,
  demoMode,
  schedule,
  setSchedule,
  saved,
  saving,
  saveError,
  onSave,
  running,
  runError,
  onRun,
  runtimeInputs,
  setRuntimeInput,
  runHistory,
}: {
  reportId: string;
  compiled: CompiledWorkflow;
  productName: string;
  artifact: ExportKind;
  setArtifact: (value: ExportKind) => void;
  copied: boolean;
  copyArtifact: () => void;
  downloadArtifact: () => void;
  demoMode: boolean;
  schedule: "manual" | "daily" | "weekly";
  setSchedule: (value: "manual" | "daily" | "weekly") => void;
  saved: SavedWorkflow | null;
  saving: boolean;
  saveError?: string;
  onSave: () => void;
  running: boolean;
  runError?: string;
  onRun: () => void;
  runtimeInputs: Record<string, string>;
  setRuntimeInput: (key: string, value: string) => void;
  runHistory: WorkflowRun[];
}) {
  const { contract } = compiled;
  const activeCode = artifact === "json" ? compiled.contract_json : compiled.playwright;
  const requiredInputs = [...new Set(contract.steps.filter((step) => step.kind === "input").map((step) => step.input_kind ?? "text"))];

  return (
    <div className="workflow-result">
      <div className="workflow-result-head">
        <div>
          <span className="eyebrow">02 · Compiled contract</span>
          <h3>{contract.name}</h3>
          <p>{productName} · <code>{contract.id}</code></p>
        </div>
        <div className={`workflow-status ${contract.status}`}>
          {contract.status === "ready" ? <Check size={14} /> : <AlertTriangle size={14} />}
          <span><b>{contract.status === "ready" ? "Ready to run" : "Review required"}</b><small>{contract.automation_readiness}% automation readiness</small></span>
        </div>
      </div>

      <div className="workflow-result-grid">
        <div className="workflow-timeline">
          <div className="workflow-block-head"><span>Behavior trace</span><b>{contract.steps.length} actions</b></div>
          {contract.steps.map((step, index) => (
            <article key={step.id}>
              <div className="workflow-step-index">{String(index + 1).padStart(2, "0")}</div>
              <div className="workflow-step-line"><i /></div>
              <div className="workflow-step-body">
                <div><b>{step.action}</b><em className={step.classification}>{step.classification}</em></div>
                <span>{step.kind} · {step.confidence}% confidence</span>
                <small><Eye size={11} /> {step.evidence_ids.join(", ") || "Evidence pending"}</small>
              </div>
            </article>
          ))}
        </div>

        <div className="workflow-contract-panel">
          <div className="workflow-block-head"><span>Operation map</span><b>{contract.endpoints.length} correlated</b></div>
          {contract.endpoints.length ? contract.endpoints.map((endpoint) => (
            <div className="workflow-endpoint" key={`${endpoint.method}-${endpoint.path}`}>
              <span className={`method ${endpoint.method.toLowerCase()}`}>{endpoint.method}</span>
              <code>{endpoint.path}</code>
              <em>{endpoint.confidence}%</em>
            </div>
          )) : <p className="workflow-no-map">No endpoint can be honestly correlated to this journey yet.</p>}

          <div className="workflow-block-head workflow-block-spaced"><span>Evidence ledger</span><b>{contract.evidence.length} records</b></div>
          <div className="workflow-evidence-ledger">
            {contract.evidence.map((item) => (
              <div key={item.id}><b>{item.id}</b><span><strong>{item.source}</strong><small>{item.detail}</small></span><em className={item.classification}>{item.classification}</em></div>
            ))}
          </div>
        </div>
      </div>

      <div className="workflow-blockers">
        <div><AlertTriangle size={16} /><span><b>What Orbit still needs</b><small>These gaps remain explicit so the generated automation cannot quietly make false assumptions.</small></span></div>
        <ul>{contract.unknowns.map((unknown) => <li key={unknown}>{unknown}</li>)}</ul>
      </div>

      <div className="workflow-operations">
        <div className="workflow-operations-head">
          <div>
            <span className="eyebrow">03 · Replay monitor</span>
            <h3>Save, replay, diagnose</h3>
            <p>Orbit runs the evidence-backed contract in an isolated browser and stores only redacted outcomes.</p>
          </div>
          <span className="workflow-secret-note"><ShieldCheck size={13} /> Runtime inputs are redacted from run history</span>
        </div>

        {demoMode ? (
          <div className="workflow-operation-notice"><Activity size={16} /><span><b>Replay is available on captured reports</b><small>Run Workflow Capture on a product you are authorized to test, then compile this journey.</small></span></div>
        ) : (
          <>
            <div className="workflow-operation-controls">
              <label>
                <span>Monitor cadence</span>
                <select value={schedule} onChange={(event) => setSchedule(event.target.value as typeof schedule)}>
                  <option value="manual">Manual only</option>
                  <option value="daily">Daily</option>
                  <option value="weekly">Weekly</option>
                </select>
              </label>
              <button className="button secondary" disabled={saving} onClick={onSave}>
                {saving ? <Loader2 className="spin" size={14} /> : <Save size={14} />}
                {saved ? `Save version ${saved.version + 1}` : "Save workflow"}
              </button>
              <button className="button primary" disabled={!saved || running} onClick={onRun}>
                {running ? <Loader2 className="spin" size={14} /> : <Play size={14} />}
                {running ? "Replaying…" : "Run isolated replay"}
              </button>
            </div>

            {requiredInputs.length > 0 && (
              <div className="workflow-runtime-inputs">
                {requiredInputs.map((input) => (
                  <label key={input}>
                    <span>{input} input</span>
                    <input
                      type={input === "password" ? "password" : "text"}
                      autoComplete="off"
                      value={runtimeInputs[input] ?? ""}
                      onChange={(event) => setRuntimeInput(input, event.target.value)}
                      placeholder={`Enter ${input} for this run or seal it below`}
                    />
                  </label>
                ))}
              </div>
            )}

            {(saveError || runError) && <p className="workflow-error"><AlertTriangle size={14} /> {saveError || runError}</p>}
            {saved && <p className="workflow-saved-state"><Check size={13} /> Saved as version {saved.version} · {saved.schedule} monitoring{saved.next_run_at ? ` · next check ${new Date(saved.next_run_at).toLocaleString()}` : ""}</p>}

            <ProductionControls
              reportId={reportId}
              saved={saved}
              requiredInputs={requiredInputs}
              runtimeInputs={runtimeInputs}
              clearRuntimeInputs={() => requiredInputs.forEach((key) => setRuntimeInput(key, ""))}
            />

            <RunLedger runs={runHistory} />
          </>
        )}
      </div>

      <div className="workflow-artifact">
        <div className="workflow-artifact-toolbar">
          <div>
            <button className={artifact === "playwright" ? "active" : ""} onClick={() => setArtifact("playwright")}><FileCode2 size={13} /> Playwright</button>
            <button className={artifact === "json" ? "active" : ""} onClick={() => setArtifact("json")}><Braces size={13} /> Contract JSON</button>
          </div>
          <div>
            <button onClick={copyArtifact}>{copied ? <Check size={13} /> : <Copy size={13} />} {copied ? "Copied" : "Copy"}</button>
            <button onClick={downloadArtifact}><Download size={13} /> Download</button>
          </div>
        </div>
        <pre><code>{activeCode}</code></pre>
      </div>
    </div>
  );
}

function ProductionControls({
  reportId,
  saved,
  requiredInputs,
  runtimeInputs,
  clearRuntimeInputs,
}: {
  reportId: string;
  saved: SavedWorkflow | null;
  requiredInputs: string[];
  runtimeInputs: Record<string, string>;
  clearRuntimeInputs: () => void;
}) {
  const [slackWebhook, setSlackWebhook] = useState("");
  const [alertEmail, setAlertEmail] = useState("");

  const vault = useQuery({
    queryKey: ["workflow-vault", reportId, saved?.id],
    queryFn: () => api.workflowVaultStatus(reportId, saved!.id),
    enabled: Boolean(saved),
  });
  const notifications = useQuery({
    queryKey: ["workflow-notifications", reportId, saved?.id],
    queryFn: () => api.workflowNotificationStatus(reportId, saved!.id),
    enabled: Boolean(saved),
  });
  const saveVault = useMutation({
    mutationFn: () => api.saveWorkflowVault(
      reportId,
      saved!.id,
      Object.fromEntries(requiredInputs.map((key) => [key, runtimeInputs[key] ?? ""])),
    ),
    onSuccess: () => {
      void vault.refetch();
      clearRuntimeInputs();
    },
  });
  const clearVault = useMutation({
    mutationFn: () => api.clearWorkflowVault(reportId, saved!.id),
    onSuccess: () => void vault.refetch(),
  });
  const saveAlerts = useMutation({
    mutationFn: () => api.updateWorkflowNotifications(reportId, saved!.id, {
      ...(slackWebhook ? { slack_webhook: slackWebhook } : {}),
      ...(alertEmail ? { email: alertEmail } : {}),
    }),
    onSuccess: () => {
      void notifications.refetch();
      setSlackWebhook("");
      setAlertEmail("");
    },
  });
  const clearAlerts = useMutation({
    mutationFn: () => api.updateWorkflowNotifications(reportId, saved!.id, {
      disable_slack: true,
      disable_email: true,
    }),
    onSuccess: () => void notifications.refetch(),
  });

  if (!saved) {
    return <div className="workflow-production-locked"><LockKeyhole size={14} /> Save the workflow before configuring encrypted inputs or alerts.</div>;
  }

  const vaultReady = vault.data?.available ?? false;
  const allInputsPresent = requiredInputs.every((key) => Boolean(runtimeInputs[key]));
  const vaultConfigured = requiredInputs.length > 0 && requiredInputs.every(
    (key) => vault.data?.configured_keys.includes(key),
  );
  const alertsConfigured = Boolean(notifications.data?.slack_enabled || notifications.data?.email_enabled);
  const error = vault.error ?? notifications.error ?? saveVault.error ?? clearVault.error
    ?? saveAlerts.error ?? clearAlerts.error;

  return (
    <div className="workflow-production-controls">
      {requiredInputs.length > 0 && (
        <section className="workflow-secure-card">
          <header>
            <i><LockKeyhole size={15} /></i>
            <span><b>Encrypted runtime vault</b><small>AES-256-GCM · values are write-only</small></span>
            <em className={vaultConfigured ? "configured" : "pending"}>{vaultConfigured ? "secured" : vaultReady ? "not configured" : "unavailable"}</em>
          </header>
          <p>Seal the current runtime inputs for unattended runs. Saving replaces the previous encrypted value and clears the plaintext fields from this page.</p>
          <div className="workflow-secure-actions">
            <button className="button secondary" disabled={!vaultReady || !allInputsPresent || saveVault.isPending} onClick={() => saveVault.mutate()}>
              {saveVault.isPending ? <Loader2 className="spin" size={13} /> : <LockKeyhole size={13} />}
              {vaultConfigured ? "Rotate encrypted inputs" : "Seal inputs for monitoring"}
            </button>
            {vaultConfigured && <button className="workflow-danger-action" disabled={clearVault.isPending} onClick={() => clearVault.mutate()}><Trash2 size={12} /> Clear vault</button>}
          </div>
        </section>
      )}

      <section className="workflow-secure-card">
        <header>
          <i><Bell size={15} /></i>
          <span><b>Failure notifications</b><small>Only status, failed step, and error code are sent</small></span>
          <em className={alertsConfigured ? "configured" : "pending"}>{alertsConfigured ? "active" : "not configured"}</em>
        </header>
        <div className="workflow-alert-fields">
          <label><span>Slack webhook</span><input type="password" autoComplete="off" value={slackWebhook} onChange={(event) => setSlackWebhook(event.target.value)} placeholder={notifications.data?.slack_enabled ? "Configured · paste to rotate" : "https://hooks.slack.com/services/…"} /></label>
          <label><span>Alert email</span><input type="email" autoComplete="off" value={alertEmail} onChange={(event) => setAlertEmail(event.target.value)} placeholder={notifications.data?.email_enabled ? "Configured · enter to rotate" : "engineering@example.com"} /></label>
        </div>
        {notifications.data && !notifications.data.email_provider_available && <p className="workflow-provider-note">Email delivery activates after the Resend provider key and verified sender are configured. Slack works immediately.</p>}
        <div className="workflow-secure-actions">
          <button className="button secondary" disabled={!vaultReady || (!slackWebhook && !alertEmail) || saveAlerts.isPending} onClick={() => saveAlerts.mutate()}>{saveAlerts.isPending ? <Loader2 className="spin" size={13} /> : <Bell size={13} />} Save destinations</button>
          {alertsConfigured && <button className="workflow-danger-action" disabled={clearAlerts.isPending} onClick={() => clearAlerts.mutate()}><Trash2 size={12} /> Disable alerts</button>}
        </div>
      </section>
      {error && <p className="workflow-error"><AlertTriangle size={14} /> {error.message}</p>}
    </div>
  );
}

function RunLedger({ runs }: { runs: WorkflowRun[] }) {
  if (!runs.length) {
    return <div className="workflow-run-empty"><RotateCcw size={15} /> No replays yet. The first run will create a step-by-step diagnostic ledger.</div>;
  }
  return (
    <div className="workflow-run-ledger">
      {runs.slice(0, 5).map((run) => (
        <article key={run.id} className={run.status}>
          <div className="workflow-run-summary">
            <i>{run.status === "passed" ? <Check size={14} /> : run.status === "failed" ? <AlertTriangle size={14} /> : <Activity size={14} />}</i>
            <span><b>{run.status}</b><small>{new Date(run.started_at).toLocaleString()} · {run.duration_ms ?? 0}ms</small></span>
            <em>{run.result.steps?.filter((step) => step.status === "passed").length ?? 0}/{run.result.steps?.length ?? 0} steps</em>
          </div>
          {run.result.message && <p>{run.result.message}</p>}
          {run.repair_proposal && (
            <div className="workflow-repair">
              <Wrench size={14} />
              <span><b>Repair proposal · {run.repair_proposal.confidence}%</b><small>{run.repair_proposal.reason}</small></span>
              <code>{run.repair_proposal.proposed_selector}</code>
              <em>approval required</em>
            </div>
          )}
        </article>
      ))}
    </div>
  );
}
