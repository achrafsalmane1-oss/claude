import { NextRequest, NextResponse } from "next/server";
import { activateAccount } from "@/lib/account";
import { createSession } from "@/lib/session";
import { billing } from "@/services";

// Mock-billing activation: stands in for the Stripe webhook + redirect flow.
// Disabled when real Stripe is configured.
export async function GET(req: NextRequest) {
  if (billing.isLive) {
    return NextResponse.redirect(new URL("/checkout", req.url));
  }
  const email = req.nextUrl.searchParams.get("email")?.trim().toLowerCase();
  if (!email || !email.includes("@")) {
    return NextResponse.redirect(new URL("/checkout?error=email", req.url));
  }
  const user = await activateAccount(email);
  await createSession(user.id);
  const dest = user.id && (await hasMandate(user.id)) ? "/dashboard" : "/onboarding/buybox";
  return NextResponse.redirect(new URL(dest, req.url));
}

async function hasMandate(userId: string) {
  const { db } = await import("@/lib/db");
  return Boolean(await db.mandate.findUnique({ where: { userId } }));
}
