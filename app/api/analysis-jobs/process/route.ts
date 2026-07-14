import { handleCallback } from "@vercel/queue";

export const runtime = "nodejs";
export const maxDuration = 180;

type AnalysisJob = { analysisId: string };

const queueHandler = handleCallback<AnalysisJob>(async (job, metadata) => {
  console.info("Processing Orbit analysis job", {
    analysisId: job?.analysisId,
    messageId: metadata.messageId,
    deliveryCount: metadata.deliveryCount,
  });
  if (!job || typeof job.analysisId !== "string") {
    throw new Error("Queue message is missing analysisId");
  }
  const secret = process.env.ORBIT_CAPTURE_SECRET;
  const deploymentHost = process.env.VERCEL_URL;
  const configuredBase = process.env.ORBIT_PUBLIC_BASE_URL;
  const enqueueUrl = process.env.ORBIT_QUEUE_ENQUEUE_URL;
  if (!secret || (!enqueueUrl && !deploymentHost && !configuredBase)) {
    throw new Error("Queue worker environment is incomplete");
  }
  const base = (
    enqueueUrl ? new URL(enqueueUrl).origin : deploymentHost ? `https://${deploymentHost}` : configuredBase!
  ).replace(/\/$/, "");
  const url = new URL(`${base}/api/v1/analyses/internal/process`);
  url.searchParams.set("analysis_id", job.analysisId);
  const response = await fetch(url, {
    method: "POST",
    headers: { "X-Orbit-Capture-Secret": secret },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Analysis worker failed with HTTP ${response.status}`);
  }
  console.info("Orbit analysis job completed", { analysisId: job.analysisId, messageId: metadata.messageId });
}, {
  visibilityTimeoutSeconds: 240,
  retry: (_error, metadata) => metadata.deliveryCount < 4 ? { afterSeconds: 30 } : { acknowledge: true },
});

// Preserve the direct SDK handler export Vercel uses for queue discovery while
// narrowing its structural input union to Next.js' route-handler contract.
export const POST = queueHandler as (request: Request) => Promise<Response>;
