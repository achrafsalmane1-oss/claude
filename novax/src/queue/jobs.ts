/**
 * Job names and payload types.
 *
 * One place to look for "what work exists in this system". Payloads are small
 * on purpose — a job carries identifiers, never enrichment data.
 */

export const QUEUES = {
  /** Download and ingest one day of the NRD feed. */
  NRD_INGEST: 'nrd.ingest',
  /** Resolve DNS for a batch of apexes. Batched so the queue stays small. */
  DNS_RESOLVE: 'dns.resolve.batch',
  /**
   * HTTP probe a batch of apexes.
   *
   * Batched for the same reason DNS is: measured against a real feed day, the
   * DNS gate kills ~43%, not the ~90% originally assumed, so one job per domain
   * here would mean ~170k jobs/day. Failures are isolated per item inside the
   * handler so a batch never retries its successes.
   */
  HTTP_PROBE: 'http.probe.batch',
  /** RDAP lookup for a batch of apexes (rate-limited per registry within). */
  RDAP_LOOKUP: 'rdap.lookup.batch',
  /** Run the rules layer, then queue survivors for the classifier. */
  SCORE_RULES: 'score.rules',
  /** Submit + collect one Anthropic batch of classifier calls. */
  SCORE_CLASSIFY: 'score.classify',
  /** Deliver new matches to one webhook. */
  WEBHOOK_DELIVER: 'webhook.deliver',
  /** Send one saved search's daily digest. */
  DIGEST_SEND: 'digest.send',
  /** Re-check a pending opt-out's DNS TXT proof. */
  OPTOUT_VERIFY: 'optout.verify',
} as const;

export type QueueName = (typeof QUEUES)[keyof typeof QUEUES];

export interface JobPayloads {
  [QUEUES.NRD_INGEST]: { date: string };
  [QUEUES.DNS_RESOLVE]: { apexes: string[] };
  [QUEUES.HTTP_PROBE]: { apexes: string[] };
  [QUEUES.RDAP_LOOKUP]: { apexes: string[] };
  [QUEUES.SCORE_RULES]: { apexes: string[] };
  [QUEUES.SCORE_CLASSIFY]: { apexes: string[]; batchId?: string };
  [QUEUES.WEBHOOK_DELIVER]: { webhookId: number };
  [QUEUES.DIGEST_SEND]: { savedSearchId: number };
  [QUEUES.OPTOUT_VERIFY]: { optOutId: number };
}

/** Retry policy per queue. Network-bound work gets more attempts. */
export const QUEUE_POLICIES: Record<QueueName, { retryLimit: number; retryDelay: number; expireInSeconds: number }> = {
  [QUEUES.NRD_INGEST]: { retryLimit: 3, retryDelay: 300, expireInSeconds: 3600 },
  [QUEUES.DNS_RESOLVE]: { retryLimit: 3, retryDelay: 60, expireInSeconds: 900 },
  [QUEUES.HTTP_PROBE]: { retryLimit: 2, retryDelay: 120, expireInSeconds: 1800 },
  [QUEUES.RDAP_LOOKUP]: { retryLimit: 3, retryDelay: 300, expireInSeconds: 1800 },
  [QUEUES.SCORE_RULES]: { retryLimit: 2, retryDelay: 60, expireInSeconds: 900 },
  // The Anthropic batch can take up to 24h; the job polls it.
  [QUEUES.SCORE_CLASSIFY]: { retryLimit: 2, retryDelay: 600, expireInSeconds: 90_000 },
  [QUEUES.WEBHOOK_DELIVER]: { retryLimit: 5, retryDelay: 60, expireInSeconds: 300 },
  [QUEUES.DIGEST_SEND]: { retryLimit: 3, retryDelay: 300, expireInSeconds: 600 },
  [QUEUES.OPTOUT_VERIFY]: { retryLimit: 10, retryDelay: 900, expireInSeconds: 300 },
};
