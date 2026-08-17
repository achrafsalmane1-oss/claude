import { NextResponse } from 'next/server';
import { authenticate, recordUsage } from '@/api/auth';
import { checkRateLimit, rateLimitHeaders } from '@/api/rate-limit';
import { parseFilters } from '@/api/filters';
import { queryDomains, toCsv } from '@/api/serialize';
import { createLogger } from '@/lib/logger';

/**
 * GET /api/v1/export — CSV export (spec §8).
 *
 * Takes exactly the same filters as `/api/v1/domains`. Not routed through
 * `withApiAuth` because that helper always emits JSON, and this endpoint's
 * whole point is a `text/csv` body with a filename the browser will use.
 *
 * Capped at 10,000 rows per request: past that, the honest answer is the
 * paginated JSON endpoint rather than a request that times out halfway.
 */

const log = createLogger('api.export');
const MAX_EXPORT_ROWS = 10_000;

export const dynamic = 'force-dynamic';

export async function GET(request: Request) {
  const key = await authenticate(request.headers);
  if (!key) {
    return NextResponse.json(
      { error: 'unauthorized', message: 'Missing or invalid API key.' },
      { status: 401 },
    );
  }

  const limit = await checkRateLimit(key);
  if (!limit.allowed) {
    return NextResponse.json(
      { error: 'rate_limited', message: `Retry in ${limit.resetSeconds}s.` },
      { status: 429, headers: rateLimitHeaders(limit) },
    );
  }

  const url = new URL(request.url);

  try {
    const filters = parseFilters(url.searchParams);
    const capped = { ...filters, limit: Math.min(filters.limit, MAX_EXPORT_ROWS) };

    const result = await queryDomains(capped);
    const csv = toCsv(result.domains);
    await recordUsage(key.id, result.count);

    const date = new Date().toISOString().slice(0, 10);
    log.info('csv export', { key_id: key.id, rows: result.count });

    return new NextResponse(csv, {
      status: 200,
      headers: {
        'Content-Type': 'text/csv; charset=utf-8',
        'Content-Disposition': `attachment; filename="novax-domains-${date}.csv"`,
        ...rateLimitHeaders(limit),
      },
    });
  } catch (err) {
    log.error('csv export failed', err, { key_id: key.id });
    return NextResponse.json(
      { error: 'export_failed', message: 'Could not build the export.' },
      { status: 500, headers: rateLimitHeaders(limit) },
    );
  }
}
