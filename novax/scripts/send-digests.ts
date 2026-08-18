/**
 * Send digests that are due now, or one specific saved search.
 *
 *   npm run digest                  # everything due this hour
 *   npm run digest -- --id=3        # one saved search, regardless of schedule
 *
 * The worker does this on a schedule; this script exists so a digest can be
 * triggered and inspected by hand.
 */
import { sendDigest, digestsDueNow } from '@/delivery/digest';
import { createLogger } from '@/lib/logger';
import { sql } from '@/db';
import { closeHttp } from '@/lib/http';

const log = createLogger('script.digest');

async function main() {
  const id = process.argv.find((a) => a.startsWith('--id='))?.split('=')[1];

  const ids = id ? [Number(id)] : await digestsDueNow();
  log.info('digests to send', { count: ids.length, ids });

  for (const savedSearchId of ids) {
    const result = await sendDigest(savedSearchId);
    log.info('digest result', { ...result });
  }

  await closeHttp();
  await sql.end();
}

main().catch(async (err) => {
  log.error('digest run failed', err);
  await sql.end().catch(() => {});
  process.exit(1);
});
