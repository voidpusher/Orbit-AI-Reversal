import { lookup } from "node:dns/promises";
import { isIP } from "node:net";
import chromium from "@sparticuz/chromium";
import puppeteer, { type ElementHandle, type KeyInput, type Page } from "puppeteer-core";

export const runtime = "nodejs";
export const maxDuration = 120;
export const dynamic = "force-dynamic";

type ContractStep = {
  id?: string;
  action?: string;
  kind?: string;
  selector?: string;
  url?: string;
  key?: string;
  input_kind?: string;
};

type WorkflowContract = {
  version?: string;
  id?: string;
  name?: string;
  target_url?: string;
  steps?: ContractStep[];
};

function isPrivateAddress(address: string): boolean {
  const normalized = address.toLowerCase();
  if (normalized === "::" || normalized === "::1") return true;
  if (normalized.startsWith("fc") || normalized.startsWith("fd") || /^fe[89ab]/.test(normalized)) return true;
  const mapped = normalized.match(/::ffff:(\d+\.\d+\.\d+\.\d+)$/)?.[1];
  const ipv4 = mapped ?? (isIP(normalized) === 4 ? normalized : null);
  if (!ipv4) return false;
  const [a, b] = ipv4.split(".").map(Number);
  return a === 0 || a === 10 || a === 127 || a >= 224 ||
    (a === 100 && b >= 64 && b <= 127) || (a === 169 && b === 254) ||
    (a === 172 && b >= 16 && b <= 31) || (a === 192 && b === 168) ||
    (a === 198 && (b === 18 || b === 19));
}

async function assertPublicUrl(raw: string, checkedHosts: Set<string>): Promise<URL> {
  const url = new URL(raw);
  if (!["http:", "https:"].includes(url.protocol) || url.username || url.password) {
    throw new Error("Only credential-free public HTTP(S) URLs are allowed");
  }
  const host = url.hostname.toLowerCase();
  if (!host || host === "localhost" || host.endsWith(".local")) throw new Error("Private host blocked");
  if (!checkedHosts.has(host)) {
    const addresses = await lookup(host, { all: true, verbatim: true });
    if (!addresses.length || addresses.some(({ address }) => isPrivateAddress(address))) {
      throw new Error("Private network address blocked");
    }
    checkedHosts.add(host);
  }
  return url;
}

function sameOriginUrl(target: URL, raw: string): URL {
  const candidate = new URL(raw, target);
  if (candidate.origin !== target.origin) throw new Error("Workflow navigation cannot leave the captured target origin");
  return candidate;
}

async function proposal(page: Page, step: ContractStep) {
  const terms = (step.action ?? "").toLowerCase().split(/\s+/).filter((term) => term.length > 2);
  const candidates = await page.$$eval("button, a, input, [role='button']", (elements) =>
    elements.slice(0, 250).map((element) => ({
      testid: element.getAttribute("data-testid"), id: element.id || null,
      name: element.getAttribute("name"), aria: element.getAttribute("aria-label"),
      text: (element.textContent ?? "").trim().slice(0, 120),
    })),
  );
  for (const candidate of candidates) {
    const haystack = Object.values(candidate).filter(Boolean).join(" ").toLowerCase();
    if (terms.length && !terms.some((term) => haystack.includes(term))) continue;
    let selector = "";
    let reason = "";
    const quoted = (value: string) => value.replace(/["\\]/g, "\\$&");
    if (candidate.testid) { selector = `[data-testid="${quoted(candidate.testid)}"]`; reason = "unique data-testid matched the action"; }
    else if (candidate.id && /^[A-Za-z][\w-]*$/.test(candidate.id)) { selector = `#${candidate.id}`; reason = "element id matched the action"; }
    else if (candidate.name) { selector = `[name="${quoted(candidate.name)}"]`; reason = "element name matched the action"; }
    else if (candidate.aria) { selector = `[aria-label="${quoted(candidate.aria)}"]`; reason = "accessible label matched the action"; }
    if (selector && (await page.$$(selector)).length === 1) {
      return { step_id: step.id ?? "", old_selector: step.selector ?? "", proposed_selector: selector,
        confidence: 82, reason, requires_approval: true };
    }
  }
  return null;
}

async function visible(handle: ElementHandle<Element>) {
  return handle.evaluate((element) => {
    const rect = element.getBoundingClientRect();
    const style = getComputedStyle(element);
    return rect.width > 0 && rect.height > 0 && style.visibility !== "hidden" && style.display !== "none";
  });
}

async function executeStep(page: Page, target: URL, step: ContractStep, inputs: Record<string, string>) {
  const kind = step.kind ?? "interaction";
  const selector = step.selector ?? "";
  if (kind === "navigate") {
    const destination = sameOriginUrl(target, step.url ?? target.toString());
    await page.goto(destination.toString(), { waitUntil: "domcontentloaded", timeout: 30_000 });
  } else if (kind === "input") {
    const element = await page.waitForSelector(selector, { visible: true, timeout: 10_000 });
    if (!element) throw new Error("SelectorNotFound");
    await element.click({ count: 3 });
    await element.type(inputs[step.input_kind ?? "text"] ?? "");
  } else if (kind === "keyboard") {
    await page.keyboard.press((step.key ?? "Enter") as KeyInput);
  } else if (kind === "scroll") {
    await page.mouse.wheel({ deltaY: 600 });
  } else if (kind === "assertion") {
    if (selector) {
      const element = await page.waitForSelector(selector, { visible: true, timeout: 10_000 });
      if (!element || !(await visible(element))) throw new Error("SelectorNotFound");
    } else {
      const found = await page.evaluate((text) => document.body.innerText.toLowerCase().includes(text.toLowerCase()), step.action ?? "");
      if (!found) throw new Error("AssertionFailed");
    }
  } else if (selector) {
    const element = await page.waitForSelector(selector, { visible: true, timeout: 10_000 });
    if (!element) throw new Error("SelectorNotFound");
    await element.click();
  } else {
    const action = (step.action ?? "").toLowerCase();
    const match = await page.$$("button, a, [role='button']").then(async (elements) => {
      for (const element of elements.slice(0, 250)) {
        const text = await element.evaluate((node) => (node.textContent ?? "").trim().toLowerCase());
        if (text && (text.includes(action) || action.includes(text))) return element;
      }
      return null;
    });
    if (!match) throw new Error("SelectorNotFound");
    await match.click();
  }
}

export async function POST(request: Request) {
  const expectedSecret = process.env.ORBIT_CAPTURE_SECRET;
  if (!expectedSecret || request.headers.get("x-orbit-capture-secret") !== expectedSecret) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  let browser;
  const overallStart = Date.now();
  try {
    const body = (await request.json()) as { contract?: WorkflowContract; inputs?: Record<string, string> };
    const contract = body.contract;
    if (!contract || contract.version !== "orbit.workflow.v1" || !contract.target_url ||
        !Array.isArray(contract.steps) || !contract.steps.length || contract.steps.length > 100) {
      return Response.json({ error: "Invalid workflow contract" }, { status: 422 });
    }
    const required = [...new Set(contract.steps.filter((step) => step.kind === "input").map((step) => step.input_kind ?? "text"))];
    const missing = required.filter((key) => !body.inputs?.[key]);
    if (missing.length) {
      return Response.json({ status: "blocked", error_code: "runtime_input_required", failure_step_id: null,
        steps: [], repair_proposal: null, message: `Runtime input required: ${missing.join(", ")}` });
    }

    const checkedHosts = new Set<string>();
    const target = await assertPublicUrl(contract.target_url, checkedHosts);
    chromium.setGraphicsMode = false;
    browser = await puppeteer.launch({
      args: await puppeteer.defaultArgs({ args: chromium.args, headless: "shell" }),
      executablePath: await chromium.executablePath(), headless: "shell",
    });
    const context = await browser.createBrowserContext();
    const page = await context.newPage();
    await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
    await page.setRequestInterception(true);
    page.on("request", (intercepted) => {
      void (async () => {
        try { await assertPublicUrl(intercepted.url(), checkedHosts); await intercepted.continue(); }
        catch { await intercepted.abort("blockedbyclient").catch(() => undefined); }
      })();
    });

    const results: Array<Record<string, unknown>> = [];
    let failureStepId: string | null = null;
    let errorCode: string | null = null;
    let repairProposal = null;
    for (const [index, step] of contract.steps.entries()) {
      const started = Date.now();
      const stepId = step.id ?? `step-${index + 1}`;
      try {
        await executeStep(page, target, step, body.inputs ?? {});
        results.push({ step_id: stepId, action: step.action ?? "Action", status: "passed", duration_ms: Date.now() - started });
      } catch (error) {
        failureStepId = stepId;
        errorCode = step.selector ? "selector_not_found" : "step_failed";
        if (step.selector) repairProposal = await proposal(page, step);
        results.push({ step_id: stepId, action: step.action ?? "Action", status: "failed",
          duration_ms: Date.now() - started, error_code: errorCode,
          message: error instanceof Error ? error.name : "ReplayError" });
        break;
      }
    }
    await context.close();
    return Response.json({ status: failureStepId ? "failed" : "passed", error_code: errorCode,
      failure_step_id: failureStepId, duration_ms: Date.now() - overallStart, steps: results,
      repair_proposal: repairProposal,
      message: failureStepId ? "Replay stopped at the first failed step" : "Replay completed" });
  } catch (error) {
    console.error("workflow replay failed", error instanceof Error ? error.name : "ReplayError");
    return Response.json({ status: "blocked", error_code: "replay_runtime_failed", failure_step_id: null,
      steps: [], repair_proposal: null, message: "The isolated replay runtime could not complete this workflow." });
  } finally {
    if (browser) await browser.close().catch(() => undefined);
  }
}
