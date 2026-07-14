import type { HarImportPayload, SanitizedHarEntry } from "./types";

const MAX_ENTRIES = 500;
const MAX_FILE_BYTES = 100 * 1024 * 1024;
const SAFE_HEADERS = new Set(["content-type", "cache-control", "server"]);
const UUID = /^[0-9a-f]{8}-[0-9a-f-]{27,}$/i;
const OPAQUE = /^[A-Za-z0-9_-]{18,}$/;
const NUMBER = /^\d{3,}$/;

type RawHeader = { name?: unknown; value?: unknown };
type RawEntry = {
  request?: { url?: unknown; method?: unknown };
  response?: { status?: unknown; headers?: unknown; content?: { mimeType?: unknown } };
  _resourceType?: unknown;
};

export interface ParsedHar {
  payload: HarImportPayload;
  originalEntries: number;
  filename: string;
}

function routeShape(pathname: string): string {
  let decoded = pathname || "/";
  try { decoded = decodeURIComponent(decoded); } catch { /* retain encoded path */ }
  const parts = decoded.split("/").map((part) => {
    const short = part.slice(0, 100);
    return UUID.test(short) || OPAQUE.test(short) || NUMBER.test(short) ? ":id" : short;
  });
  const value = parts.join("/").slice(0, 240);
  return value.startsWith("/") ? value : `/${value}`;
}

function headersFrom(raw: unknown): Record<string, string> {
  if (!Array.isArray(raw)) return {};
  const result: Record<string, string> = {};
  for (const item of raw as RawHeader[]) {
    const name = typeof item?.name === "string" ? item.name.toLowerCase() : "";
    if (SAFE_HEADERS.has(name) && typeof item.value === "string") {
      result[name] = item.value.slice(0, 160);
    }
  }
  return result;
}

function sanitizeEntry(raw: RawEntry): SanitizedHarEntry | null {
  if (typeof raw?.request?.url !== "string") return null;
  let parsed: URL;
  try {
    parsed = new URL(raw.request.url);
  } catch {
    return null;
  }
  if (!['http:', 'https:'].includes(parsed.protocol)) return null;
  const headers = headersFrom(raw.response?.headers);
  const contentType = headers["content-type"] || (
    typeof raw.response?.content?.mimeType === "string" ? raw.response.content.mimeType.slice(0, 160) : undefined
  );
  const resourceType = typeof raw._resourceType === "string" ? raw._resourceType.toLowerCase().slice(0, 40) : undefined;
  return {
    url: `${parsed.protocol}//${parsed.host}${routeShape(parsed.pathname)}`,
    method: typeof raw.request?.method === "string" ? raw.request.method.toUpperCase().slice(0, 12) : "GET",
    status: Number.isInteger(raw.response?.status) ? Number(raw.response?.status) : 0,
    ...(resourceType ? { resource_type: resourceType } : {}),
    ...(contentType ? { content_type: contentType } : {}),
    ...(headers["cache-control"] ? { cache_control: headers["cache-control"] } : {}),
    ...(headers.server ? { server: headers.server } : {}),
  };
}

export async function parseAndSanitizeHar(file: File): Promise<ParsedHar> {
  if (file.size > MAX_FILE_BYTES) throw new Error("HAR files must be 100 MB or smaller.");
  let parsed: unknown;
  try {
    parsed = JSON.parse(await file.text());
  } catch {
    throw new Error("This file is not valid HAR JSON.");
  }
  const rawEntries = (parsed as { log?: { entries?: unknown } })?.log?.entries;
  if (!Array.isArray(rawEntries) || rawEntries.length === 0) {
    throw new Error("No network entries were found in this HAR file.");
  }
  const entries = (rawEntries as RawEntry[]).map(sanitizeEntry).filter((entry): entry is SanitizedHarEntry => Boolean(entry));
  if (entries.length === 0) throw new Error("The HAR has no supported HTTP or HTTPS requests.");
  const target = entries.find((entry) => entry.resource_type === "document") ?? entries[0];
  const targetUrl = new URL(target.url);
  return {
    payload: {
      target_url: `${targetUrl.protocol}//${targetUrl.host}/`,
      entries: entries.slice(0, MAX_ENTRIES),
      authorized_public_analysis: true,
    },
    originalEntries: rawEntries.length,
    filename: file.name,
  };
}
