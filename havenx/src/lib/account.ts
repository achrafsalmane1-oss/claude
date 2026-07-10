import { db } from "./db";
import { outreach, notifications } from "@/services";
import { subscriptionDates } from "@/services/billing";

/**
 * Called after a successful payment (mock activation route or Stripe
 * webhook): creates the account + subscription with the 40-day first cycle
 * and kicks off (mocked) infrastructure provisioning + warmup.
 */
export async function activateAccount(
  email: string,
  stripe?: { customerId?: string; subscriptionId?: string }
) {
  const user = await db.user.upsert({
    where: { email },
    update: {},
    create: { email },
  });

  const existing = await db.subscription.findUnique({
    where: { userId: user.id },
  });
  if (!existing) {
    const dates = subscriptionDates();
    await db.subscription.create({
      data: {
        userId: user.id,
        status: "ACTIVE",
        stripeCustomerId: stripe?.customerId,
        stripeSubscriptionId: stripe?.subscriptionId,
        ...dates,
      },
    });

    await outreach.provisionIdentity(user.id, {
      name: user.name ?? email,
      company: "",
    });

    // Ops record for the fulfillment pipeline; the provisioning cron picks
    // it up (plan → domains → inboxes → warmup → campaign).
    await db.infrastructure.upsert({
      where: { userId: user.id },
      update: {},
      create: { userId: user.id },
    });

    await notifications.notify({
      userId: user.id,
      email,
      type: "welcome",
      title: "Welcome to HavenX",
      body: "Your outreach infrastructure is being provisioned. Days 1-10 cover setup and warmup — outreach begins day 11. Sourcing for your buy-box starts as soon as you define it.",
      href: "/onboarding/buybox",
    });
  }

  return user;
}
