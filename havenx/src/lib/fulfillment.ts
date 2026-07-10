import { db } from "./db";
import {
  inboxProvider,
  sender,
  copywriter,
  sourcing,
  emailFinder,
  emailVerifier,
  notifications,
} from "@/services";
import type { InboxRecord } from "@/services/inboxProvider";
import type { CampaignLead } from "@/services/sender";
import { pickMockReplies, MockSendingToolService } from "@/services/sender";
import { processReply } from "./replies";

const DOMAINS_PER_CLIENT = 10; // 2000/day ÷ (10 domains × 3 inboxes × ~70/inbox)
const INBOXES_PER_DOMAIN = 3;
const TOPUP_BUFFER = 1.3; // push 30% extra to absorb bounces/invalids

/**
 * Provisioning state machine. Idempotent and resumable: each step records
 * itself in `lastCompletedStep`; a failed step records `lastError` and is
 * retried on the next cron tick. Steps, in order:
 *   buy_plan → buy_domains → create_inboxes → connect_sender (warmup starts)
 * Then, once the subscription's day-11 mark passes: generate copy, create the
 * campaign, and flip to ACTIVE.
 */
export async function advanceProvisioning(userId: string) {
  const [infra, user] = await Promise.all([
    db.infrastructure.findUnique({ where: { userId } }),
    db.user.findUnique({
      where: { id: userId },
      include: { mandate: true, subscription: true },
    }),
  ]);
  if (!infra || !user?.mandate || !user.subscription) return;
  if (infra.status === "ACTIVE" || infra.status === "PAUSED") return;

  const mandate = user.mandate;

  try {
    let { planId, domains, senderAccountIds } = infra;
    let inboxes = (infra.inboxes as InboxRecord[] | null) ?? [];
    let step = infra.lastCompletedStep;

    if (!step) {
      const plan = await inboxProvider.buyPlan(
        userId,
        DOMAINS_PER_CLIENT * INBOXES_PER_DOMAIN
      );
      planId = plan.planId;
      step = "buy_plan";
      await db.infrastructure.update({
        where: { userId },
        data: { status: "PROVISIONING", planId, lastCompletedStep: step, lastError: null },
      });
    }

    if (step === "buy_plan") {
      domains = await inboxProvider.suggestDomains(
        mandate.senderCompany,
        DOMAINS_PER_CLIENT
      );
      await inboxProvider.buyDomains(planId!, domains);
      step = "buy_domains";
      await db.infrastructure.update({
        where: { userId },
        data: { domains, lastCompletedStep: step, lastError: null },
      });
    }

    if (step === "buy_domains") {
      inboxes = await inboxProvider.createInboxes(
        planId!,
        domains,
        INBOXES_PER_DOMAIN,
        mandate.senderName
      );
      step = "create_inboxes";
      await db.infrastructure.update({
        where: { userId },
        data: { inboxes: JSON.parse(JSON.stringify(inboxes)), lastCompletedStep: step, lastError: null },
      });
    }

    if (step === "create_inboxes") {
      senderAccountIds = await sender.connectInboxes(inboxes);
      step = "connect_sender";
      await db.infrastructure.update({
        where: { userId },
        data: {
          senderAccountIds,
          lastCompletedStep: step,
          status: "WARMING",
          warmupStartedAt: infra.warmupStartedAt ?? new Date(),
          lastError: null,
        },
      });
    }

    // Day 11+: warmup done → generate copy, create campaign, go live.
    if (step === "connect_sender") {
      if (new Date() < user.subscription.outreachStartsAt) return;

      const copy = await copywriter.generateCampaignCopy(mandate);
      const campaignId = await sender.createCampaign({
        name: `${mandate.senderCompany} — buy-box outreach`,
        accountIds: senderAccountIds,
        copy,
        dailyLimit: infra.dailySendTarget,
      });
      await db.infrastructure.update({
        where: { userId },
        data: {
          campaignId,
          copyVariants: JSON.parse(JSON.stringify(copy)) ,
          status: "ACTIVE",
          activatedAt: new Date(),
          lastCompletedStep: "campaign_live",
          lastError: null,
        },
      });
      await notifications.notify({
        userId,
        email: user.email,
        type: "outreach_live",
        title: "Outreach is live",
        body: "Warmup is complete and outreach in your name has started. Interested owners will appear in your dashboard as replies come in.",
        href: "/dashboard",
      });
    }
  } catch (e) {
    await db.infrastructure.update({
      where: { userId },
      data: { lastError: e instanceof Error ? e.message : String(e) },
    });
    console.error(`[fulfillment] provisioning error for ${userId}:`, e);
  }
}

/**
 * Daily top-up (cron, Mon-Fri): keep every active client's campaign fed so
 * it never runs out — source → find email → verify → niche variant → push.
 */
export async function topUpClient(userId: string) {
  const [infra, user] = await Promise.all([
    db.infrastructure.findUnique({ where: { userId } }),
    db.user.findUnique({ where: { id: userId }, include: { mandate: true } }),
  ]);
  if (!infra || infra.status !== "ACTIVE" || !infra.campaignId || !user?.mandate) {
    return { pushed: 0 };
  }

  const queued = await sender.getQueueDepth(infra.campaignId);
  const needed = Math.max(
    0,
    Math.ceil(infra.dailySendTarget * TOPUP_BUFFER) - queued
  );
  if (needed === 0) return { pushed: 0 };

  // 1. Source fresh owners (skip domains we already have for this client).
  const raw = await sourcing.source(user.mandate, needed);
  const existing = new Set(
    (
      await db.prospect.findMany({
        where: { userId },
        select: { domain: true },
      })
    ).map((p) => p.domain)
  );
  const fresh = raw.filter((l) => !existing.has(l.domain));

  const leads: CampaignLead[] = [];
  for (const lead of fresh) {
    // 2. Persist as SOURCED.
    const prospect = await db.prospect.create({
      data: {
        userId,
        stage: "SOURCED",
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

    // 3. Find + verify the owner's email.
    const found = await emailFinder.find(lead.ownerName, lead.domain);
    if (!found) continue;
    const verdict = await emailVerifier.verify(found.email);
    if (verdict === "invalid") {
      await db.prospect.update({
        where: { id: prospect.id },
        data: { emailStatus: "invalid" },
      });
      continue;
    }

    // 4. Niche variant for copy personalization (2-3 words, lowercase).
    const niche = await copywriter.nicheVariant(
      user.mandate.industries[0] ?? "services",
      lead.description
    );

    await db.prospect.update({
      where: { id: prospect.id },
      data: {
        stage: "ENRICHED",
        enrichedAt: new Date(),
        contactEmail: found.email,
        emailStatus: verdict === "deliverable" ? "verified" : "found",
        nicheVariant: niche,
      },
    });

    if (verdict === "deliverable") {
      leads.push({
        prospectId: prospect.id,
        email: found.email,
        firstName: lead.ownerName.split(" ")[0],
        companyName: lead.companyName,
        niche,
      });
    }
  }

  // 5. Push verified leads into the campaign.
  if (leads.length > 0) {
    const ids = await sender.addLeads(infra.campaignId, leads);
    await Promise.all(
      leads.map((l, i) =>
        db.prospect.update({
          where: { id: l.prospectId },
          data: { senderLeadId: ids[i] },
        })
      )
    );
  }

  // 6. Snapshot today's funnel for the dashboard chart.
  await snapshotFunnel(userId);

  // Dev only: the mock sender simulates a trickle of inbound replies so the
  // demo pipeline keeps moving end-to-end.
  if (sender instanceof MockSendingToolService) {
    for (const { prospect, replyText } of await pickMockReplies(userId)) {
      await processReply(prospect.id, replyText);
    }
  }

  return { pushed: leads.length };
}

export async function snapshotFunnel(userId: string) {
  const [sourced, enriched, contacted, replied, interested] = await Promise.all([
    db.prospect.count({ where: { userId } }),
    db.prospect.count({ where: { userId, stage: { in: ["ENRICHED", "CONTACTED", "REPLIED"] } } }),
    db.prospect.count({ where: { userId, stage: { in: ["CONTACTED", "REPLIED"] } } }),
    db.prospect.count({ where: { userId, stage: "REPLIED" } }),
    db.prospect.count({ where: { userId, replyDisposition: "INTERESTED" } }),
  ]);
  const today = new Date();
  today.setUTCHours(0, 0, 0, 0);
  await db.funnelSnapshot.upsert({
    where: { userId_date: { userId, date: today } },
    update: { sourced, enriched, contacted, replied, interested },
    create: { userId, date: today, sourced, enriched, contacted, replied, interested },
  });
}
