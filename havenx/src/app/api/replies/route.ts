import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { processReply } from "@/lib/replies";

const payload = z.object({
  prospectId: z.string(),
  replyText: z.string().min(1),
});

/**
 * Manual/dev inbound-reply seam: classify a reply for a known prospect id.
 * Production replies arrive via /api/webhooks/sender (matched by email).
 * Protected by REPLY_WEBHOOK_SECRET when set (always set it in production).
 */
export async function POST(req: NextRequest) {
  const secret = process.env.REPLY_WEBHOOK_SECRET;
  if (secret && req.headers.get("x-webhook-secret") !== secret) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const parsed = payload.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid payload" }, { status: 400 });
  }

  const disposition = await processReply(
    parsed.data.prospectId,
    parsed.data.replyText
  );
  if (!disposition) {
    return NextResponse.json({ error: "prospect not found" }, { status: 404 });
  }

  return NextResponse.json({ ok: true, disposition });
}
