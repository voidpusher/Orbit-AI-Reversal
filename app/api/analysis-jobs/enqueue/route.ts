import { DuplicateMessageError, send } from "@vercel/queue";
import { timingSafeEqual } from "node:crypto";

export const runtime = "nodejs";

function validSecret(candidate: string | null): boolean {
  const expected = process.env.ORBIT_CAPTURE_SECRET;
  if (!expected || !candidate) return false;
  const left = Buffer.from(candidate);
  const right = Buffer.from(expected);
  return left.length === right.length && timingSafeEqual(left, right);
}

export async function POST(request: Request) {
  if (!validSecret(request.headers.get("x-orbit-capture-secret"))) {
    return Response.json({ detail: "Unauthorized" }, { status: 401 });
  }
  const body = (await request.json().catch(() => null)) as { analysisId?: unknown } | null;
  if (!body || typeof body.analysisId !== "string" || !/^[0-9a-f-]{36}$/i.test(body.analysisId)) {
    return Response.json({ detail: "A valid analysisId is required" }, { status: 422 });
  }
  try {
    const result = await send(
      "orbit-analysis",
      { analysisId: body.analysisId },
      { idempotencyKey: body.analysisId, retentionSeconds: 86_400 },
    );
    return Response.json({ queued: true, messageId: result.messageId }, { status: 202 });
  } catch (error) {
    if (error instanceof DuplicateMessageError) {
      return Response.json({ queued: true, duplicate: true }, { status: 202 });
    }
    throw error;
  }
}
