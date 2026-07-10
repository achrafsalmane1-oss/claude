export interface InboxRecord {
  address: string;
  domain: string;
  smtpHost: string;
  smtpPort: number;
  smtpUsername: string;
  /** Reference to the secret, not the secret itself, once a real vault is wired. */
  smtpPasswordRef: string;
  imapHost: string;
  imapPort: number;
}

export interface PurchaseResult {
  planId: string;
}

export interface DomainInboxProvider {
  /** Buy/extend a plan sized for one client's sending volume. */
  buyPlan(clientId: string, inboxCount: number): Promise<PurchaseResult>;

  /** Suggest available lookalike domains for the client's brand. */
  suggestDomains(companyName: string, count: number): Promise<string[]>;

  /** Purchase the given domains under the plan. */
  buyDomains(planId: string, domains: string[]): Promise<void>;

  /** Create SMTP inboxes across the domains and return their credentials. */
  createInboxes(
    planId: string,
    domains: string[],
    sendersPerDomain: number,
    senderName: string
  ): Promise<InboxRecord[]>;
}

const DOMAIN_SUFFIXES = ["hq", "team", "group", "co", "partners", "capital"];

/** Mock: fabricates domains and inbox records instantly, no money spent. */
export class MockDomainInboxProvider implements DomainInboxProvider {
  async buyPlan(clientId: string): Promise<PurchaseResult> {
    console.log(`[inbox:mock] plan purchased for client ${clientId}`);
    return { planId: `plan_mock_${clientId.slice(-6)}` };
  }

  async suggestDomains(companyName: string, count: number): Promise<string[]> {
    const base = companyName
      .toLowerCase()
      .replace(/\b(llc|inc|co|corp|capital|partners|holdings|group)\b/g, "")
      .replace(/[^a-z0-9]+/g, "")
      .slice(0, 18);
    return DOMAIN_SUFFIXES.slice(0, count).map((s) => `${base}${s}.com`);
  }

  async buyDomains(planId: string, domains: string[]) {
    console.log(`[inbox:mock] purchased domains ${domains.join(", ")} on ${planId}`);
  }

  async createInboxes(
    planId: string,
    domains: string[],
    sendersPerDomain: number,
    senderName: string
  ): Promise<InboxRecord[]> {
    const first = senderName.split(" ")[0]?.toLowerCase() || "team";
    const last = senderName.split(" ")[1]?.toLowerCase() || "";
    const locals = [first, last ? `${first}.${last}` : `${first}1`, last ? `${first[0]}${last}` : `${first}2`];
    return domains.flatMap((domain) =>
      locals.slice(0, sendersPerDomain).map((local, i) => ({
        address: `${local}@${domain}`,
        domain,
        smtpHost: `smtp.${domain}`,
        smtpPort: 587,
        smtpUsername: `${local}@${domain}`,
        smtpPasswordRef: `mock-secret-${domain}-${i}`,
        imapHost: `imap.${domain}`,
        imapPort: 993,
      }))
    );
  }
}

/**
 * "Winner" (SMTP inbox platform) adapter — STUB pending API docs + key.
 * Once the API surface is confirmed (buy plan / buy domain / create inbox
 * endpoints + auth scheme), implement each method as one HTTP call and this
 * drops in with no other code changes. Requires WINNER_API_KEY.
 */
export class WinnerDomainInboxProvider implements DomainInboxProvider {
  constructor(private apiKey: string) {
    void this.apiKey;
  }
  private unimplemented(): never {
    throw new Error(
      "WinnerDomainInboxProvider: awaiting provider API documentation — see README 'Going live'"
    );
  }
  async buyPlan(): Promise<PurchaseResult> {
    this.unimplemented();
  }
  async suggestDomains(): Promise<string[]> {
    this.unimplemented();
  }
  async buyDomains(): Promise<void> {
    this.unimplemented();
  }
  async createInboxes(): Promise<InboxRecord[]> {
    this.unimplemented();
  }
}
