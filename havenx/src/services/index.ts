// Service wiring. Everything above this layer imports services from here,
// so pointing the app at real providers means changing only this file.

import { MockOutreachService } from "./outreach";
import { MockEnrichmentService } from "./enrichment";
import { MockReplyClassificationService } from "./replyClassification";
import { MockBillingService, StripeBillingService } from "./billing";
import { DefaultNotificationService } from "./notifications";
import type {
  BillingService,
  EnrichmentService,
  NotificationService,
  OutreachService,
  ReplyClassificationService,
} from "./types";

export const outreach: OutreachService = new MockOutreachService();
export const enrichment: EnrichmentService = new MockEnrichmentService();
export const replyClassifier: ReplyClassificationService =
  new MockReplyClassificationService();
export const notifications: NotificationService =
  new DefaultNotificationService();

export const billing: BillingService = process.env.STRIPE_SECRET_KEY
  ? new StripeBillingService(process.env.STRIPE_SECRET_KEY)
  : new MockBillingService();

export * from "./types";
