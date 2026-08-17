import { z } from 'zod';
import { eq, desc } from 'drizzle-orm';
import { withApiAuth } from '@/api/handler';
import { db, webhooks } from '@/db';
import { filterSchema } from '@/api/filters';
import { generateSecret } from '@/delivery/webhooks';

/**
 * Webhook registration (spec §8).
 *
 *   GET  /api/v1/webhooks  — list
 *   POST /api/v1/webhooks  — register a URL + filter set
 *
 * The signing secret is returned once, on creation, and never again — the same
 * reasoning as API keys.
 */

export const dynamic = 'force-dynamic';

const createSchema = z.object({
  url: z.string().url(),
  filters: z.record(z.string(), z.unknown()).optional(),
  saved_search_id: z.number().int().optional(),
});

export const GET = withApiAuth(async ({ key }) => {
  if (!key.userId) {
    return { body: { error: 'no_user', message: 'This API key is not attached to a user account.' }, status: 400 };
  }

  const rows = await db
    .select()
    .from(webhooks)
    .where(eq(webhooks.userId, key.userId))
    .orderBy(desc(webhooks.createdAt));

  return {
    body: {
      data: rows.map((r) => ({
        id: r.id,
        url: r.url,
        filters: r.filters,
        active: r.active,
        consecutive_failures: r.consecutiveFailures,
        disabled_at: r.disabledAt?.toISOString() ?? null,
        created_at: r.createdAt.toISOString(),
      })),
      count: rows.length,
    },
    rowsReturned: rows.length,
  };
});

export const POST = withApiAuth(async ({ key, request }) => {
  if (!key.userId) {
    return { body: { error: 'no_user', message: 'This API key is not attached to a user account.' }, status: 400 };
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return { body: { error: 'invalid_json', message: 'Request body must be JSON.' }, status: 400 };
  }

  const parsed = createSchema.safeParse(body);
  if (!parsed.success) {
    return {
      body: { error: 'invalid_request', message: 'Invalid body', detail: parsed.error.issues },
      status: 400,
    };
  }

  // Refuse to post to a non-public address. Without this, a registered webhook
  // is a server-side request forgery primitive against our own network.
  const target = new URL(parsed.data.url);
  if (target.protocol !== 'https:' && target.hostname !== 'localhost') {
    return {
      body: { error: 'insecure_url', message: 'Webhook URLs must use https.' },
      status: 400,
    };
  }
  if (isPrivateHost(target.hostname)) {
    return {
      body: { error: 'invalid_url', message: 'Webhook URLs must point at a public host.' },
      status: 400,
    };
  }

  if (parsed.data.filters) {
    const check = filterSchema.safeParse(parsed.data.filters);
    if (!check.success) {
      return {
        body: { error: 'invalid_filters', message: 'Invalid filters', detail: check.error.issues },
        status: 400,
      };
    }
  }

  const secret = generateSecret();

  const rows = await db
    .insert(webhooks)
    .values({
      userId: key.userId,
      url: parsed.data.url,
      secret,
      filters: parsed.data.filters ?? {},
      savedSearchId: parsed.data.saved_search_id ?? null,
    })
    .returning({ id: webhooks.id });

  return {
    status: 201,
    rowsReturned: 1,
    body: {
      data: {
        id: rows[0]!.id,
        url: parsed.data.url,
        // Shown exactly once.
        secret,
        verification:
          'Each delivery carries X-Novax-Signature: sha256=<hmac> and X-Novax-Timestamp. ' +
          'Recompute HMAC-SHA256 over "<timestamp>.<raw body>" with this secret and compare.',
      },
    },
  };
});

/** Block loopback, link-local and RFC1918 targets. */
function isPrivateHost(hostname: string): boolean {
  const h = hostname.toLowerCase();
  if (h === 'localhost' || h.endsWith('.localhost') || h.endsWith('.internal') || h.endsWith('.local')) {
    return true;
  }
  if (h === '::1' || h === '0.0.0.0') return true;

  const ipv4 = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(h);
  if (!ipv4) return false;

  const [a, b] = [Number(ipv4[1]), Number(ipv4[2])];
  return (
    a === 10 ||
    a === 127 ||
    (a === 172 && b >= 16 && b <= 31) ||
    (a === 192 && b === 168) ||
    (a === 169 && b === 254) ||
    a === 0
  );
}
