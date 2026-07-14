import { lookup } from "node:dns/promises";
import { isIP } from "node:net";
import chromium from "@sparticuz/chromium";
import puppeteer, { type HTTPResponse, type Page } from "puppeteer-core";

export const runtime = "nodejs";
export const maxDuration = 120;
export const dynamic = "force-dynamic";

const MAX_HTML_CHARS = 700_000;
const MAX_NETWORK_SIGNALS = 150;
const BROWSER_UA =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 " +
  "(KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36";

type CapturePage = {
  url: string;
  status: number;
  title: string;
  html: string;
  headers: Record<string, string>;
};

type NetworkSignal = {
  host: string;
  path: string;
  status: number;
  method: string;
  resource_type: string;
  content_type: string;
  cache_control: string;
  server: string;
};

function isPrivateAddress(address: string): boolean {
  const normalized = address.toLowerCase();
  if (normalized === "::" || normalized === "::1") return true;
  if (normalized.startsWith("fc") || normalized.startsWith("fd")) return true;
  if (/^fe[89ab]/.test(normalized)) return true;
  const mapped = normalized.match(/::ffff:(\d+\.\d+\.\d+\.\d+)$/)?.[1];
  const ipv4 = mapped ?? (isIP(normalized) === 4 ? normalized : null);
  if (!ipv4) return false;
  const [a, b] = ipv4.split(".").map(Number);
  return (
    a === 0 || a === 10 || a === 127 || a >= 224 ||
    (a === 100 && b >= 64 && b <= 127) ||
    (a === 169 && b === 254) ||
    (a === 172 && b >= 16 && b <= 31) ||
    (a === 192 && b === 168) ||
    (a === 198 && (b === 18 || b === 19))
  );
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

function resourceType(page: Page, response: HTTPResponse): string {
  try {
    return response.request().resourceType();
  } catch {
    return "other";
  }
}

export async function POST(request: Request) {
  const expectedSecret = process.env.ORBIT_CAPTURE_SECRET;
  if (!expectedSecret || request.headers.get("x-orbit-capture-secret") !== expectedSecret) {
    return Response.json({ error: "Unauthorized" }, { status: 401 });
  }

  let browser;
  try {
    const body = (await request.json()) as { targetUrl?: string; maxPages?: number; deepCrawl?: boolean };
    if (!body.targetUrl) return Response.json({ error: "targetUrl is required" }, { status: 400 });
    const checkedHosts = new Set<string>();
    const target = await assertPublicUrl(body.targetUrl, checkedHosts);
    const originHost = target.hostname;
    const maxPages = Math.max(1, Math.min(body.deepCrawl ? Number(body.maxPages ?? 3) : 1, 3));

    chromium.setGraphicsMode = false;
    browser = await puppeteer.launch({
      args: await puppeteer.defaultArgs({ args: chromium.args, headless: "shell" }),
      executablePath: await chromium.executablePath(),
      headless: "shell",
    });
    const context = await browser.createBrowserContext();
    const pages: CapturePage[] = [];
    const signals: NetworkSignal[] = [];
    const pending = [target.toString()];
    const visited = new Set<string>();

    while (pending.length && visited.size < maxPages) {
      const candidate = pending.shift()!;
      if (visited.has(candidate)) continue;
      const page = await context.newPage();
      await page.setUserAgent(BROWSER_UA);
      await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
      await page.setRequestInterception(true);
      let documentResponse: HTTPResponse | null = null;
      page.on("request", (intercepted) => {
        void (async () => {
          try {
            await assertPublicUrl(intercepted.url(), checkedHosts);
            await intercepted.continue();
          } catch {
            await intercepted.abort("blockedbyclient").catch(() => undefined);
          }
        })();
      });
      page.on("response", (response) => {
        if (response.request().isNavigationRequest() && response.request().frame() === page.mainFrame()) {
          documentResponse = response;
        }
        if (signals.length >= MAX_NETWORK_SIGNALS) return;
        try {
          const url = new URL(response.url());
          const headers = response.headers();
          signals.push({
            host: url.hostname,
            path: url.pathname.slice(0, 200),
            status: response.status(),
            method: response.request().method(),
            resource_type: resourceType(page, response),
            content_type: (headers["content-type"] ?? "").slice(0, 120),
            cache_control: (headers["cache-control"] ?? "").slice(0, 120),
            server: (headers.server ?? "").slice(0, 80),
          });
        } catch {
          // Ignore malformed/non-HTTP response URLs.
        }
      });

      try {
        const response = await page.goto(candidate, { waitUntil: "domcontentloaded", timeout: 30_000 });
        documentResponse ??= response;
        await new Promise((resolve) => setTimeout(resolve, 5_000));
        const finalUrl = await assertPublicUrl(page.url(), checkedHosts);
        const html = await page.content();
        pages.push({
          url: finalUrl.toString(),
          status: documentResponse?.status() ?? 0,
          title: (await page.title()).slice(0, 300),
          html: html.slice(0, MAX_HTML_CHARS),
          headers: documentResponse?.headers() ?? {},
        });
        visited.add(candidate);

        if (body.deepCrawl) {
          const links = await page.$$eval("a[href]", (anchors) =>
            anchors.slice(0, 200).map((anchor) => (anchor as HTMLAnchorElement).href),
          );
          for (const link of links) {
            try {
              const discovered = new URL(link);
              if (discovered.hostname === originHost && ["http:", "https:"].includes(discovered.protocol)) {
                discovered.hash = "";
                if (!visited.has(discovered.toString()) && !pending.includes(discovered.toString())) {
                  pending.push(discovered.toString());
                }
              }
            } catch {
              // Ignore malformed links.
            }
          }
        }
      } finally {
        await page.close();
      }
    }

    await context.close();
    return Response.json({ pages, network_signals: signals, engine: "serverless-chromium" });
  } catch (error) {
    console.error("browser capture failed", error);
    const message = error instanceof Error ? error.message : "Browser capture failed";
    return Response.json({ error: message }, { status: 502 });
  } finally {
    if (browser) await browser.close().catch(() => undefined);
  }
}
