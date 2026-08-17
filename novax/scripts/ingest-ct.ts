/**
 * Run the CT poller standalone, for debugging.
 *
 *   npm run ingest:ct -- --seconds=60
 *
 * In production this runs inside the worker process, not here.
 */
import { ctPoller } from '@/ingest/ct/poller';
import { createLogger } from '@/lib/logger';
import { sql } from '@/db';
import { closeHttp } from '@/lib/http';

const log = createLogger('script.ingest-ct');

async function main() {
  const secondsArg = process.argv.find((a) => a.startsWith('--seconds='))?.split('=')[1];
  const seconds = secondsArg ? Number(secondsArg) : 60;

  log.info('starting CT poller', { seconds });

  const stopTimer = setTimeout(() => {
    log.info('time is up; stopping', ctPoller.health() as unknown as Record<string, unknown>);
    ctPoller.stop();
  }, seconds * 1000);

  const reporter = setInterval(() => {
    log.info('ct health', ctPoller.health() as unknown as Record<string, unknown>);
  }, 10_000);

  await ctPoller.start();

  clearTimeout(stopTimer);
  clearInterval(reporter);
  log.info('final', ctPoller.health() as unknown as Record<string, unknown>);

  await closeHttp();
  await sql.end();
}

main().catch(async (err) => {
  log.error('ct poller failed', err);
  await sql.end().catch(() => {});
  process.exit(1);
});
