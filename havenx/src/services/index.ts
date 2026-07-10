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
  HttpEmailFinderService,
  type EmailFinderService,
} from "./emailFinder";
import {
  MockEmailVerifierService,
  ReoonEmailVerifierService,
  type EmailVerifierService,
} from "./emailVerifier";
import {
  MockDomainInboxProvider,
  WinnerDomainInboxProvider,
  type DomainInboxProvider,
} from "./inboxProvider";
import {
  MockSendingToolService,
  InstantlySendingToolService,
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

export const sourcing: LeadSourcingService = env.CLAY_WEBHOOK_URL
  ? new ClayLeadSourcingService(env.CLAY_WEBHOOK_URL)
  : new MockLeadSourcingService();

export const emailFinder: EmailFinderService =
  env.EMAIL_FINDER_API_URL && env.EMAIL_FINDER_API_KEY
    ? new HttpEmailFinderService(env.EMAIL_FINDER_API_URL, env.EMAIL_FINDER_API_KEY)
    : new MockEmailFinderService();

export const emailVerifier: EmailVerifierService = env.REOON_API_KEY
  ? new ReoonEmailVerifierService(env.REOON_API_KEY)
  : new MockEmailVerifierService();

export const inboxProvider: DomainInboxProvider = env.WINNER_API_KEY
  ? new WinnerDomainInboxProvider(env.WINNER_API_KEY)
  : new MockDomainInboxProvider();

export const sender: SendingToolService = env.INSTANTLY_API_KEY
  ? new InstantlySendingToolService(env.INSTANTLY_API_KEY)
  : new MockSendingToolService();

export const copywriter: CopywritingService = env.ANTHROPIC_API_KEY
  ? new AnthropicCopywritingService(env.ANTHROPIC_API_KEY)
  : new TemplateCopywritingService();

export const replyClassifier: ReplyClassificationService = env.ANTHROPIC_API_KEY
  ? new AnthropicReplyClassificationService(env.ANTHROPIC_API_KEY)
  : new MockReplyClassificationService();

export * from "./types";
