import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { advanceProvisioning } from "@/lib/fulfillment";

export const maxDuration = 300;

function authorized(req: NextRequest) {
  const secret = process.env.CRON_SECRET;
  if (!secret) return process.env.DEMO_MODE === "true";
  return req.headers.get("authorization") === `Bearer ${secret}`;
}

/**
 * Hourly cron: advances every non-active account through the provisioning
 * state machine (plan → domains → inboxes → warmup → campaign live at day 11).
 * Failed steps retry on the next tick.
 */
export async function GET(req: NextRequest) {
  if (!authorized(req)) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  // DEMO_MODE escape hatch: ?force=1 skips the day-11 wait for testing.
  if (
    process.env.DEMO_MODE === "true" &&
    req.nextUrl.searchParams.get("force") === "1"
  ) {
    await db.subscription.updateMany({
      where: { outreachStartsAt: { gt: new Date() } },
      data: { outreachStartsAt: new Date() },
    });
  }

  const pending = await db.infrastructure.findMany({
    where: { status: { in: ["PENDING", "PROVISIONING", "WARMING", "FAILED"] } },
    select: { userId: true },
  });

  for (const { userId } of pending) {
    await advanceProvisioning(userId);
  }

  return NextResponse.json({ processed: pending.length });
}
