import { db } from "@/lib/db";
import type { InboxRecord } from "./inboxProvider";
import type { CampaignCopy } from "./copywriting";

export interface CampaignLead {
  prospectId: string;
  email: string;
  firstName: string;
  companyName: string;
  niche: string; // 2-3 word lowercase niche variant
}

export interface SendingToolService {
  /** Connect SMTP inboxes as sending accounts, with warmup enabled. */
  connectInboxes(inboxes: InboxRecord[]): Promise<string[]>;

  /**
   * Create the client's campaign: two copy variants, Mon-Fri schedule,
   * dailyLimit across the connected accounts. Returns the campaign id.
   */
  createCampaign(input: {
    name: string;
    accountIds: string[];
    copy: CampaignCopy;
    dailyLimit: number;
  }): Promise<string>;

  /** Push leads with personalization variables. Returns per-lead ids. */
  addLeads(campaignId: string, leads: CampaignLead[]): Promise<string[]>;

  /** Remaining un-contacted leads in the campaign (to keep it topped up). */
  getQueueDepth(campaignId: string): Promise<number>;
}

/**
 * Mock sending tool. "Sending" is simulated: pushed leads are marked
 * CONTACTED, and syncMockReplies() periodically turns a small share of
 * contacted prospects into replies so the demo pipeline keeps moving.
 */
export class MockSendingToolService implements SendingToolService {
  async connectInboxes(inboxes: InboxRecord[]): Promise<string[]> {
    console.log(`[sender:mock] connected ${inboxes.length} inboxes, warmup enabled`);
    return inboxes.map((i) => `acct_${i.address.replace(/[^a-z0-9]/g, "")}`);
  }

  async createCampaign(input: {
    name: string;
    accountIds: string[];
    copy: CampaignCopy;
    dailyLimit: number;
  }): Promise<string> {
    console.log(
      `[sender:mock] campaign "${input.name}" created — ${input.accountIds.length} accounts, ${input.dailyLimit}/day Mon-Fri, ${input.copy.variants.length} variants`
    );
    return `camp_mock_${Date.now().toString(36)}`;
  }

  async addLeads(campaignId: string, leads: CampaignLead[]): Promise<string[]> {
    const now = new Date();
    await db.prospect.updateMany({
      where: { id: { in: leads.map((l) => l.prospectId) } },
      data: {
        stage: "CONTACTED",
        contactedAt: now,
        pushedAt: now,
      },
    });
    return leads.map((l) => `lead_${l.prospectId.slice(-8)}`);
  }

  async getQueueDepth(): Promise<number> {
    return 0; // mock always wants a top-up
  }
}

const MOCK_REPLIES: { text: string; weight: number }[] = [
  { text: "Not interested, please remove me from your list.", weight: 5 },
  { text: "We're not for sale, thanks anyway.", weight: 4 },
  { text: "Not right now — check back next year.", weight: 2 },
  { text: "Interesting timing. I'm 62 and thinking about what's next. What would this look like? Happy to take a call.", weight: 1 },
  { text: "Maybe. What kind of numbers are you seeing for businesses like mine? I'd want to keep my crew on.", weight: 1 },
];

/** Dev-only: simulate a trickle of inbound replies for a user's contacted pool. */
export async function pickMockReplies(userId: string, max = 3) {
  const contacted = await db.prospect.findMany({
    where: { userId, stage: "CONTACTED", contactedAt: { lt: new Date(Date.now() - 3_600_000) } },
    take: 50,
    orderBy: { contactedAt: "asc" },
  });
  const count = Math.min(max, Math.floor(contacted.length * 0.05));
  const total = MOCK_REPLIES.reduce((a, r) => a + r.weight, 0);
  return contacted.slice(0, count).map((p) => {
    let roll = Math.random() * total;
    const reply =
      MOCK_REPLIES.find((r) => (roll -= r.weight) <= 0) ?? MOCK_REPLIES[0];
    return { prospect: p, replyText: reply.text };
  });
}

/**
 * Instantly API v2 adapter. Written against the public v2 docs
 * (https://developer.instantly.ai) — UNTESTED until a key is provided; verify
 * field names on first live run. Requires INSTANTLY_API_KEY.
 */
export class InstantlySendingToolService implements SendingToolService {
  private base = "https://api.instantly.ai/api/v2";
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
      throw new Error(`Instantly ${method} ${path} → ${res.status}: ${await res.text()}`);
    }
    return res.json();
  }

  async connectInboxes(inboxes: InboxRecord[]): Promise<string[]> {
    const ids: string[] = [];
    for (const inbox of inboxes) {
      const account = await this.call("/accounts", "POST", {
        email: inbox.address,
        smtp_host: inbox.smtpHost,
        smtp_port: inbox.smtpPort,
        smtp_username: inbox.smtpUsername,
        smtp_password: inbox.smtpPasswordRef, // replace with secret lookup
        imap_host: inbox.imapHost,
        imap_port: inbox.imapPort,
        warmup: { enabled: true },
      });
      ids.push(account.id ?? inbox.address);
    }
    return ids;
  }

  async createCampaign(input: {
    name: string;
    accountIds: string[];
    copy: CampaignCopy;
    dailyLimit: number;
  }): Promise<string> {
    const campaign = await this.call("/campaigns", "POST", {
      name: input.name,
      email_list: input.accountIds,
      daily_limit: input.dailyLimit,
      // Mon-Fri sending window
      campaign_schedule: {
        schedules: [
          {
            name: "weekdays",
            timing: { from: "08:00", to: "17:00" },
            days: { 1: true, 2: true, 3: true, 4: true, 5: true },
            timezone: "America/Chicago",
          },
        ],
      },
      sequences: [
        {
          steps: [
            {
              type: "email",
              variants: input.copy.variants.map((v) => ({
                subject: v.subject,
                body: v.body,
              })),
            },
          ],
        },
      ],
    });
    return campaign.id;
  }

  async addLeads(campaignId: string, leads: CampaignLead[]): Promise<string[]> {
    const ids: string[] = [];
    for (const lead of leads) {
      const created = await this.call("/leads", "POST", {
        campaign: campaignId,
        email: lead.email,
        first_name: lead.firstName,
        company_name: lead.companyName,
        custom_variables: { niche: lead.niche },
      });
      ids.push(created.id ?? lead.email);
    }
    return ids;
  }

  async getQueueDepth(campaignId: string): Promise<number> {
    const res = await this.call(
      `/campaigns/${campaignId}/analytics`,
      "GET"
    ).catch(() => null);
    if (!res) return 0;
    return Math.max(0, (res.leads_count ?? 0) - (res.contacted_count ?? 0));
  }
}
