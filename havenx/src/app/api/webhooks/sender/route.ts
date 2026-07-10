import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { processReply } from "@/lib/replies";

/**
 * Sending-tool reply webhook (Instantly "Reply Received" / equivalent).
 * Point the tool's webhook at this URL with ?secret=<SENDER_WEBHOOK_SECRET>.
 * Maps the reply back to a prospect by lead email, then classifies and
 * notifies via the shared reply path.
 */
export async function POST(req: NextRequest) {
  const secret = process.env.SENDER_WEBHOOK_SECRET;
  if (secret && req.nextUrl.searchParams.get("secret") !== secret) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const payload = await req.json().catch(() => null);
  if (!payload) {
    return NextResponse.json({ error: "invalid payload" }, { status: 400 });
  }

  // Instantly v2 reply events carry lead_email + reply_text_snippet/reply_text;
  // other tools use similar shapes. Normalize defensively.
  const email: string | undefined =
    payload.lead_email ?? payload.email ?? payload.lead?.email;
  const replyText: string | undefined =
    payload.reply_text ?? payload.reply_text_snippet ?? payload.text ?? payload.body;

  if (!email || !replyText) {
    return NextResponse.json({ ignored: true });
  }

  const prospect = await db.prospect.findFirst({
    where: {
      contactEmail: email.toLowerCase(),
      stage: { in: ["CONTACTED", "REPLIED"] },
    },
    orderBy: { contactedAt: "desc" },
  });
  if (!prospect) return NextResponse.json({ ignored: "no matching prospect" });

  const disposition = await processReply(prospect.id, replyText);
  return NextResponse.json({ ok: true, disposition });
}
