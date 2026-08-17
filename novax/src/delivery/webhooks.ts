import { createHmac, randomBytes, timingSafeEqual } from 'node:crypto';
import { eq, and, gt, sql as raw } from 'drizzle-orm';
import { db, webhooks, deliveries, domainScores } from '@/db';
import { env } from '@/config/env';
import { fetchWithLimits } from '@/lib/http';
import { createLogger } from '@/lib/logger';
import { parseFilters } from '@/api/filters';
import { queryDomains } from '@/api/serialize';

/**
 * Webhook delivery (spec §8).
 *
 * Two properties that are not optional:
 *
 *  - **Signed.** An unsigned webhook cannot be verified by the receiver, which
 *    means anyone who learns the URL can post fake leads into their CRM. Every
 *    request carries an HMAC-SHA256 over `timestamp.body`, which also makes it
 *    replay-resistant.
 *  - **Queued.** Delivery happens in the worker, never in an API request, so a
 *    slow receiver cannot hold our request thread open.
 *
 * A watermark (`last_delivered_score_id`) rather than a timestamp decides what
 * is new, because two domains scored in the same millisecond must not be able
 * to straddle a delivery boundary.
 */

const log = createLogger('delivery.webhooks');

export function generateSecret(): string {
  return `whsec_${randomBytes(24).toString('base64url')}`;
}

/** `sha256=<hex>` over `<timestamp>.<body>`. */
export function signPayload(secret: string, body: string, timestamp: number): string {
  const hmac = createHmac('sha256', secret);
  hmac.update(`${timestamp}.${body}`, 'utf8');
  return `sha256=${hmac.digest('hex')}`;
}

/**
 * Verify a signature. Exported so the docs can point receivers at a reference
 * implementation, and so it can be tested.
 */
export function verifySignature(
  secret: string,
  body: string,
  timestamp: number,
  signature: string,
  toleranceSeconds = 300,
): boolean {
  const age = Math.abs(Date.now() / 1000 - timestamp);
  if (age > toleranceSeconds) return false;

  const expected = signPayload(secret, body, timestamp);
  const a = Buffer.from(expected, 'utf8');
  const b = Buffer.from(signature, 'utf8');
  return a.length === b.length && timingSafeEqual(a, b);
}

export interface DeliveryOutcome {
  webhookId: number;
  delivered: number;
  status: 'delivered' | 'failed' | 'skipped';
  statusCode?: number;
  error?: string;
}

/**
 * Deliver everything new for one webhook.
 *
 * The watermark is only advanced on a successful delivery, so a failure retries
 * the same batch rather than skipping it.
 */
export async function deliverWebhook(webhookId: number): Promise<DeliveryOutcome> {
  const rows = await db.select().from(webhooks).where(eq(webhooks.id, webhookId)).limit(1);
  const hook = rows[0];

  if (!hook) return { webhookId, delivered: 0, status: 'skipped', error: 'webhook not found' };
  if (!hook.active) return { webhookId, delivered: 0, status: 'skipped', error: 'webhook inactive' };

  // Find matching domains scored since the watermark. `queryDomains` applies
  // the suppression gate, so an opted-out domain can never be pushed.
  const filters = parseFilters((hook.filters ?? {}) as Record<string, unknown>);
  const matches = await queryDomains({ ...filters, limit: Math.min(filters.limit, 200) });

  const newScoreIds = await db
    .select({ id: domainScores.id, apex: domainScores.apex })
    .from(domainScores)
    .where(and(eq(domainScores.isCurrent, true), gt(domainScores.id, hook.lastDeliveredScoreId)));

  const newApexes = new Set(newScoreIds.map((r) => r.apex));
  const payloadDomains = matches.domains.filter((d) => newApexes.has(d.domain));

  if (payloadDomains.length === 0) {
    return { webhookId, delivered: 0, status: 'skipped' };
  }

  const highWater = Math.max(hook.lastDeliveredScoreId, ...newScoreIds.map((r) => r.id));

  const body = JSON.stringify({
    event: 'domains.matched',
    webhook_id: hook.id,
    delivered_at: new Date().toISOString(),
    count: payloadDomains.length,
    data: payloadDomains,
  });
  const timestamp = Math.floor(Date.now() / 1000);

  const attempt = hook.consecutiveFailures + 1;

  const [delivery] = await db
    .insert(deliveries)
    .values({
      kind: 'webhook',
      webhookId: hook.id,
      target: hook.url,
      domainCount: payloadDomains.length,
      attempt,
      status: 'pending',
      payloadSummary: { domains: payloadDomains.map((d) => d.domain).slice(0, 50) },
    })
    .returning({ id: deliveries.id });

  try {
    const response = await fetchWithLimits(hook.url, {
      method: 'POST',
      headers: {
        'content-type': 'application/json',
        'x-novax-signature': signPayload(hook.secret, body, timestamp),
        'x-novax-timestamp': String(timestamp),
        'x-novax-webhook-id': String(hook.id),
      },
      body,
      timeoutMs: env.WEBHOOK_TIMEOUT_MS,
      // Cap what we read back: we only care about the status code.
      maxBytes: 8 * 1024,
    });

    const ok = response.statusCode >= 200 && response.statusCode < 300;

    await db
      .update(deliveries)
      .set({
        status: ok ? 'delivered' : 'failed',
        statusCode: response.statusCode,
        deliveredAt: ok ? new Date() : null,
        error: ok ? null : `receiver returned HTTP ${response.statusCode}`,
      })
      .where(eq(deliveries.id, delivery!.id));

    if (ok) {
      await db
        .update(webhooks)
        .set({ lastDeliveredScoreId: highWater, consecutiveFailures: 0 })
        .where(eq(webhooks.id, hook.id));

      log.info('webhook delivered', { webhook_id: hook.id, domains: payloadDomains.length });
      return {
        webhookId,
        delivered: payloadDomains.length,
        status: 'delivered',
        statusCode: response.statusCode,
      };
    }

    await recordFailure(hook.id, `HTTP ${response.statusCode}`);
    return {
      webhookId,
      delivered: 0,
      status: 'failed',
      statusCode: response.statusCode,
      error: `receiver returned HTTP ${response.statusCode}`,
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    await db
      .update(deliveries)
      .set({ status: 'failed', error: message })
      .where(eq(deliveries.id, delivery!.id));
    await recordFailure(hook.id, message);
    return { webhookId, delivered: 0, status: 'failed', error: message };
  }
}

/**
 * Count a failure and disable the endpoint once it is clearly gone. Retrying a
 * dead URL forever is how you end up on someone's blocklist.
 */
async function recordFailure(webhookId: number, error: string): Promise<void> {
  const rows = await db
    .update(webhooks)
    .set({ consecutiveFailures: raw`${webhooks.consecutiveFailures} + 1` })
    .where(eq(webhooks.id, webhookId))
    .returning({ failures: webhooks.consecutiveFailures });

  const failures = rows[0]?.failures ?? 0;
  if (failures >= env.WEBHOOK_MAX_ATTEMPTS) {
    await db
      .update(webhooks)
      .set({ active: false, disabledAt: new Date() })
      .where(eq(webhooks.id, webhookId));
    log.warn('webhook disabled after repeated failures', { webhook_id: webhookId, failures, error });
  }
}

/** Every active webhook, for the worker's periodic sweep. */
export async function activeWebhookIds(): Promise<number[]> {
  const rows = await db.select({ id: webhooks.id }).from(webhooks).where(eq(webhooks.active, true));
  return rows.map((r) => r.id);
}
