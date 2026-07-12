import { NextRequest, NextResponse } from "next/server";
import { pollReplies } from "@/lib/fulfillment";

export const maxDuration = 120;

function authorized(req: NextRequest) {
  const secret = process.env.CRON_SECRET;
  if (!secret) return process.env.DEMO_MODE === "true";
  return req.headers.get("authorization") === `Bearer ${secret}`;
}

/**
 * Reply poll cron (frequent, incl. weekends — owners reply anytime): pulls new
 * inbound mail from the sending provider, classifies replies, and notifies
 * customers of interested owners. Idempotent (dedupes by provider message id).
 */
export async function GET(req: NextRequest) {
  if (!authorized(req)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const { processed } = await pollReplies();
  return NextResponse.json({ processed });
}
