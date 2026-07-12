import { NextRequest, NextResponse } from "next/server";
import { seedDemo } from "@/lib/seedDemo";

export const maxDuration = 120;

/**
 * One-time demo seeder, callable over HTTPS after deploy (the build host can
 * reach the DB; the dev sandbox can't). Protected by SEED_SECRET, or allowed
 * when DEMO_MODE=true. Idempotent — wipes and recreates demo@havenx.app.
 */
export async function GET(req: NextRequest) {
  const secret = process.env.SEED_SECRET;
  const ok = secret
    ? req.nextUrl.searchParams.get("secret") === secret
    : process.env.DEMO_MODE === "true";
  if (!ok) return NextResponse.json({ error: "unauthorized" }, { status: 401 });

  try {
    await seedDemo();
    return NextResponse.json({ ok: true, demo: "demo@havenx.app" });
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : String(e) },
      { status: 500 }
    );
  }
}
