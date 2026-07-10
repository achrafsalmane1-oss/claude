import { NextRequest, NextResponse } from "next/server";
import { db } from "@/lib/db";
import { createSession } from "@/lib/session";

export async function GET(req: NextRequest) {
  const token = req.nextUrl.searchParams.get("token");
  if (!token) return NextResponse.redirect(new URL("/login", req.url));

  const record = await db.magicLinkToken.findUnique({ where: { token } });
  if (!record || record.usedAt || record.expiresAt < new Date()) {
    return NextResponse.redirect(new URL("/login?error=email", req.url));
  }

  const user = await db.user.findUnique({ where: { email: record.email } });
  if (!user) return NextResponse.redirect(new URL("/login", req.url));

  await db.magicLinkToken.update({
    where: { token },
    data: { usedAt: new Date() },
  });
  await createSession(user.id);

  const mandate = await db.mandate.findUnique({ where: { userId: user.id } });
  return NextResponse.redirect(
    new URL(mandate ? "/dashboard" : "/onboarding/buybox", req.url)
  );
}
