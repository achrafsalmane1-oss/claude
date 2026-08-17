/**
 * Score enriched domains.
 *
 *   npm run score:run                    # rules + classifier (if a key is set)
 *   npm run score:run -- --rules-only    # rules layer only, no LLM cost
 *   npm run score:run -- --limit=500
 */
import { runScoring, claimDomainsForScoring } from '@/score/pipeline';
import { createLogger } from '@/lib/logger';
import { sql } from '@/db';
import { closeHttp } from '@/lib/http';

const log = createLogger('script.score');

async function main() {
  const rulesOnly = process.argv.includes('--rules-only');
  const limitArg = process.argv.find((a) => a.startsWith('--limit='))?.split('=')[1];
  const limit = limitArg ? Number(limitArg) : 1_000;

  const apexes = await claimDomainsForScoring(limit);
  log.info('claimed for scoring', { count: apexes.length, rules_only: rulesOnly });

  if (apexes.length === 0) {
    log.info('nothing to score');
    await sql.end();
    return;
  }

  const result = await runScoring(apexes, rulesOnly ? { useClassifier: false } : {});
  log.info('done', { ...result });

  await closeHttp();
  await sql.end();
}

main().catch(async (err) => {
  log.error('scoring run failed', err);
  await sql.end().catch(() => {});
  process.exit(1);
});
