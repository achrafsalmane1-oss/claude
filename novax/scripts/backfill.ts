/**
 * Re-enrich a date range (spec §11).
 *
 *   npm run backfill -- --from=2026-08-10 --to=2026-08-13
 *   npm run backfill -- --from=2026-08-10 --to=2026-08-13 --stage=http --dry-run
 *   npm run backfill -- --apex=example.com
 *
 * Use this after fixing a parser or changing the scoring rules: it resets the
 * chosen domains to the start of the chosen stage and lets the normal pipeline
 * pick them up, rather than running a second, divergent code path.
 */
import { sql as raw } from 'drizzle-orm';
import { db, sql } from '@/db';
import { createLogger } from '@/lib/logger';
import { runScoring } from '@/score/pipeline';
import { closeHttp } from '@/lib/http';

const log = createLogger('script.backfill');

type Stage = 'dns' | 'http' | 'rdap' | 'score';

async function main() {
  const arg = (n: string) => process.argv.find((a) => a.startsWith(`--${n}=`))?.split('=')[1];
  const from = arg('from');
  const to = arg('to');
  const apex = arg('apex');
  const stage = (arg('stage') ?? 'dns') as Stage;
  const dryRun = process.argv.includes('--dry-run');
  const limit = Number(arg('limit') ?? 100_000);

  if (!apex && !from) {
    process.stderr.write(
      'usage: npm run backfill -- --from=YYYY-MM-DD [--to=YYYY-MM-DD] [--stage=dns|http|rdap|score] [--limit=N] [--dry-run]\n' +
        '       npm run backfill -- --apex=example.com\n',
    );
    process.exit(1);
  }

  const where = apex
    ? raw`apex = ${apex}`
    : raw`first_seen_at >= ${from}::date and first_seen_at < (${to ?? from}::date + interval '1 day')`;

  const [countRow] = await db.execute<{ count: number }>(
    raw`select count(*)::int as count from domains where ${where} and is_suppressed = false`,
  );
  const total = countRow?.count ?? 0;

  log.info('backfill target', { from, to, apex, stage, total, dry_run: dryRun });

  if (dryRun) {
    log.info('dry run: nothing changed');
    await sql.end();
    return;
  }

  if (stage === 'score') {
    // Re-score in place: enrichment is untouched, only the scoring layer runs.
    // This is the common case after a rules change, and it is free.
    const rows = await db.execute<{ apex: string }>(
      raw`select apex from domains where ${where} and is_suppressed = false
          and status in ('enriched', 'scored', 'rejected') limit ${limit}`,
    );
    const apexes = [...rows].map((r) => r.apex);
    log.info('rescoring', { count: apexes.length });

    const chunkSize = 500;
    for (let i = 0; i < apexes.length; i += chunkSize) {
      const chunk = apexes.slice(i, i + chunkSize);
      const result = await runScoring(chunk, { useClassifier: false });
      log.info('rescored chunk', { offset: i, ...result });
    }
    await closeHttp();
    await sql.end();
    return;
  }

  // For the enrichment stages, reset status so the normal pumps re-claim them.
  // `requeue_after` is cleared too, or an unconfigured domain would wait 72h.
  const statusFor: Record<Exclude<Stage, 'score'>, string> = {
    dns: 'discovered',
    http: 'enriching',
    rdap: 'enriching',
  };

  const updated = await db.execute<{ apex: string }>(
    raw`update domains set status = ${statusFor[stage]}, requeue_after = null, updated_at = now()
        where ${where} and is_suppressed = false
        and id in (select id from domains where ${where} limit ${limit})
        returning apex`,
  );

  log.info('backfill queued', {
    stage,
    reset_to: statusFor[stage],
    domains: [...updated].length,
    note: 'the worker will pick these up on its next pump tick',
  });

  await closeHttp();
  await sql.end();
}

main().catch(async (err) => {
  log.error('backfill failed', err);
  await sql.end().catch(() => {});
  process.exit(1);
});
