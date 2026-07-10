"use server";

import { revalidatePath } from "next/cache";
import { db } from "@/lib/db";
import { getCurrentUser } from "@/lib/session";

export async function claimProspect(prospectId: string) {
  const user = await getCurrentUser();
  if (!user) return;
  await db.prospect.updateMany({
    where: { id: prospectId, userId: user.id, replyDisposition: "INTERESTED" },
    data: { introStatus: "CLAIMED", claimedAt: new Date() },
  });
  revalidatePath("/dashboard");
  revalidatePath("/dashboard/interested");
}

export async function toggleBookingLink(prospectId: string, enabled: boolean) {
  const user = await getCurrentUser();
  if (!user) return;
  await db.prospect.updateMany({
    where: { id: prospectId, userId: user.id, replyDisposition: "INTERESTED" },
    data: { bookingLinkRequested: enabled },
  });
  revalidatePath("/dashboard/interested");
}

export async function markNotificationsRead() {
  const user = await getCurrentUser();
  if (!user) return;
  await db.notification.updateMany({
    where: { userId: user.id, readAt: null },
    data: { readAt: new Date() },
  });
  revalidatePath("/dashboard", "layout");
}
