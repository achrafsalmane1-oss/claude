import { sql as raw } from 'drizzle-orm';
import { db, apiUsage } from '@/db';
import type { AuthenticatedKey } from './auth';

/**
 * Per-key rate limiting (spec §8).
 *
 * A fixed window in Postgres rather than an in-memory counter: the moment there
 * are two web instances an in-memory limiter is simply wrong, and the same
 * table doubles as the usage counter the spec asks for from day one.
 *
 * One upsert per request is the entire limiter. `window_start` is truncated to
 * the window, so the primary key *is* the bucket.
 */

export interface RateLimitResult {
  allowed: boolean;
  limit: number;
  remaining: number;
  /** Seconds until the current window resets. */
  resetSeconds: number;
  window: 'minute' | 'day';
}

function windowStart(window: 'minute' | 'day', now: Date): Date {
  const d = new Date(now);
  d.setUTCSeconds(0, 0);
  if (window === 'day') d.setUTCHours(0, 0, 0, 0);
  return d;
}

function windowSeconds(window: 'minute' | 'day'): number {
  return window === 'minute' ? 60 : 86_400;
}

async function bump(keyId: number, window: 'minute' | 'day', now: Date): Promise<number> {
  const start = windowStart(window, now);

  const rows = await db
    .insert(apiUsage)
    .values({ apiKeyId: keyId, window, windowStart: start, requestCount: 1 })
    .onConflictDoUpdate({
      target: [apiUsage.apiKeyId, apiUsage.window, apiUsage.windowStart],
      set: { requestCount: raw`${apiUsage.requestCount} + 1` },
    })
    .returning({ count: apiUsage.requestCount });

  return rows[0]?.count ?? 1;
}

/**
 * Check and consume one request against both windows.
 *
 * Both counters are incremented even when the minute window is already over
 * limit, so a client hammering a limit still shows up in daily usage — which is
 * the number you want when deciding whether someone is abusing a key.
 */
export async function checkRateLimit(key: AuthenticatedKey, now = new Date()): Promise<RateLimitResult> {
  const [minuteCount, dayCount] = await Promise.all([
    bump(key.id, 'minute', now),
    bump(key.id, 'day', now),
  ]);

  const elapsedInMinute = now.getUTCSeconds();
  const elapsedInDay = now.getUTCHours() * 3600 + now.getUTCMinutes() * 60 + now.getUTCSeconds();

  if (dayCount > key.rateLimitPerDay) {
    return {
      allowed: false,
      limit: key.rateLimitPerDay,
      remaining: 0,
      resetSeconds: windowSeconds('day') - elapsedInDay,
      window: 'day',
    };
  }

  if (minuteCount > key.rateLimitPerMinute) {
    return {
      allowed: false,
      limit: key.rateLimitPerMinute,
      remaining: 0,
      resetSeconds: windowSeconds('minute') - elapsedInMinute,
      window: 'minute',
    };
  }

  return {
    allowed: true,
    limit: key.rateLimitPerMinute,
    remaining: Math.max(0, key.rateLimitPerMinute - minuteCount),
    resetSeconds: windowSeconds('minute') - elapsedInMinute,
    window: 'minute',
  };
}

/** Standard rate-limit headers, so a client can back off intelligently. */
export function rateLimitHeaders(result: RateLimitResult): Record<string, string> {
  return {
    'X-RateLimit-Limit': String(result.limit),
    'X-RateLimit-Remaining': String(result.remaining),
    'X-RateLimit-Reset': String(result.resetSeconds),
    ...(result.allowed ? {} : { 'Retry-After': String(result.resetSeconds) }),
  };
}

/** Drop usage rows older than 30 days. Called by the worker's maintenance job. */
export async function pruneUsage(): Promise<number> {
  const result = await db.execute<{ count: number }>(raw`
    with deleted as (
      delete from api_usage where window_start < now() - interval '30 days' returning 1
    )
    select count(*)::int as count from deleted
  `);
  return [...result][0]?.count ?? 0;
}
