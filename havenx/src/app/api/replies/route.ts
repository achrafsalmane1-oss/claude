import { NextRequest, NextResponse } from "next/server";
import { z } from "zod";
import { db } from "@/lib/db";
import { replyClassifier, notifications } from "@/services";

const payload = z.object({
  prospectId: z.string(),
  replyText: z.string().min(1),
});

/**
 * Inbound-reply seam. The real outreach provider posts owner replies here;
 * the reply is classified, the pipeline updated, and — when interested — the
 * customer is notified in-app + by email. Protected by REPLY_WEBHOOK_SECRET
 * when set (always set it in production).
 */
export async function POST(req: NextRequest) {
  const secret = process.env.REPLY_WEBHOOK_SECRET;
  if (secret && req.headers.get("x-webhook-secret") !== secret) {
    return NextResponse.json({ error: "unauthorized" }, { status: 401 });
  }

  const parsed = payload.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: "invalid payload" }, { status: 400 });
  }
  const { prospectId, replyText } = parsed.data;

  const prospect = await db.prospect.findUnique({
    where: { id: prospectId },
    include: { user: true },
  });
  if (!prospect) {
    return NextResponse.json({ error: "prospect not found" }, { status: 404 });
  }

  const disposition = await replyClassifier.classify(replyText);

  await db.prospect.update({
    where: { id: prospect.id },
    data: {
      stage: "REPLIED",
      replyDisposition: disposition,
      replyText,
      repliedAt: new Date(),
    },
  });

  if (disposition === "INTERESTED") {
    await notifications.notify({
      userId: prospect.userId,
      email: prospect.user.email,
      type: "interested_reply",
      title: "An owner just replied with interest",
      body: `An owner in your buy-box just replied with interest — ${prospect.ownerName} at ${prospect.companyName}. View the introduction in your dashboard.`,
      href: "/dashboard/interested",
    });
  }

  return NextResponse.json({ ok: true, disposition });
}
