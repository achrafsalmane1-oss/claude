import { db } from "@/lib/db";

export interface OutboundEmail {
  fromUserId: string; // provider mailbox id to send from
  to: string;
  subject: string;
  body: string;
}

export interface InboundEmail {
  messageId: string;
  fromEmail: string; // the owner who replied
  toMailbox: string; // our sending inbox that received it
  text: string;
  isWarmup: boolean;
}

export interface SendingToolService {
  /** Turn on native warmup for the given provider mailbox ids. */
  setupWarming(providerUserIds: string[]): Promise<void>;

  /** Send one email. Returns the provider message id, or null on failure. */
  sendEmail(email: OutboundEmail): Promise<string | null>;

  /** Pull new inbound messages account-wide, for reply detection. */
  fetchInbound(cursor?: string | null): Promise<{
    inbound: InboundEmail[];
    nextCursor?: string | null;
  }>;
}

const MOCK_REPLIES: { text: string; weight: number }[] = [
  { text: "Not interested, please remove me from your list.", weight: 5 },
  { text: "We're not for sale, thanks anyway.", weight: 4 },
  { text: "Not right now — check back next year.", weight: 2 },
  { text: "Interesting timing. I'm 62 and thinking about what's next. What would this look like? Happy to take a call.", weight: 1 },
  { text: "Maybe. What kind of numbers are you seeing for businesses like mine? I'd want to keep my crew on.", weight: 1 },
];

/**
 * Mock sender. sendEmail is a no-op success; fetchInbound synthesizes a small
 * trickle of replies from already-contacted prospects so the demo pipeline
 * flows end-to-end without a real provider.
 */
export class MockSendingToolService implements SendingToolService {
  async setupWarming(ids: string[]) {
    console.log(`[sender:mock] warmup enabled on ${ids.length} inboxes`);
  }

  async sendEmail(email: OutboundEmail): Promise<string | null> {
    return `mockmsg_${email.to}_${Date.now().toString(36)}`;
  }

  async fetchInbound(): Promise<{ inbound: InboundEmail[]; nextCursor?: string | null }> {
    const contacted = await db.prospect.findMany({
      where: {
        stage: "CONTACTED",
        contactEmail: { not: null },
        contactedAt: { lt: new Date(Date.now() - 3_600_000) },
      },
      take: 40,
      orderBy: { contactedAt: "asc" },
    });
    const count = Math.min(3, Math.ceil(contacted.length * 0.05));
    const total = MOCK_REPLIES.reduce((a, r) => a + r.weight, 0);
    const inbound = contacted.slice(0, count).map((p) => {
      let roll = Math.random() * total;
      const reply = MOCK_REPLIES.find((r) => (roll -= r.weight) <= 0) ?? MOCK_REPLIES[0];
      return {
        messageId: `mockin_${p.id}_${Date.now().toString(36)}`,
        fromEmail: p.contactEmail!,
        toMailbox: "inbox@havenx",
        text: reply.text,
        isWarmup: false,
      };
    });
    return { inbound };
  }
}

/**
 * Winnr sender. Winnr hosts the inboxes, so it is also the transport:
 * native warmup, per-message send, and account-wide inbox polling.
 * Requires WINNR_API_KEY.
 */
export class WinnrSendingToolService implements SendingToolService {
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

  async setupWarming(userIds: string[]) {
    if (userIds.length === 0) return;
    await this.call("/warming/enable", "POST", {
      user_ids: userIds,
      settings: { emails_per_day: 25, rampup_enabled: true, rampup_speed: "normal" },
    });
  }

  async sendEmail(email: OutboundEmail): Promise<string | null> {
    try {
      const res = await this.call(
        `/email-users/${email.fromUserId}/inbox/send`,
        "POST",
        { to: email.to, subject: email.subject, body: email.body, html: false }
      );
      return res.data?.message_id ?? res.message_id ?? `sent_${Date.now()}`;
    } catch (e) {
      console.error("[sender:winnr] send failed:", e);
      return null;
    }
  }

  async fetchInbound(
    cursor?: string | null
  ): Promise<{ inbound: InboundEmail[]; nextCursor?: string | null }> {
    const q = new URLSearchParams({ limit: "100", exclude_warmup: "true" });
    if (cursor) q.set("cursor", cursor);
    const res = await this.call(`/inbox?${q.toString()}`, "GET");
    const inbound: InboundEmail[] = (res.data ?? [])
      .filter((m: { folder?: string; is_warmup?: boolean }) => !m.is_warmup)
      .map((m: {
        message_id?: string;
        id?: string;
        from?: string;
        from_email?: string;
        to?: string;
        text?: string;
        snippet?: string;
        body_preview?: string;
      }) => ({
        messageId: m.message_id ?? m.id ?? "",
        fromEmail: extractEmail(m.from_email ?? m.from ?? ""),
        toMailbox: m.to ?? "",
        text: m.text ?? m.snippet ?? m.body_preview ?? "",
        isWarmup: false,
      }))
      .filter((m: InboundEmail) => m.messageId && m.fromEmail);
    return { inbound, nextCursor: res.pagination?.next_cursor ?? null };
  }
}

function extractEmail(raw: string): string {
  const m = raw.match(/<([^>]+)>/);
  return (m ? m[1] : raw).trim().toLowerCase();
}
