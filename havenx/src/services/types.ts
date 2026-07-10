// Service interfaces. Every external dependency (outreach infrastructure,
// enrichment, reply classification, billing, email) lives behind one of these
// interfaces. The UI and server actions only ever import from
// `src/services/index.ts`, so swapping a mock for a real provider is a
// one-line change there.

export interface SenderIdentity {
  name: string;
  company: string;
  signature?: string;
  replyToDisplay?: string;
}

export interface FunnelCounts {
  sourced: number;
  enriched: number;
  contacted: number;
  replied: number;
  notInterested: number;
  notNow: number;
  interested: number;
}

export interface OutreachService {
  /**
   * Provision outreach infrastructure for a new customer and begin warmup.
   * Real implementation: mailbox provisioning + warmup via Instantly/Salesforge,
   * LinkedIn seat setup, etc. Returns when provisioning has been *initiated*.
   */
  provisionIdentity(userId: string, identity: SenderIdentity): Promise<void>;

  /** Begin running multi-channel outreach against the user's active mandate. */
  startOutreach(userId: string): Promise<void>;

  /** Per-stage funnel counts for the user's pipeline. */
  getFunnelCounts(userId: string): Promise<FunnelCounts>;
}

export interface CompanyProfile {
  companyName: string;
  domain: string;
  description: string;
  incorporatedOn: Date | null;
  headcount: number | null;
  estRevenueUsd: number | null;
  location: string | null;
}

export interface EnrichmentService {
  /** Given a company domain, return a verified company profile (real impl: Clay). */
  enrichDomain(domain: string): Promise<CompanyProfile | null>;
}

export type ReplyClass = "NOT_INTERESTED" | "NOT_NOW" | "INTERESTED";

export interface ReplyClassificationService {
  /** Classify a raw owner reply into a pipeline disposition. */
  classify(replyText: string): Promise<ReplyClass>;
}

export interface CheckoutResult {
  /** Where to send the browser next (Stripe Checkout URL, or internal path in mock mode). */
  redirectUrl: string;
}

export interface BillingService {
  /**
   * Start the $499/mo subscription. Invoice one is charged immediately; the
   * first cycle runs 40 days (days 1-10 are setup/warmup), then renews every
   * 30 days.
   */
  startCheckout(email: string): Promise<CheckoutResult>;

  /** Whether this implementation talks to real Stripe. */
  readonly isLive: boolean;
}

export interface NotificationService {
  /** In-app notification + transactional email. Email send is mocked in dev. */
  notify(input: {
    userId: string;
    email: string;
    type: string;
    title: string;
    body: string;
    href?: string;
  }): Promise<void>;

  /** Send a magic sign-in link. */
  sendMagicLink(email: string, url: string): Promise<void>;
}
