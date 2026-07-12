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
import type { CampaignCopy } from "@/services/copywriting";
import { processReply } from "./replies";

const DOMAINS_PER_CLIENT = 10; // 2000/day ÷ (10 domains × 3 inboxes × ~67/inbox)
const INBOXES_PER_DOMAIN = 3;
const SEND_BATCH = 200; // emails sent per dispatch-cron run per client
const ENRICH_BATCH = 250; // owners enriched per top-up run per client (bounds runtime)

/**
 * Provisioning state machine. Idempotent and resumable: each step records
 * itself in `lastCompletedStep`; a failed step records `lastError` and is
 * retried on the next cron tick.
 *   buy_plan → buy_domains → create_inboxes → connect_sender (warmup starts)
 * Then, once the subscription's day-11 mark passes: generate copy → ACTIVE.
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

  // MONEY INTERLOCK: when the real (paid) providers are active, never spend
  // infrastructure money on an account that hasn't actually paid. A real
  // Stripe subscription id is the proof of payment. Mock/staging mode skips
  // this so the demo pipeline still runs end-to-end for free.
  if (process.env.FULFILLMENT_LIVE === "true" && !user.subscription.stripeSubscriptionId) {
    return;
  }

  const mandate = user.mandate;

  try {
    let { planId, domains } = infra;
    let inboxes = (infra.inboxes as unknown as InboxRecord[] | null) ?? [];
    let domainIds: Record<string, string> = {};
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
      domainIds = await inboxProvider.buyDomains(planId!, domains);
      step = "buy_domains";
      await db.infrastructure.update({
        where: { userId },
        data: {
          domains: Object.keys(domainIds),
          inboxes: JSON.parse(JSON.stringify({ __domainIds: domainIds })),
          lastCompletedStep: step,
          lastError: null,
        },
      });
    } else if (step === "buy_domains") {
      const stored = infra.inboxes as { __domainIds?: Record<string, string> } | null;
      domainIds = stored?.__domainIds ?? Object.fromEntries((domains ?? []).map((d) => [d, d]));
    }

    if (step === "buy_domains") {
      inboxes = await inboxProvider.createInboxes(
        domainIds,
        INBOXES_PER_DOMAIN,
        mandate.senderName
      );
      step = "create_inboxes";
      await db.infrastructure.update({
        where: { userId },
        data: {
          inboxes: JSON.parse(JSON.stringify(inboxes)),
          lastCompletedStep: step,
          lastError: null,
        },
      });
    }

    if (step === "create_inboxes") {
      await sender.setupWarming(inboxes.map((i) => i.providerUserId));
      step = "connect_sender";
      await db.infrastructure.update({
        where: { userId },
        data: {
          senderAccountIds: inboxes.map((i) => i.providerUserId),
          lastCompletedStep: step,
          status: "WARMING",
          warmupStartedAt: infra.warmupStartedAt ?? new Date(),
          lastError: null,
        },
      });
    }

    // Day 11+: warmup done → generate copy, go live. (No external campaign —
    // this app is the sequencer; sending happens in the dispatch cron.)
    if (step === "connect_sender") {
      if (new Date() < user.subscription.outreachStartsAt) return;

      const copy = await copywriter.generateCampaignCopy(mandate);
      await db.infrastructure.update({
        where: { userId },
        data: {
          copyVariants: JSON.parse(JSON.stringify(copy)),
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
 * Enrichment top-up (cron, weekdays): keep a healthy backlog of send-ready
 * (ENRICHED + verified) owners so the dispatch cron never starves —
 * source → find email → verify → niche variant. No sending here.
 */
export async function topUpClient(userId: string) {
  const [infra, user] = await Promise.all([
    db.infrastructure.findUnique({ where: { userId } }),
    db.user.findUnique({ where: { id: userId }, include: { mandate: true } }),
  ]);
  if (!infra || infra.status !== "ACTIVE" || !user?.mandate) return { enriched: 0 };

  // Keep ~2 days of sending queued as verified, deliverable, un-contacted.
  const ready = await db.prospect.count({
    where: { userId, stage: "ENRICHED", emailStatus: "verified", contactedAt: null },
  });
  const needed = Math.min(ENRICH_BATCH, Math.max(0, infra.dailySendTarget * 2 - ready));
  if (needed === 0) return { enriched: 0 };

  const raw = await sourcing.source(user.mandate, Math.ceil(needed * 1.4));
  const existing = new Set(
    (await db.prospect.findMany({ where: { userId }, select: { domain: true } })).map(
      (p) => p.domain
    )
  );
  const fresh = raw.filter((l) => !existing.has(l.domain));

  let enriched = 0;
  for (const lead of fresh) {
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

    const found = await emailFinder.find({
      fullName: lead.ownerName,
      domain: lead.domain,
      linkedinUrl: lead.linkedinUrl,
    });
    if (!found) continue;

    const verdict = await emailVerifier.verify(found.email);
    if (verdict === "invalid") {
      await db.prospect.update({ where: { id: prospect.id }, data: { emailStatus: "invalid" } });
      continue;
    }

    const niche = await copywriter.nicheVariant(
      user.mandate.industries[0] ?? "services",
      lead.description
    );

    await db.prospect.update({
      where: { id: prospect.id },
      data: {
        stage: "ENRICHED",
        enrichedAt: new Date(),
        contactEmail: found.email.toLowerCase(),
        emailStatus: verdict === "deliverable" ? "verified" : "found",
        nicheVariant: niche,
      },
    });
    if (verdict === "deliverable") enriched++;
  }

  await snapshotFunnel(userId);
  return { enriched };
}

function startOfUtcDay(): Date {
  const d = new Date();
  d.setUTCHours(0, 0, 0, 0);
  return d;
}

function fill(t: string, v: { firstName: string; companyName: string; niche: string }) {
  return t
    .replaceAll("{{firstName}}", v.firstName)
    .replaceAll("{{companyName}}", v.companyName)
    .replaceAll("{{niche}}", v.niche);
}

/**
 * Send dispatch (cron, weekday business hours): sends the day's outreach for
 * one client up to its daily target, paced across runs and rotated across
 * inboxes. Picks verified, deliverable, un-contacted owners and sends in the
 * client's name. Never sends on weekends (the cron schedule enforces that).
 */
export async function dispatchSends(userId: string) {
  const infra = await db.infrastructure.findUnique({ where: { userId } });
  if (!infra || infra.status !== "ACTIVE") return { sent: 0 };

  const inboxes = (infra.inboxes as unknown as InboxRecord[] | null) ?? [];
  const copy = infra.copyVariants as unknown as CampaignCopy | null;
  if (inboxes.length === 0 || !copy?.variants?.length) return { sent: 0 };

  const sentToday = await db.prospect.count({
    where: { userId, contactedAt: { gte: startOfUtcDay() } },
  });
  const remaining = Math.min(SEND_BATCH, infra.dailySendTarget - sentToday);
  if (remaining <= 0) return { sent: 0 };

  const batch = await db.prospect.findMany({
    where: { userId, stage: "ENRICHED", emailStatus: "verified", contactedAt: null },
    take: remaining,
    orderBy: { enrichedAt: "asc" },
  });

  let sent = 0;
  for (let i = 0; i < batch.length; i++) {
    const p = batch[i];
    if (!p.contactEmail) continue;
    const inbox = inboxes[i % inboxes.length];
    const variant = copy.variants[i % copy.variants.length];
    const vars = {
      firstName: p.ownerName.split(" ")[0],
      companyName: p.companyName,
      niche: p.nicheVariant ?? "your industry",
    };
    const messageId = await sender.sendEmail({
      fromUserId: inbox.providerUserId,
      to: p.contactEmail,
      subject: fill(variant.subject, vars),
      body: fill(variant.body, vars),
    });
    if (!messageId) continue;
    await db.prospect.update({
      where: { id: p.id },
      data: { stage: "CONTACTED", contactedAt: new Date(), pushedAt: new Date(), senderLeadId: messageId },
    });
    sent++;
  }

  if (sent > 0) await snapshotFunnel(userId);
  return { sent };
}

/**
 * Reply poll (cron): pulls new inbound mail account-wide from the sending
 * provider, dedupes by provider message id, matches each reply to a prospect
 * by sender email, and runs it through classification + notification.
 */
export async function pollReplies() {
  const anchor = await db.infrastructure.findFirst({
    where: { status: "ACTIVE" },
    orderBy: { updatedAt: "asc" },
  });
  const { inbound, nextCursor } = await sender.fetchInbound(anchor?.inboxCursor);

  let processed = 0;
  for (const msg of inbound) {
    if (msg.isWarmup) continue;
    const seen = await db.processedInbound.findUnique({ where: { messageId: msg.messageId } });
    if (seen) continue;
    await db.processedInbound.create({ data: { messageId: msg.messageId } });

    const prospect = await db.prospect.findFirst({
      where: { contactEmail: msg.fromEmail, stage: { in: ["CONTACTED", "REPLIED"] } },
      orderBy: { contactedAt: "desc" },
    });
    if (!prospect) continue;
    await processReply(prospect.id, msg.text);
    processed++;
  }

  if (anchor && nextCursor !== undefined) {
    await db.infrastructure.update({
      where: { userId: anchor.userId },
      data: { inboxCursor: nextCursor },
    });
  }
  return { processed };
}

export async function snapshotFunnel(userId: string) {
  const [sourced, enriched, contacted, replied, interested] = await Promise.all([
    db.prospect.count({ where: { userId } }),
    db.prospect.count({ where: { userId, stage: { in: ["ENRICHED", "CONTACTED", "REPLIED"] } } }),
    db.prospect.count({ where: { userId, stage: { in: ["CONTACTED", "REPLIED"] } } }),
    db.prospect.count({ where: { userId, stage: "REPLIED" } }),
    db.prospect.count({ where: { userId, replyDisposition: "INTERESTED" } }),
  ]);
  const today = startOfUtcDay();
  await db.funnelSnapshot.upsert({
    where: { userId_date: { userId, date: today } },
    update: { sourced, enriched, contacted, replied, interested },
    create: { userId, date: today, sourced, enriched, contacted, replied, interested },
  });
}
