"use client";

// Lightweight, dependency-free error reporting. Always logs to the console; when
// NEXT_PUBLIC_SENTRY_DSN is set it also ships a minimal Sentry envelope so no
// heavyweight SDK is required in the bundle.

const DSN = process.env.NEXT_PUBLIC_SENTRY_DSN;

function ingestUrl(dsn: string): string | null {
  try {
    const url = new URL(dsn);
    const projectId = url.pathname.replace(/^\//, "");
    return `${url.protocol}//${url.host}/api/${projectId}/envelope/?sentry_key=${url.username}&sentry_version=7`;
  } catch {
    return null;
  }
}

export function captureException(error: unknown, context?: Record<string, unknown>): void {
  const err = error instanceof Error ? error : new Error(String(error));
  console.error("[orbit]", err, context ?? "");

  if (!DSN || typeof window === "undefined") return;
  const endpoint = ingestUrl(DSN);
  if (!endpoint) return;

  try {
    const eventId = (crypto.randomUUID?.() ?? `${Date.now()}${Math.random()}`).replace(/-/g, "");
    const header = { event_id: eventId, sent_at: new Date().toISOString() };
    const event = {
      event_id: eventId,
      timestamp: Date.now() / 1000,
      platform: "javascript",
      level: "error",
      environment: process.env.NODE_ENV,
      exception: { values: [{ type: err.name, value: err.message }] },
      request: { url: window.location.href },
      extra: context,
    };
    const envelope = `${JSON.stringify(header)}\n${JSON.stringify({ type: "event" })}\n${JSON.stringify(event)}`;
    void fetch(endpoint, {
      method: "POST",
      body: envelope,
      keepalive: true,
      headers: { "Content-Type": "application/x-sentry-envelope" },
    }).catch(() => {});
  } catch {
    /* never let reporting throw */
  }
}

let installed = false;

export function initClientObservability(): void {
  if (installed || typeof window === "undefined") return;
  installed = true;
  window.addEventListener("error", (event) => captureException(event.error ?? event.message));
  window.addEventListener("unhandledrejection", (event) => captureException(event.reason));
}
