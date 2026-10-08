import type { SanitizedWorkflowStep, WorkflowCapturePayload } from "./types";

const MAX_FILE_BYTES = 5 * 1024 * 1024;
const MAX_STEPS = 200;
const EMAIL = /[\w.+-]+@[\w.-]+\.[a-z]{2,}/i;
const LONG_TOKEN = /[a-z0-9_-]{28,}/i;
const UUID = /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i;

type RawRecorderStep = {
  type?: unknown;
  url?: unknown;
  key?: unknown;
  value?: unknown;
  selectors?: unknown;
};

type RawRecorder = {
  title?: unknown;
  steps?: unknown;
};

export interface ParsedRecorder {
  filename: string;
  originalSteps: number;
  payload: Omit<WorkflowCapturePayload, "entries">;
}

function safeRoute(value: string): string | null {
  try {
    const parsed = new URL(value);
    if (!["http:", "https:"].includes(parsed.protocol)) return null;
    const parts = parsed.pathname.split("/").map((part) => {
      if (UUID.test(part) || /^\d{3,}$/.test(part) || LONG_TOKEN.test(part)) return ":id";
      return part.slice(0, 100);
    });
    parsed.pathname = parts.join("/").slice(0, 240) || "/";
    parsed.search = "";
    parsed.hash = "";
    return parsed.toString();
  } catch {
    return null;
  }
}

function selectorCandidates(raw: unknown): string[] {
  if (!Array.isArray(raw)) return [];
  const values: string[] = [];
  for (const group of raw) {
    const candidates = Array.isArray(group) ? group : [group];
    for (const candidate of candidates) {
      if (typeof candidate !== "string") continue;
      const value = candidate.trim();
      if (!value || value.length > 500 || EMAIL.test(value) || LONG_TOKEN.test(value)) continue;
      values.push(value.startsWith("pierce/") ? value.slice(7) : value);
    }
  }
  return values;
}

function bestSelector(raw: unknown): string | undefined {
  const values = selectorCandidates(raw);
  return values.find((value) => value.startsWith("#") || value.includes("data-testid") || value.includes("data-test"))
    ?? values.find((value) => !/^(aria|xpath|text)\//i.test(value))
    ?? values.find((value) => value.startsWith("text/"))?.replace(/^text\//i, "text=")
    ?? values[0];
}

function valueKind(value: string, selector: string | undefined): SanitizedWorkflowStep["value_kind"] {
  const hint = `${selector ?? ""}`.toLowerCase();
  if (hint.includes("password")) return "password";
  if (hint.includes("email") || EMAIL.test(value)) return "email";
  if (hint.includes("search")) return "search";
  if (/^-?\d+(\.\d+)?$/.test(value)) return "number";
  return value ? "text" : "unknown";
}

function sanitizeStep(raw: RawRecorderStep): SanitizedWorkflowStep | null {
  const type = typeof raw.type === "string" ? raw.type : "";
  if (type === "navigate" && typeof raw.url === "string") {
    const url = safeRoute(raw.url);
    return url ? { type, url } : null;
  }
  if (type === "click" || type === "waitForElement") {
    const selector = bestSelector(raw.selectors);
    return selector ? { type, selector } : null;
  }
  if (type === "change") {
    const selector = bestSelector(raw.selectors);
    const value = typeof raw.value === "string" ? raw.value : "";
    return selector ? {
      type,
      selector,
      value_kind: valueKind(value, selector),
      value_length: Math.min(value.length, 10_000),
    } : null;
  }
  if (type === "keyDown" && typeof raw.key === "string") {
    return { type, key: raw.key.slice(0, 40) };
  }
  if (type === "scroll") return { type };
  return null;
}

export async function parseAndSanitizeRecorder(file: File): Promise<ParsedRecorder> {
  if (file.size > MAX_FILE_BYTES) throw new Error("Recorder exports must be 5 MB or smaller.");
  let parsed: RawRecorder;
  try {
    parsed = JSON.parse(await file.text()) as RawRecorder;
  } catch {
    throw new Error("This file is not valid Recorder JSON.");
  }
  if (!Array.isArray(parsed.steps) || !parsed.steps.length) {
    throw new Error("No Chrome DevTools Recorder steps were found.");
  }
  const steps = (parsed.steps as RawRecorderStep[])
    .map(sanitizeStep)
    .filter((step): step is SanitizedWorkflowStep => Boolean(step))
    .slice(0, MAX_STEPS);
  if (!steps.length) throw new Error("The recording has no supported navigation or interaction steps.");
  const firstNavigation = steps.find((step) => step.type === "navigate" && step.url);
  if (!firstNavigation?.url) throw new Error("The recording must include a navigation step with a public URL.");
  const target = new URL(firstNavigation.url);
  return {
    filename: file.name,
    originalSteps: parsed.steps.length,
    payload: {
      target_url: `${target.protocol}//${target.host}${target.pathname}`,
      title: typeof parsed.title === "string" && parsed.title.trim() ? parsed.title.trim().slice(0, 160) : "Captured workflow",
      steps,
      authorized_public_analysis: true,
    },
  };
}
