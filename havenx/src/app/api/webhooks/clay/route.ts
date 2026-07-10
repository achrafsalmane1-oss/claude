import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { db } from "@/lib/db";

const leadSchema = z.object({
  clientId: z.string(),
  ownerName: z.string(),
  ownerTitle: z.string().optional(),
  linkedinUrl: z.string().optional(),
  companyName: z.string(),
  domain: z.string(),
  description: z.string().optional(),
  headcount: z.number().optional(),
  estRevenueUsd: z.number().optional(),
  location: z.string().optional(),
  email: z.string().optional(), // if Clay already enriched the email
});

/**
 * Clay results webhook. The Clay workflow POSTs each sourced (and optionally
 * email-enriched) owner here with the clientId we sent in the sourcing
 * request. Rows land as SOURCED (or ENRICHED when an email is included) and
 * the next top-up cron verifies + pushes them.
 * Protect with ?secret=<CLAY_WEBHOOK_SECRET>.
 */
export async function POST(req: NextRequest) {
  const secret = process.env.CLAY_WEBHOOK_SECRET;
  if (secret && req.nextUrl.searchParams.get("secret") !== secret) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const body = await req.json().catch(() => null);
  const rows = Array.isArray(body) ? body : [body];
  let created = 0;

  for (const row of rows) {
    const parsed = leadSchema.safeParse(row);
    if (!parsed.success) continue;
    const lead = parsed.data;

    const exists = await db.prospect.findFirst({
      where: { userId: lead.clientId, domain: lead.domain },
      select: { id: true },
    });
    if (exists) continue;

    await db.prospect.create({
      data: {
        userId: lead.clientId,
        stage: lead.email ? "ENRICHED" : "SOURCED",
        enrichedAt: lead.email ? new Date() : null,
        contactEmail: lead.email?.toLowerCase(),
        emailStatus: lead.email ? "found" : null,
        ownerName: lead.ownerName,
        ownerTitle: lead.ownerTitle,
        linkedinUrl: lead.linkedinUrl,
        companyName: lead.companyName,
        domain: lead.domain,
        description: lead.description,
        headcount: lead.headcount,
        estRevenueUsd: lead.estRevenueUsd,
        location: lead.location,
      },
    });
    created++;
  }

  return NextResponse.json({ created });
}
