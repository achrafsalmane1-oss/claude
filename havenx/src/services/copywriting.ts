import Anthropic from "@anthropic-ai/sdk";
import type { Mandate } from "@/generated/prisma/client";

export interface CopyVariant {
  subject: string;
  /** Body with {{firstName}}, {{companyName}}, {{niche}} placeholders. */
  body: string;
}

export interface CampaignCopy {
  variants: CopyVariant[];
}

export interface CopywritingService {
  /** Generate the client's two-variant campaign copy from their mandate. */
  generateCampaignCopy(mandate: Mandate): Promise<CampaignCopy>;

  /**
   * Produce the niche variant for one lead: 2-3 words, lowercase, reads
   * naturally in "...looking to buy companies in {{niche}}".
   */
  nicheVariant(industry: string, companyDescription: string): Promise<string>;
}

/** House style both implementations follow. */
function templateVariants(mandate: Mandate): CampaignCopy {
  const sig = mandate.senderSignature || `${mandate.senderName}\n${mandate.senderCompany}`;
  return {
    variants: [
      {
        subject: "quick question about {{companyName}}",
        body:
          `Hey {{firstName}},\n\n` +
          `Love what you're doing with {{companyName}}. We're actively looking to buy companies in {{niche}}, and yours stood out.\n\n` +
          `Would you be open to a short conversation about what a sale could look like — even if it's just exploratory?\n\n` +
          `${sig}`,
      },
      {
        subject: "{{companyName}} — worth a conversation?",
        body:
          `Hi {{firstName}},\n\n` +
          `I'll keep this short: we invest in {{niche}} businesses like {{companyName}}, and I wanted to ask whether selling is something you'd ever consider.\n\n` +
          `If not, no problem at all — happy to give you a quick, no-strings estimate of what your company is worth, so you have a number in your back pocket.\n\n` +
          `${sig}`,
      },
    ],
  };
}

/** Mock: template copy + derived niche, no API calls. */
export class TemplateCopywritingService implements CopywritingService {
  async generateCampaignCopy(mandate: Mandate): Promise<CampaignCopy> {
    return templateVariants(mandate);
  }

  async nicheVariant(industry: string): Promise<string> {
    return industry.toLowerCase().replace(/[^a-z\s]/g, "").trim().split(/\s+/).slice(0, 3).join(" ");
  }
}

/**
 * Claude-powered copywriting. Personalizes the two house-style variants to
 * the client's mandate and generates a per-lead niche variant.
 * Requires ANTHROPIC_API_KEY.
 */
export class AnthropicCopywritingService implements CopywritingService {
  private client: Anthropic;
  private model = process.env.COPY_MODEL ?? "claude-opus-4-8";

  constructor(apiKey: string) {
    this.client = new Anthropic({ apiKey });
  }

  async generateCampaignCopy(mandate: Mandate): Promise<CampaignCopy> {
    const base = templateVariants(mandate);
    try {
      return await this.generate(mandate, base);
    } catch (e) {
      // Never let an API error (billing, rate limit, outage) block activation.
      console.error("[copywriter] falling back to template:", e);
      return base;
    }
  }

  private async generate(mandate: Mandate, base: CampaignCopy): Promise<CampaignCopy> {
    const response = await this.client.messages.create({
      model: this.model,
      max_tokens: 2000,
      output_config: {
        format: {
          type: "json_schema",
          schema: {
            type: "object",
            properties: {
              variants: {
                type: "array",
                items: {
                  type: "object",
                  properties: {
                    subject: { type: "string" },
                    body: { type: "string" },
                  },
                  required: ["subject", "body"],
                  additionalProperties: false,
                },
              },
            },
            required: ["variants"],
            additionalProperties: false,
          },
        },
      },
      messages: [
        {
          role: "user",
          content: `You write cold outreach for an acquisition buyer contacting small-business owners. Rewrite the two email variants below so they fit this buyer's mandate, keeping them under 90 words each, plain-spoken, respectful, zero hype, and keeping the {{firstName}}, {{companyName}}, and {{niche}} placeholders exactly as written. Variant 1 opens a conversation about selling; variant 2 offers a free valuation estimate as the soft ask. Sign with the same signature.

Buyer mandate:
- Buyer: ${mandate.senderName}, ${mandate.senderCompany}
- Thesis: ${mandate.thesis ?? "buying strong founder-led businesses"}
- Industries: ${mandate.industries.join(", ")}
- Ideal owner situations: ${mandate.ownerSituations.join(", ") || "any"}

Base variants:
${JSON.stringify(base.variants, null, 2)}`,
        },
      ],
    });
    if (response.stop_reason === "refusal") return base;
    const text = response.content.find((b) => b.type === "text")?.text;
    if (!text) return base;
    try {
      const parsed = JSON.parse(text) as CampaignCopy;
      return parsed.variants?.length ? parsed : base;
    } catch {
      return base;
    }
  }

  async nicheVariant(industry: string, companyDescription: string): Promise<string> {
    const fallback = industry.toLowerCase().replace(/[^a-z\s]/g, "").trim().split(/\s+/).slice(0, 3).join(" ");
    try {
      const response = await this.client.messages.create({
        model: this.model,
        max_tokens: 20,
        messages: [
          {
            role: "user",
            content: `Company industry: "${industry}". Description: "${companyDescription}".

Reply with ONLY a 2-3 word, all-lowercase niche phrase that completes this sentence naturally: "We're actively looking to buy companies in ___". No punctuation, no quotes. Example outputs: "commercial hvac", "dental practices", "route-based landscaping".`,
          },
        ],
      });
      const text = response.content.find((b) => b.type === "text")?.text?.trim().toLowerCase();
      if (!text) return fallback;
      return text.replace(/[^a-z\s-]/g, "").trim().split(/\s+/).slice(0, 3).join(" ") || fallback;
    } catch (e) {
      console.error("[copywriter] niche fallback:", e);
      return fallback;
    }
  }
}
