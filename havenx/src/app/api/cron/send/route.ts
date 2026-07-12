import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { dispatchSends } from "@/lib/fulfillment";

export const maxDuration = 300;

function authorized(req: NextRequest) {
  const secret = process.env.CRON_SECRET;
  if (!secret) return process.env.DEMO_MODE === "true";
  return req.headers.get("authorization") === `Bearer ${secret}`;
}

/**
 * Send dispatch cron (weekday business hours, several times/day): sends each
 * active client's outreach in their name, paced to the daily target. Weekends
 * are skipped (schedule + guard).
 */
export async function GET(req: NextRequest) {
  if (!authorized(req)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }
  const day = new Date().getUTCDay();
  const force = req.nextUrl.searchParams.get("force") === "1" && process.env.DEMO_MODE === "true";
  if ((day === 0 || day === 6) && !force) {
    return NextResponse.json({ skipped: "weekend" });
  }

  const active = await db.infrastructure.findMany({
    where: { status: "ACTIVE" },
    select: { userId: true },
  });
  const sent: Record<string, number> = {};
  for (const { userId } of active) {
    sent[userId] = (await dispatchSends(userId)).sent;
  }
  return NextResponse.json({ sent });
}
