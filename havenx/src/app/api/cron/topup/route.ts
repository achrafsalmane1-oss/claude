import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { topUpClient, snapshotFunnel } from "@/lib/fulfillment";

export const maxDuration = 300;

function authorized(req: NextRequest) {
  const secret = process.env.CRON_SECRET;
  if (!secret) return process.env.DEMO_MODE === "true";
  return req.headers.get("authorization") === `Bearer ${secret}`;
}

/**
 * Daily top-up cron (weekdays): keeps every active client's campaign fed to
 * its daily send target so campaigns never run out. Also snapshots the
 * funnel for warming accounts so their dashboards fill during days 1-10.
 */
export async function GET(req: NextRequest) {
  if (!authorized(req)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  // No sending Saturdays/Sundays (cron schedule also enforces this; belt & braces).
  const day = new Date().getUTCDay();
  const force = req.nextUrl.searchParams.get("force") === "1" && process.env.DEMO_MODE === "true";
  if ((day === 0 || day === 6) && !force) {
    return NextResponse.json({ skipped: "weekend" });
  }

  const active = await db.infrastructure.findMany({
    where: { status: "ACTIVE" },
    select: { userId: true },
  });
  const results: Record<string, number> = {};
  for (const { userId } of active) {
    results[userId] = (await topUpClient(userId)).pushed;
  }

  // Keep warming accounts' charts moving too (sourcing runs from day 1).
  const warming = await db.infrastructure.findMany({
    where: { status: "WARMING" },
    select: { userId: true },
  });
  for (const { userId } of warming) {
    await snapshotFunnel(userId);
  }

  return NextResponse.json({ active: results, warming: warming.length });
}
