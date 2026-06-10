import { NextResponse } from "next/server";
import { callOF } from "@/lib/of/client";

export async function GET() {
  const [hyperliquid, mids, events] = await Promise.all([
    callOF<Record<string, unknown>>("hyperliquid", { action: "get_account_summary" }).catch(() => null),
    callOF<Record<string, string>>("hyperliquid", { action: "get_all_mids" }).catch(() => null),
    callOF<unknown[]>("polymarket", { action: "get_events", limit: 8, active: true }).catch(() => null),
  ]);
  return NextResponse.json({ hyperliquid, mids, events });
}
