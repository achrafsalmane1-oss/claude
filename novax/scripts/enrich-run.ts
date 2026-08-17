/**
 * Run the enrichment pipeline synchronously over a batch, without the queue.
 *
 *   npm run enrich -- --batch=200
 *
 * This is the debugging path: it walks DNS -> HTTP -> RDAP inline so you can
 * watch the gate attrition happen. The worker does the same thing via pg-boss.
 */
import { claimDomainsForDns, resolveBatch } from '@/enrich/dns';
import { probeDomain, saveProbeResult } from '@/enrich/http';
import { lookupRdap, saveRdapResult } from '@/enrich/rdap';
import { recordCost, STAGE_COST_MICRO_USD, enrichmentStats } from '@/enrich/pipeline';
import { db, domains } from '@/db';
import { eq, inArray } from 'drizzle-orm';
import { mapLimit } from '@/lib/backoff';
import { env } from '@/config/env';
import { createLogger } from '@/lib/logger';
import { sql } from '@/db';
import { closeHttp } from '@/lib/http';

const log = createLogger('script.enrich');

async function main() {
  const batchArg = process.argv.find((a) => a.startsWith('--batch='))?.split('=')[1];
  const batchSize = batchArg ? Number(batchArg) : 200;

  // --- Gate 1: DNS ---
  const apexes = await claimDomainsForDns(batchSize);
  log.info('claimed for dns', { count: apexes.length });
  if (apexes.length === 0) {
    log.info('nothing to enrich');
    await sql.end();
    return;
  }

  const dnsResults = await resolveBatch(apexes);
  for (const r of dnsResults) await recordCost(r.apex, 'dns', STAGE_COST_MICRO_USD.dns);

  const survivors = dnsResults.filter((r) => r.passed);
  log.info('dns gate', {
    in: apexes.length,
    survived: survivors.length,
    killed: apexes.length - survivors.length,
    kill_rate: ((apexes.length - survivors.length) / apexes.length).toFixed(3),
    business_mx: survivors.filter((r) => r.mxKind === 'business' || r.mxKind === 'security').length,
  });

  // --- Gate 2: HTTP probe ---
  const probes = await mapLimit(survivors, env.HTTP_PROBE_CONCURRENCY, async (r) => {
    const result = await probeDomain(r.apex);
    await saveProbeResult(result);
    await recordCost(r.apex, 'http', STAGE_COST_MICRO_USD.http);
    return result;
  });

  const live = probes.filter((p) => !p.isParked && !p.error);
  log.info('http gate', {
    in: probes.length,
    reachable: probes.filter((p) => !p.error).length,
    parked: probes.filter((p) => p.isParked).length,
    placeholder: probes.filter((p) => p.isPlaceholder).length,
    survived: live.length,
    robots_blocked: probes.filter((p) => !p.robotsAllowed).length,
  });

  // --- Gate 3: RDAP (only for what survived) ---
  const rdapResults = await mapLimit(live, 5, async (p) => {
    const result = await lookupRdap(p.apex);
    await saveRdapResult(result);
    await recordCost(p.apex, 'rdap', STAGE_COST_MICRO_USD.rdap);
    return result;
  });

  log.info('rdap stage', {
    looked_up: rdapResults.length,
    with_creation_date: rdapResults.filter((r) => r.createdDate).length,
    redacted: rdapResults.filter((r) => r.hadRedactions).length,
    errors: rdapResults.filter((r) => r.error).length,
  });

  await db
    .update(domains)
    .set({ status: 'enriched', updatedAt: new Date() })
    .where(
      inArray(
        domains.apex,
        probes.map((p) => p.apex),
      ),
    );

  log.info('pipeline stats', { ...(await enrichmentStats()) } as Record<string, unknown>);

  // Show what survived, for eyeballing.
  for (const p of live.slice(0, 15)) {
    log.info('survivor', {
      apex: p.apex,
      title: p.title,
      tech: p.tech,
      status: p.statusCode,
    });
  }

  await closeHttp();
  await sql.end();
}

main().catch(async (err) => {
  log.error('enrichment run failed', err);
  await sql.end().catch(() => {});
  process.exit(1);
});
