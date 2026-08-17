import { z } from 'zod';
import { eq, desc } from 'drizzle-orm';
import { withApiAuth } from '@/api/handler';
import { db, savedSearches } from '@/db';
import { filterSchema } from '@/api/filters';

/**
 * Saved searches (spec §8).
 *
 *   GET  /api/v1/searches   — list this key's saved searches
 *   POST /api/v1/searches   — save a filter set, optionally with a daily digest
 *
 * The stored `filters` object is exactly the query params the domains endpoint
 * accepts, so a saved search is replayable by hand and there is no second
 * filter language to keep in sync.
 */

export const dynamic = 'force-dynamic';

const createSchema = z.object({
  name: z.string().min(1).max(200),
  filters: z.record(z.string(), z.unknown()),
  digest_enabled: z.boolean().optional(),
  digest_hour_utc: z.number().int().min(0).max(23).optional(),
});

export const GET = withApiAuth(async ({ key }) => {
  if (!key.userId) {
    return {
      body: { error: 'no_user', message: 'This API key is not attached to a user account.' },
      status: 400,
    };
  }

  const rows = await db
    .select()
    .from(savedSearches)
    .where(eq(savedSearches.userId, key.userId))
    .orderBy(desc(savedSearches.createdAt));

  return {
    body: {
      data: rows.map((r) => ({
        id: r.id,
        name: r.name,
        filters: r.filters,
        digest_enabled: r.digestEnabled,
        digest_hour_utc: r.digestHourUtc,
        last_digest_at: r.lastDigestAt?.toISOString() ?? null,
        created_at: r.createdAt.toISOString(),
      })),
      count: rows.length,
    },
    rowsReturned: rows.length,
  };
});

export const POST = withApiAuth(async ({ key, request }) => {
  if (!key.userId) {
    return {
      body: { error: 'no_user', message: 'This API key is not attached to a user account.' },
      status: 400,
    };
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

  // Validate the filters against the same schema the API uses, so a saved
  // search cannot contain a filter that will fail every time it runs.
  const filterCheck = filterSchema.safeParse(parsed.data.filters);
  if (!filterCheck.success) {
    return {
      body: {
        error: 'invalid_filters',
        message: 'The filters object is not a valid set of query parameters.',
        detail: filterCheck.error.issues,
      },
      status: 400,
    };
  }

  const rows = await db
    .insert(savedSearches)
    .values({
      userId: key.userId,
      name: parsed.data.name,
      filters: parsed.data.filters,
      digestEnabled: parsed.data.digest_enabled ?? false,
      ...(parsed.data.digest_hour_utc !== undefined
        ? { digestHourUtc: parsed.data.digest_hour_utc }
        : {}),
    })
    .returning({ id: savedSearches.id });

  return {
    body: {
      data: {
        id: rows[0]!.id,
        name: parsed.data.name,
        filters: parsed.data.filters,
        digest_enabled: parsed.data.digest_enabled ?? false,
      },
    },
    status: 201,
    rowsReturned: 1,
  };
});
