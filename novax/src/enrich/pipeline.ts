import { eq, and, inArray, sql as raw } from 'drizzle-orm';
import { db, domains, domainDns, domainHttp, enrichmentCosts } from '@/db';
import { env } from '@/config/env';
import { createLogger } from '@/lib/logger';
import { mapLimit } from '@/lib/backoff';
import { enqueue, enqueueMany, QUEUES } from '@/queue';
import { resolveBatch, claimDomainsForDns } from './dns';
import { probeDomain, saveProbeResult } from './http';
import { lookupRdap, saveRdapResult } from './rdap';

/**
 * Enrichment orchestration (spec §6).
 *
 * The rule that makes this affordable: **cheap checks gate expensive ones, and
 * nothing that failed a gate is ever enriched further.** Concretely:
 *
 *   DNS (free, batched)  ──fails──▶ 72h requeue, stop.
 *        │ passes
 *        ▼
 *   HTTP probe (bandwidth) ──parked──▶ stop.
 *        │ real page
 *        ▼
 *   RDAP (rate-limited)  ──▶ confirms registration age
 *        │
 *        ▼
 *   ready to score
 *
 * Measured attrition, over 300 domains from the 2026-08-13 feed:
 *   DNS gate killed 43% (129/300) as unconfigured
 *   of the 171 survivors, 19 were unreachable, 3 outright parked, 59 served an
 *   empty or placeholder page
 * The 43% is well below the ~90% first assumed, which is why the HTTP and RDAP
 * stages are batched rather than one-job-per-domain — see DECISIONS.md.
 *
 * Every stage records what it cost in `enrichment_costs`, because the spec sets
 * a unit-economics tripwire and you cannot honour a budget you do not measure.
 */

const log = createLogger('enrich.pipeline');

/**
 * Cost model, in micro-dollars (1/1,000,000 USD).
 *
 * These are amortised infrastructure costs, not invoices: DNS and RDAP are
 * bandwidth and CPU on a box we already pay for. They exist so that the ratio
 * between stages is visible and so the per-domain total can be compared against
 * ENRICHMENT_BUDGET_MICRO_USD. Adjust them to match your actual hosting bill.
 */
export const STAGE_COST_MICRO_USD = {
  /** Amortised per domain inside a batch: a handful of UDP queries. */
  dns: 1,
  /** Up to 512KB of egress/ingress plus a TLS handshake. */
  http: 20,
  /** One HTTPS request to a registry, rate-limited. */
  rdap: 5,
} as const;

export async function recordCost(
  apex: string,
  stage: keyof typeof STAGE_COST_MICRO_USD | 'classifier',
  microUsd: number,
  detail?: Record<string, unknown>,
): Promise<void> {
  await db.insert(enrichmentCosts).values({
    apex,
    stage,
    microUsd,
    detail: detail ?? null,
  });
}

/** Total spent on one domain so far. */
export async function spendForDomain(apex: string): Promise<number> {
  const rows = await db
    .select({ total: raw<number>`coalesce(sum(${enrichmentCosts.microUsd}), 0)::int` })
    .from(enrichmentCosts)
    .where(eq(enrichmentCosts.apex, apex));
  return rows[0]?.total ?? 0;
}

/** True when this domain has already consumed its enrichment budget. */
export async function isOverBudget(apex: string): Promise<boolean> {
  return (await spendForDomain(apex)) >= env.ENRICHMENT_BUDGET_MICRO_USD;
}

// --- Stage 1: DNS ----------------------------------------------------------

/**
 * Claim a batch of domains and resolve them, then fan out the survivors.
 * Returns how many passed the gate.
 */
export async function runDnsStage(batchSize = env.QUEUE_DNS_BATCH_SIZE): Promise<number> {
  const apexes = await claimDomainsForDns(batchSize);
  if (apexes.length === 0) return 0;

  const results = await resolveBatch(apexes);

  for (const result of results) {
    await recordCost(result.apex, 'dns', STAGE_COST_MICRO_USD.dns, {
      mx_provider: result.mxProvider,
      mx_kind: result.mxKind,
    });
  }

  const survivors = results.filter((r) => r.passed).map((r) => r.apex);
  if (survivors.length > 0) {
    // Chunk into probe batches. The singleton key is the chunk's first apex,
    // which collapses an accidental duplicate fan-out of the same batch.
    const chunks: { apexes: string[] }[] = [];
    for (let i = 0; i < survivors.length; i += env.QUEUE_HTTP_BATCH_SIZE) {
      chunks.push({ apexes: survivors.slice(i, i + env.QUEUE_HTTP_BATCH_SIZE) });
    }
    await enqueueMany(QUEUES.HTTP_PROBE, chunks);
  }

  return survivors.length;
}

// --- Stage 2: HTTP probe ---------------------------------------------------

export interface HttpStageResult {
  probed: number;
  parked: number;
  survivors: string[];
}

/**
 * Probe a batch of domains.
 *
 * Parking is terminal: a parked domain does not proceed to RDAP, because we
 * already know the answer and RDAP is the rate-limited stage.
 *
 * Per-item failures are caught and recorded rather than thrown, so one dead
 * host cannot cause the whole batch — including its successes — to be retried.
 */
export async function runHttpStage(apexes: string[]): Promise<HttpStageResult> {
  if (apexes.length === 0) return { probed: 0, parked: 0, survivors: [] };

  const outcomes = await mapLimit(apexes, env.HTTP_PROBE_CONCURRENCY, async (apex) => {
    try {
      if (await isOverBudget(apex)) {
        log.warn('domain over enrichment budget; skipping http', { apex });
        return { apex, parked: false, proceed: false };
      }

      const result = await probeDomain(apex);
      await saveProbeResult(result);
      await recordCost(apex, 'http', STAGE_COST_MICRO_USD.http, {
        status: result.statusCode,
        bytes: result.contentLength,
        parked: result.isParked,
      });

      if (result.isParked) {
        await db
          .update(domains)
          .set({ status: 'enriched', updatedAt: new Date() })
          .where(eq(domains.apex, apex));
        log.debug('parked; stopping enrichment', { apex, vendor: result.parkingVendor });
        // Still needs scoring — the rules layer turns "parked" into a kill row.
        await enqueue(QUEUES.SCORE_RULES, { apexes: [apex] }, { singletonKey: `score:${apex}` });
        return { apex, parked: true, proceed: false };
      }

      if (result.error) {
        await db
          .update(domainHttp)
          .set({ failureCount: raw`${domainHttp.failureCount} + 1`, lastAttemptedAt: new Date() })
          .where(and(eq(domainHttp.apex, apex), eq(domainHttp.isCurrent, true)));
      }

      // Note a domain disallowed by robots.txt still proceeds: RDAP uses no
      // page content at all, so there is nothing to comply away.
      return { apex, parked: false, proceed: true };
    } catch (err) {
      log.error('http probe failed for one domain; batch continues', err, { apex });
      return { apex, parked: false, proceed: false };
    }
  });

  const survivors = outcomes.filter((o) => o.proceed).map((o) => o.apex);
  if (survivors.length > 0) {
    const chunks: { apexes: string[] }[] = [];
    for (let i = 0; i < survivors.length; i += env.QUEUE_RDAP_BATCH_SIZE) {
      chunks.push({ apexes: survivors.slice(i, i + env.QUEUE_RDAP_BATCH_SIZE) });
    }
    await enqueueMany(QUEUES.RDAP_LOOKUP, chunks);
  }

  return {
    probed: apexes.length,
    parked: outcomes.filter((o) => o.parked).length,
    survivors,
  };
}

// --- Stage 3: RDAP ---------------------------------------------------------

/**
 * Look up a batch. Concurrency is deliberately low: the per-registry token
 * bucket inside `lookupRdap` is the real limiter, and piling requests up behind
 * it just holds sockets open.
 */
export async function runRdapStage(apexes: string[]): Promise<number> {
  if (apexes.length === 0) return 0;

  const done = await mapLimit(apexes, 5, async (apex) => {
    try {
      if (await isOverBudget(apex)) {
        log.warn('domain over enrichment budget; skipping rdap', { apex });
        return apex;
      }

      const result = await lookupRdap(apex);
      await saveRdapResult(result);
      await recordCost(apex, 'rdap', STAGE_COST_MICRO_USD.rdap, {
        registrar: result.registrar,
        had_redactions: result.hadRedactions,
      });
      return apex;
    } catch (err) {
      log.error('rdap lookup failed for one domain; batch continues', err, { apex });
      return apex;
    }
  });

  await db
    .update(domains)
    .set({ status: 'enriched', updatedAt: new Date() })
    .where(inArray(domains.apex, done));

  // Enrichment complete; hand the batch to the scoring layer.
  await enqueue(QUEUES.SCORE_RULES, { apexes: done });

  return done.length;
}

// --- Reporting -------------------------------------------------------------

export interface EnrichmentStats {
  totalDomains: number;
  byStatus: Record<string, number>;
  dnsGateKillRate: number;
  parkedRate: number;
  avgCostMicroUsdPerDomain: number;
  enrichmentFailureRate: number;
}

/** Pipeline health, surfaced on `/health` (spec §11). */
export async function enrichmentStats(): Promise<EnrichmentStats> {
  const statusRows = await db
    .select({ status: domains.status, count: raw<number>`count(*)::int` })
    .from(domains)
    .groupBy(domains.status);

  const byStatus: Record<string, number> = {};
  let total = 0;
  for (const row of statusRows) {
    byStatus[row.status] = row.count;
    total += row.count;
  }

  const [dnsRow] = await db
    .select({
      observed: raw<number>`count(*)::int`,
      failures: raw<number>`count(*) filter (where ${domainDns.failureCount} > 0)::int`,
    })
    .from(domainDns)
    .where(eq(domainDns.isCurrent, true));

  const [httpRow] = await db
    .select({
      probed: raw<number>`count(*)::int`,
      parked: raw<number>`count(*) filter (where ${domainHttp.isParked})::int`,
      failures: raw<number>`count(*) filter (where ${domainHttp.lastError} is not null)::int`,
    })
    .from(domainHttp)
    .where(eq(domainHttp.isCurrent, true));

  const [costRow] = await db
    .select({
      total: raw<number>`coalesce(sum(${enrichmentCosts.microUsd}), 0)::bigint`,
      domains: raw<number>`count(distinct ${enrichmentCosts.apex})::int`,
    })
    .from(enrichmentCosts);

  const unconfigured = byStatus['unconfigured'] ?? 0;
  const dnsObserved = dnsRow?.observed ?? 0;
  const probed = httpRow?.probed ?? 0;
  const attempted = (dnsRow?.observed ?? 0) + probed;
  const failures = (dnsRow?.failures ?? 0) + (httpRow?.failures ?? 0);

  return {
    totalDomains: total,
    byStatus,
    dnsGateKillRate: dnsObserved === 0 ? 0 : unconfigured / dnsObserved,
    parkedRate: probed === 0 ? 0 : (httpRow?.parked ?? 0) / probed,
    avgCostMicroUsdPerDomain:
      !costRow || costRow.domains === 0 ? 0 : Number(costRow.total) / costRow.domains,
    enrichmentFailureRate: attempted === 0 ? 0 : failures / attempted,
  };
}
