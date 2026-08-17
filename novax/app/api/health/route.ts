import { NextResponse } from 'next/server';
import { buildHealthReport } from '@/ops/health';
import { createLogger } from '@/lib/logger';

/**
 * GET /api/health — the operational endpoint from spec §11.
 *
 * Unauthenticated so an external monitor can poll it, but it exposes only
 * aggregate counters, never domain data.
 *
 * Returns 200 when healthy or degraded and 503 when down, so a plain
 * status-code monitor works without parsing the body.
 */

const log = createLogger('api.health');

export const dynamic = 'force-dynamic';

export async function GET() {
  try {
    const report = await buildHealthReport();
    return NextResponse.json(report, {
      status: report.status === 'down' ? 503 : 200,
      headers: { 'Cache-Control': 'no-store' },
    });
  } catch (err) {
    log.error('health check failed', err);
    return NextResponse.json(
      {
        status: 'down',
        checked_at: new Date().toISOString(),
        problems: ['health check itself failed — the database is probably unreachable'],
      },
      { status: 503, headers: { 'Cache-Control': 'no-store' } },
    );
  }
}
