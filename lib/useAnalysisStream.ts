"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "./api";
import type { Analysis, AnalysisEvent } from "./types";

interface StreamState {
  events: AnalysisEvent[];
  analysis: Analysis | null;
  connected: boolean;
  error: string | null;
}

const TERMINAL = new Set(["completed", "failed", "cancelled"]);

/**
 * Subscribes to an analysis event stream (SSE) and mirrors the analysis record.
 * Falls back to polling if the browser cannot open an EventSource. Poll-refreshes
 * the analysis record so we learn the report_id and terminal status reliably.
 */
export function useAnalysisStream(analysisId: string | null): StreamState {
  const [events, setEvents] = useState<AnalysisEvent[]>([]);
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [connected, setConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const seen = useRef<Set<number>>(new Set());

  useEffect(() => {
    if (!analysisId) return;
    seen.current = new Set();
    setEvents([]);
    let closed = false;
    let poll: ReturnType<typeof setInterval> | undefined;

    const pushEvent = (event: AnalysisEvent) => {
      if (seen.current.has(event.sequence)) return;
      seen.current.add(event.sequence);
      setEvents((prev) => [...prev, event].sort((a, b) => a.sequence - b.sequence));
    };

    const refresh = async () => {
      try {
        const record = await api.getAnalysis(analysisId);
        if (closed) return;
        setAnalysis(record);
        if (TERMINAL.has(record.status)) {
          source.close();
          if (poll) clearInterval(poll);
        }
      } catch (err) {
        if (!closed) setError(err instanceof Error ? err.message : "Failed to load analysis");
      }
    };

    const source = new EventSource(api.eventStreamUrl(analysisId));
    source.onopen = () => setConnected(true);
    source.onmessage = (message) => {
      try {
        pushEvent(JSON.parse(message.data) as AnalysisEvent);
      } catch {
        /* keepalive */
      }
    };
    // Named events (event: <kind>) don't trigger onmessage — capture them too.
    const kinds = [
      "analysis.queued", "browser.opening", "browser.fallback", "page.exploring",
      "evidence.recorded", "report.generating", "report.ready", "analysis.completed",
      "analysis.failed", "analysis.cancelled", "analysis.status",
    ];
    kinds.forEach((kind) =>
      source.addEventListener(kind, (message) => {
        try {
          pushEvent(JSON.parse((message as MessageEvent).data) as AnalysisEvent);
          if (kind === "report.ready" || kind === "analysis.completed" || kind === "analysis.failed") {
            void refresh();
          }
        } catch {
          /* ignore */
        }
      }),
    );
    source.onerror = () => setConnected(false);

    void refresh();
    poll = setInterval(refresh, 2500);

    return () => {
      closed = true;
      source.close();
      if (poll) clearInterval(poll);
    };
  }, [analysisId]);

  return { events, analysis, connected, error };
}
