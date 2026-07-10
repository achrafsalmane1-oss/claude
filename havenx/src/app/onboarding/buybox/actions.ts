"use server";

import { redirect } from "next/navigation";
import { z } from "zod";
import { db } from "@/lib/db";
import { getCurrentUser } from "@/lib/session";
import { outreach, notifications } from "@/services";

const mandateSchema = z.object({
  industries: z.array(z.string().min(1)).min(1),
  geographies: z.array(z.string().min(1)).min(1),
  revenueMinUsd: z.number().int().nonnegative().nullable(),
  revenueMaxUsd: z.number().int().nonnegative().nullable(),
  ebitdaMinUsd: z.number().int().nonnegative().nullable(),
  ebitdaMaxUsd: z.number().int().nonnegative().nullable(),
  employeesMin: z.number().int().nonnegative().nullable(),
  employeesMax: z.number().int().nonnegative().nullable(),
  businessModelKeywords: z.array(z.string()),
  mustHaves: z.string(),
  hardExclusions: z.string(),
  ownerSituations: z.array(z.string()),
  senderName: z.string().min(1),
  senderCompany: z.string().min(1),
  senderSignature: z.string(),
  senderReplyToName: z.string(),
  thesis: z.string(),
});

export type MandateInput = z.infer<typeof mandateSchema>;

export async function saveMandate(input: MandateInput) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");

  const data = mandateSchema.parse(input);

  await db.mandate.upsert({
    where: { userId: user.id },
    update: { ...data, active: true },
    create: { ...data, userId: user.id, active: true },
  });

  await outreach.provisionIdentity(user.id, {
    name: data.senderName,
    company: data.senderCompany,
    signature: data.senderSignature || undefined,
    replyToDisplay: data.senderReplyToName || undefined,
  });
  await outreach.startOutreach(user.id);

  await notifications.notify({
    userId: user.id,
    email: user.email,
    type: "mandate_active",
    title: "Your buy-box is live",
    body: "Sourcing has started for your mandate. Outreach in your name begins on day 11, after infrastructure warmup completes.",
    href: "/dashboard",
  });

  redirect("/dashboard");
}
