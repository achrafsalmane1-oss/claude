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
