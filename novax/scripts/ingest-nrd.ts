/**
 * Ingest one day of the NRD feed.
 *
 *   npm run ingest:nrd                    # most recent reliably-published day
 *   npm run ingest:nrd -- --date=2026-08-13
 *
 * Safe to re-run: the apex unique index makes a repeat run a no-op.
 */
import { ingestNrdDay, latestAvailableFeedDate } from '@/ingest/nrd';
import { createLogger } from '@/lib/logger';
import { sql } from '@/db';

const log = createLogger('script.ingest-nrd');

async function main() {
  const dateArg = process.argv.find((a) => a.startsWith('--date='))?.split('=')[1];
  const date = dateArg ?? latestAvailableFeedDate();

  const result = await ingestNrdDay(date);

  log.info('done', { ...result });
  if (result.warning) {
    log.warn('run completed with a warning — treat this day as incomplete', {
      warning: result.warning,
    });
  }
  await sql.end();
}

main().catch(async (err) => {
  log.error('ingest failed', err);
  await sql.end().catch(() => {});
  process.exit(1);
});
