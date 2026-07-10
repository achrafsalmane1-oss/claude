import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { createSession } from "@/lib/session";

// One-click sign-in as the seeded demo account. Dev/demo environments only.
export async function GET(req: NextRequest) {
  if (process.env.DEMO_MODE !== "true") {
    return NextResponse.redirect(new URL("/", req.url));
  }
  const user = await db.user.findUnique({
    where: { email: "demo@havenx.app" },
  });
  if (!user) return NextResponse.redirect(new URL("/checkout", req.url));
  await createSession(user.id);
  return NextResponse.redirect(new URL("/dashboard", req.url));
}
