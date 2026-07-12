// Service wiring. Everything above this layer imports services from here,
// so pointing the app at real providers means changing only this file.
// Every real adapter activates automatically when its env key is present;
// otherwise the mock runs and the whole pipeline still works end-to-end.

import { MockOutreachService } from "./outreach";
import { MockEnrichmentService } from "./enrichment";
import {
  MockReplyClassificationService,
  AnthropicReplyClassificationService,
} from "./replyClassification";
import { MockBillingService, StripeBillingService } from "./billing";
import { DefaultNotificationService } from "./notifications";
import {
  MockLeadSourcingService,
  ClayLeadSourcingService,
  type LeadSourcingService,
} from "./sourcing";
import {
  MockEmailFinderService,
  MoltsetsEmailFinderService,
  type EmailFinderService,
} from "./emailFinder";
import {
  MockEmailVerifierService,
  OrbisearchEmailVerifierService,
  type EmailVerifierService,
} from "./emailVerifier";
import {
  MockDomainInboxProvider,
  WinnrDomainInboxProvider,
  type DomainInboxProvider,
} from "./inboxProvider";
import {
  MockSendingToolService,
  WinnrSendingToolService,
  type SendingToolService,
} from "./sender";
import {
  TemplateCopywritingService,
  AnthropicCopywritingService,
  type CopywritingService,
} from "./copywriting";
import type {
  BillingService,
  EnrichmentService,
  NotificationService,
  OutreachService,
  ReplyClassificationService,
} from "./types";

const env = process.env;

export const outreach: OutreachService = new MockOutreachService();
export const enrichment: EnrichmentService = new MockEnrichmentService();
export const notifications: NotificationService =
  new DefaultNotificationService();

export const billing: BillingService = env.STRIPE_SECRET_KEY
  ? new StripeBillingService(env.STRIPE_SECRET_KEY)
  : new MockBillingService();

// FULFILLMENT_LIVE flips the entire outbound backend from free, synchronous
// mocks to the real providers atomically. Left unset (staging/demo), the whole
// pipeline — sourcing, enrichment, verification, inbox provisioning, sending —
// runs on mocks: no Clay/Winnr credits burned, no domains bought, no real
// email sent, and the seeded demo account is safe. Set it to "true" (with the
// keys present) only when provisioning real paying clients.
const fulfillmentLive = env.FULFILLMENT_LIVE === "true";

export const sourcing: LeadSourcingService =
  fulfillmentLive && env.CLAY_WEBHOOK_URL
    ? new ClayLeadSourcingService(env.CLAY_WEBHOOK_URL)
    : new MockLeadSourcingService();

export const emailFinder: EmailFinderService =
  fulfillmentLive && env.MOLTSETS_API_KEY
    ? new MoltsetsEmailFinderService(env.MOLTSETS_API_KEY)
    : new MockEmailFinderService();

export const emailVerifier: EmailVerifierService =
  fulfillmentLive && env.ORBISEARCH_API_KEY
    ? new OrbisearchEmailVerifierService(env.ORBISEARCH_API_KEY)
    : new MockEmailVerifierService();

export const inboxProvider: DomainInboxProvider =
  fulfillmentLive && env.WINNR_API_KEY
    ? new WinnrDomainInboxProvider(env.WINNR_API_KEY)
    : new MockDomainInboxProvider();

export const sender: SendingToolService =
  fulfillmentLive && env.WINNR_API_KEY
    ? new WinnrSendingToolService(env.WINNR_API_KEY)
    : new MockSendingToolService();

// Copywriting + classification also gate on FULFILLMENT_LIVE so staging stays
// instant and free (template copy, keyword classification) and never depends on
// Anthropic credits; live uses Claude (with graceful fallback baked into each).
export const copywriter: CopywritingService =
  fulfillmentLive && env.ANTHROPIC_API_KEY
    ? new AnthropicCopywritingService(env.ANTHROPIC_API_KEY)
    : new TemplateCopywritingService();

export const replyClassifier: ReplyClassificationService =
  fulfillmentLive && env.ANTHROPIC_API_KEY
    ? new AnthropicReplyClassificationService(env.ANTHROPIC_API_KEY)
    : new MockReplyClassificationService();

export * from "./types";
