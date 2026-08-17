import { desc, eq, sql as raw } from 'drizzle-orm';
import { db, ctLogState, feedRuns, domains, domainScores } from '@/db';
import { env } from '@/config/env';
import { queueDepths } from '@/queue';
import { enrichmentStats } from '@/enrich/pipeline';

/**
 * Health reporting (spec §11).
 *
 * The four metrics the spec names, plus enough context to act on them:
 *   - seconds since the last CT event
 *   - last successful NRD feed download
 *   - queue depth per job type
 *   - enrichment failure rate
 *
 * `status` is derived so a monitor can alert on one field instead of parsing
 * the whole document.
 */

export type HealthStatus = 'ok' | 'degraded' | 'down';

export interface HealthReport {
  status: HealthStatus;
  checked_at: string;
  problems: string[];
  ct: {
    enabled: boolean;
    seconds_since_last_event: number | null;
    active_logs: number;
    logs_with_errors: number;
    total_entries_processed: number;
  };
  nrd_feed: {
    last_success_at: string | null;
    last_success_date: string | null;
    hours_since_success: number | null;
    last_status: string | null;
    last_warning: string | null;
  };
  queues: Record<string, number>;
  pipeline: {
    total_domains: number;
    by_status: Record<string, number>;
    dns_gate_kill_rate: number;
    parked_rate: number;
    enrichment_failure_rate: number;
    avg_cost_micro_usd_per_domain: number;
  };
  scoring: {
    scored_total: number;
    hot: number;
    warm: number;
    scored_last_24h: number;
  };
}

export async function buildHealthReport(): Promise<HealthReport> {
  const problems: string[] = [];

  // --- CT ------------------------------------------------------------------
  const ctRows = await db.select().from(ctLogState).orderBy(desc(ctLogState.lastEventAt));
  const lastEvent = ctRows.find((r) => r.lastEventAt)?.lastEventAt ?? null;
  const secondsSinceCt = lastEvent ? Math.floor((Date.now() - lastEvent.getTime()) / 1000) : null;
  const logsWithErrors = ctRows.filter((r) => r.consecutiveFailures > 0).length;

  if (env.CT_ENABLED) {
    if (secondsSinceCt === null) {
      problems.push('CT stream has never produced an event');
    } else if (secondsSinceCt > env.CT_SILENCE_ALERT_SECONDS) {
      problems.push(
        `CT stream silent for ${Math.floor(secondsSinceCt / 60)} minutes (threshold ${Math.floor(env.CT_SILENCE_ALERT_SECONDS / 60)})`,
      );
    }
  }

  // --- NRD feed ------------------------------------------------------------
  const feedRows = await db
    .select()
    .from(feedRuns)
    .where(eq(feedRuns.feed, 'nrd'))
    .orderBy(desc(feedRuns.startedAt))
    .limit(5);

  const lastSuccess = feedRows.find((r) => r.status === 'success');
  const hoursSinceFeed = lastSuccess?.finishedAt
    ? Math.floor((Date.now() - lastSuccess.finishedAt.getTime()) / 3_600_000)
    : null;

  if (hoursSinceFeed === null) {
    problems.push('NRD feed has never completed successfully');
  } else if (hoursSinceFeed > 36) {
    problems.push(`NRD feed has not succeeded in ${hoursSinceFeed} hours`);
  }
  if (feedRows[0]?.status === 'failed') {
    problems.push(`most recent NRD feed run failed: ${feedRows[0].error ?? 'unknown error'}`);
  }
  if (lastSuccess?.warning) {
    problems.push(`NRD feed warning: ${lastSuccess.warning}`);
  }

  // --- Queues --------------------------------------------------------------
  let queues: Record<string, number> = {};
  try {
    queues = await queueDepths();
  } catch {
    problems.push('queue is unreachable');
  }

  // --- Pipeline ------------------------------------------------------------
  const pipeline = await enrichmentStats();
  if (pipeline.enrichmentFailureRate > 0.25) {
    problems.push(`enrichment failure rate is ${(pipeline.enrichmentFailureRate * 100).toFixed(1)}%`);
  }
  if (pipeline.avgCostMicroUsdPerDomain > env.ENRICHMENT_BUDGET_MICRO_USD) {
    problems.push(
      `average enrichment cost ${pipeline.avgCostMicroUsdPerDomain.toFixed(0)} micro-USD exceeds the ${env.ENRICHMENT_BUDGET_MICRO_USD} budget`,
    );
  }

  // --- Scoring -------------------------------------------------------------
  const [scoreRow] = await db
    .select({
      total: raw<number>`count(*)::int`,
      hot: raw<number>`count(*) filter (where ${domainScores.tier} = 'hot')::int`,
      warm: raw<number>`count(*) filter (where ${domainScores.tier} = 'warm')::int`,
      last24h: raw<number>`count(*) filter (where ${domainScores.scoredAt} > now() - interval '24 hours')::int`,
    })
    .from(domainScores)
    .where(eq(domainScores.isCurrent, true));

  // A CT outage alone is degraded (the daily feed still covers us); losing the
  // feed as well means we are blind.
  const status: HealthStatus =
    problems.length === 0 ? 'ok' : problems.length >= 3 || hoursSinceFeed === null ? 'down' : 'degraded';

  return {
    status,
    checked_at: new Date().toISOString(),
    problems,
    ct: {
      enabled: env.CT_ENABLED,
      seconds_since_last_event: secondsSinceCt,
      active_logs: ctRows.filter((r) => r.enabled).length,
      logs_with_errors: logsWithErrors,
      total_entries_processed: ctRows.reduce((sum, r) => sum + Number(r.entriesProcessed), 0),
    },
    nrd_feed: {
      last_success_at: lastSuccess?.finishedAt?.toISOString() ?? null,
      last_success_date: lastSuccess?.feedDate ?? null,
      hours_since_success: hoursSinceFeed,
      last_status: feedRows[0]?.status ?? null,
      last_warning: lastSuccess?.warning ?? null,
    },
    queues,
    pipeline: {
      total_domains: pipeline.totalDomains,
      by_status: pipeline.byStatus,
      dns_gate_kill_rate: Number(pipeline.dnsGateKillRate.toFixed(4)),
      parked_rate: Number(pipeline.parkedRate.toFixed(4)),
      enrichment_failure_rate: Number(pipeline.enrichmentFailureRate.toFixed(4)),
      avg_cost_micro_usd_per_domain: Number(pipeline.avgCostMicroUsdPerDomain.toFixed(2)),
    },
    scoring: {
      scored_total: scoreRow?.total ?? 0,
      hot: scoreRow?.hot ?? 0,
      warm: scoreRow?.warm ?? 0,
      scored_last_24h: scoreRow?.last24h ?? 0,
    },
  };
}

export { domains };
