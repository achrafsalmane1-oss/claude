import { db } from "./db";
import { replyClassifier, notifications } from "@/services";

/**
 * Single path for every inbound owner reply — the /api/replies seam, the
 * sending-tool webhook, and the dev reply simulator all land here.
 * Classifies, updates the pipeline, and notifies the customer on interest.
 */
export async function processReply(prospectId: string, replyText: string) {
  const prospect = await db.prospect.findUnique({
    where: { id: prospectId },
    include: { user: true },
  });
  if (!prospect) return null;

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

  return disposition;
}
