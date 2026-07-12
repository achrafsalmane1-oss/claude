import Anthropic from "@anthropic-ai/sdk";
import type { ReplyClass, ReplyClassificationService } from "./types";

/**
 * Mock reply classifier. The real implementation calls an LLM with the reply
 * text and the mandate for context. This one uses keyword heuristics that are
 * good enough for seeded demo data.
 */
export class MockReplyClassificationService
  implements ReplyClassificationService
{
  async classify(replyText: string): Promise<ReplyClass> {
    const t = replyText.toLowerCase();
    if (
      /(not interested|no thanks|remove me|stop|unsubscribe|not for sale)/.test(t)
    ) {
      return "NOT_INTERESTED";
    }
    if (/(next year|not right now|maybe later|check back|too early)/.test(t)) {
      return "NOT_NOW";
    }
    return "INTERESTED";
  }
}

/**
 * Claude-powered reply classification for production, where owner replies
 * are free-form and keyword heuristics misfire. Requires ANTHROPIC_API_KEY.
 */
export class AnthropicReplyClassificationService
  implements ReplyClassificationService
{
  private client: Anthropic;
  private model = process.env.COPY_MODEL ?? "claude-opus-4-8";

  constructor(apiKey: string) {
    this.client = new Anthropic({ apiKey });
  }

  // Keyword fallback for when the API is unavailable (billing/rate limit/outage).
  private fallback = new MockReplyClassificationService();

  async classify(replyText: string): Promise<ReplyClass> {
    try {
      const response = await this.client.messages.create({
        model: this.model,
        max_tokens: 10,
        messages: [
          {
            role: "user",
            content: `A business owner replied to acquisition outreach (an investor asked whether they'd consider selling their company). Classify the reply.

Reply: """${replyText.slice(0, 2000)}"""

Answer with exactly one word:
- INTERESTED — open to a conversation about selling, asks questions, wants a call/valuation
- NOT_NOW — not ruling it out, but says later / bad timing
- NOT_INTERESTED — declines, opt-out, hostile, or auto-reply`,
          },
        ],
      });
      const text = response.content
        .find((b) => b.type === "text")
        ?.text?.trim()
        .toUpperCase();
      if (text?.includes("NOT_INTERESTED")) return "NOT_INTERESTED";
      if (text?.includes("NOT_NOW")) return "NOT_NOW";
      if (text?.includes("INTERESTED")) return "INTERESTED";
      return this.fallback.classify(replyText);
    } catch (e) {
      console.error("[classifier] falling back to keywords:", e);
      return this.fallback.classify(replyText);
    }
  }
}
