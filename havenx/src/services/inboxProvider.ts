export interface InboxRecord {
  address: string;
  domain: string;
  /** Provider's mailbox/user id — required to send and to poll this inbox. */
  providerUserId: string;
}

export interface PurchaseResult {
  planId: string;
}

export interface DomainInboxProvider {
  /** Optional plan/order step. Winnr charges per-domain, so this is a no-op there. */
  buyPlan(clientId: string, inboxCount: number): Promise<PurchaseResult>;

  /** Suggest available sending domains for the client's brand. */
  suggestDomains(companyName: string, count: number): Promise<string[]>;

  /** Purchase/register the domains. Returns the provider domain ids by name. */
  buyDomains(planId: string, domains: string[]): Promise<Record<string, string>>;

  /** Create SMTP inboxes across the domains. */
  createInboxes(
    domainIds: Record<string, string>,
    sendersPerDomain: number,
    senderName: string
  ): Promise<InboxRecord[]>;
}

const DOMAIN_SUFFIXES = ["hq", "team", "group", "co", "partners", "capital", "mail", "hub", "grp", "inc"];

/** Mock: fabricates domains and inbox records instantly, no money spent. */
export class MockDomainInboxProvider implements DomainInboxProvider {
  async buyPlan(clientId: string): Promise<PurchaseResult> {
    return { planId: `plan_mock_${clientId.slice(-6)}` };
  }

  async suggestDomains(companyName: string, count: number): Promise<string[]> {
    const base = companyName
      .toLowerCase()
      .replace(/\b(llc|inc|co|corp|capital|partners|holdings|group)\b/g, "")
      .replace(/[^a-z0-9]+/g, "")
      .slice(0, 16);
    return DOMAIN_SUFFIXES.slice(0, count).map((s) => `${base}${s}.com`);
  }

  async buyDomains(_planId: string, domains: string[]): Promise<Record<string, string>> {
    return Object.fromEntries(domains.map((d) => [d, `dom_${d.replace(/[^a-z0-9]/g, "")}`]));
  }

  async createInboxes(
    domainIds: Record<string, string>,
    sendersPerDomain: number,
    senderName: string
  ): Promise<InboxRecord[]> {
    const first = senderName.split(" ")[0]?.toLowerCase() || "team";
    const last = senderName.split(" ")[1]?.toLowerCase() || "";
    const locals = [first, last ? `${first}.${last}` : `${first}1`, last ? `${first[0]}${last}` : `${first}2`];
    return Object.keys(domainIds).flatMap((domain) =>
      locals.slice(0, sendersPerDomain).map((local, i) => ({
        address: `${local}@${domain}`,
        domain,
        providerUserId: `mockuser_${domain.replace(/[^a-z0-9]/g, "")}_${i}`,
      }))
    );
  }
}

/**
 * Winnr adapter ("Elite Email Infra"). Winnr both hosts the inboxes and is the
 * send/receive transport, so this provider handles domains + inboxes and
 * WinnrSendingToolService handles warming/send/inbox. One Winnr account holds
 * every client's domains; per-client separation lives in our DB.
 * Requires WINNR_API_KEY.
 */
export class WinnrDomainInboxProvider implements DomainInboxProvider {
  private base = "https://api.winnr.app/v1";
  constructor(private apiKey: string) {}

  private async call(path: string, method: string, body?: unknown) {
    const res = await fetch(`${this.base}${path}`, {
      method,
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        "Content-Type": "application/json",
      },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (!res.ok) {
      throw new Error(`Winnr ${method} ${path} → ${res.status}: ${await res.text()}`);
    }
    return res.json();
  }

  async buyPlan(): Promise<PurchaseResult> {
    return { planId: "winnr" }; // Winnr bills per-domain; no separate plan object
  }

  async suggestDomains(companyName: string, count: number): Promise<string[]> {
    // Build lookalike candidates from the client's brand, then bulk-check
    // availability. (Winnr's /domains/suggest route isn't live; search-bulk is.)
    const base = companyName
      .toLowerCase()
      .replace(/\b(llc|inc|co|corp|capital|partners|holdings|group)\b/g, "")
      .replace(/[^a-z0-9]+/g, "")
      .slice(0, 16);
    const affixes = [
      `${base}hq`, `${base}team`, `${base}group`, `${base}co`, `${base}partners`,
      `get${base}`, `join${base}`, `try${base}`, `${base}mail`, `${base}hub`,
      `${base}grp`, `${base}io`, `${base}now`, `with${base}`, `${base}app`,
    ];
    const candidates = affixes.map((a) => `${a}.com`);
    const res = await this.call("/domains/search-bulk", "POST", {
      domains: candidates,
    });
    const available: string[] = (res.data?.results ?? [])
      .filter((d: { available?: boolean }) => d.available)
      .map((d: { domain: string }) => d.domain);
    return available.slice(0, count);
  }

  async buyDomains(_planId: string, domains: string[]): Promise<Record<string, string>> {
    // Async purchase (recommended for >2-3 domains): returns a job to poll.
    const res = await this.call("/domains/purchase", "POST", {
      async: true,
      domains: domains.map((domain) => ({ domain, register: true })),
    });
    if (res.job_id) await this.pollJob(res.job_id);

    // Resolve domain names → provider domain ids.
    const list = await this.call("/domains?limit=100", "GET");
    const byName: Record<string, string> = {};
    for (const d of list.data ?? []) {
      if (domains.includes(d.domain)) byName[d.domain] = d.id;
    }
    return byName;
  }

  private async pollJob(jobId: string, tries = 40) {
    for (let i = 0; i < tries; i++) {
      const job = await this.call(`/jobs/${jobId}`, "GET");
      if (job.status === "completed") return job.result;
      if (job.status === "failed") {
        throw new Error(`Winnr job ${jobId} failed: ${JSON.stringify(job.error)}`);
      }
      await new Promise((r) => setTimeout(r, 3000));
    }
    throw new Error(`Winnr job ${jobId} timed out`);
  }

  async createInboxes(
    domainIds: Record<string, string>,
    sendersPerDomain: number,
    senderName: string
  ): Promise<InboxRecord[]> {
    const first = senderName.split(" ")[0]?.toLowerCase().replace(/[^a-z]/g, "") || "team";
    const last = senderName.split(" ")[1]?.toLowerCase().replace(/[^a-z]/g, "") || "";
    const locals = [first, last ? `${first}.${last}` : `${first}.team`, last ? `${first[0]}.${last}` : `${first}.hq`];

    const inboxes: InboxRecord[] = [];
    for (const [domain, domainId] of Object.entries(domainIds)) {
      for (const local of locals.slice(0, sendersPerDomain)) {
        const res = await this.call("/email-users", "POST", {
          username: local,
          domain: domainId,
          name: senderName,
        });
        const user = res.data ?? res;
        inboxes.push({
          address: user.full_address ?? `${local}@${domain}`,
          domain,
          providerUserId: user.id,
        });
      }
    }
    return inboxes;
  }
}
