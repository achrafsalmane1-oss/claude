/**
 * The worker process.
 *
 * One long-running Node process (spec §3: not serverless) that owns:
 *   - the CT log poller, which holds long-lived connections
 *   - every queued job handler
 *   - the periodic schedule: daily feed, stage pumps, digests, alerts
 *
 * Run with `npm run worker`. Deployed as a second Railway service off the same
 * image as the web app, with NOVAX_ROLE=worker.
 */
process.env.NOVAX_ROLE = 'worker';

import { env } from '@/config/env';
import { createLogger } from '@/lib/logger';
import { closeHttp } from '@/lib/http';
import { sql } from '@/db';
import { getBoss, work, enqueue, stopQueue, QUEUES } from '@/queue';
import { ctPoller } from '@/ingest/ct/poller';
import { ingestNrdDay, latestAvailableFeedDate } from '@/ingest/nrd';
import { runDnsStage, runHttpStage, runRdapStage } from '@/enrich/pipeline';
import { runScoring, claimDomainsForScoring } from '@/score/pipeline';
import { deliverWebhook, activeWebhookIds } from '@/delivery/webhooks';
import { sendDigest, digestsDueNow } from '@/delivery/digest';
import { verifyOptOut, pendingOptOuts } from '@/compliance/opt-out';
import { checkAndAlert } from '@/ops/alerts';
import { pruneUsage } from '@/api/rate-limit';
import { db, optOuts } from '@/db';
import { eq } from 'drizzle-orm';

const log = createLogger('worker');

let shuttingDown = false;
const intervals: NodeJS.Timeout[] = [];

/** Run `fn` every `ms`, logging failures without letting them kill the timer. */
function every(name: string, ms: number, fn: () => Promise<void>): void {
  const tick = async () => {
    if (shuttingDown) return;
    try {
      await fn();
    } catch (err) {
      log.error(`scheduled task failed: ${name}`, err);
    }
  };
  intervals.push(setInterval(tick, ms));
  // Run once shortly after boot rather than waiting a full interval.
  setTimeout(tick, 5_000);
}

async function registerHandlers(): Promise<void> {
  await work(QUEUES.NRD_INGEST, async ({ date }) => {
    await ingestNrdDay(date);
  });

  await work(QUEUES.DNS_RESOLVE, async ({ apexes }) => {
    // An empty payload means "claim whatever is next", which is how the pump
    // schedules work without having to know what is pending.
    if (apexes.length === 0) await runDnsStage();
    else await runDnsStage(apexes.length);
  });

  await work(QUEUES.HTTP_PROBE, async ({ apexes }) => {
    await runHttpStage(apexes);
  });

  await work(QUEUES.RDAP_LOOKUP, async ({ apexes }) => {
    await runRdapStage(apexes);
  });

  await work(QUEUES.SCORE_RULES, async ({ apexes }) => {
    await runScoring(apexes);
  });

  await work(QUEUES.WEBHOOK_DELIVER, async ({ webhookId }) => {
    await deliverWebhook(webhookId);
  });

  await work(QUEUES.DIGEST_SEND, async ({ savedSearchId }) => {
    await sendDigest(savedSearchId);
  });

  await work(QUEUES.OPTOUT_VERIFY, async ({ optOutId }) => {
    const rows = await db.select({ apex: optOuts.apex }).from(optOuts).where(eq(optOuts.id, optOutId)).limit(1);
    if (rows[0]) await verifyOptOut(rows[0].apex);
  });
}

function startSchedule(): void {
  // --- Daily NRD feed -----------------------------------------------------
  // Hourly check, but ingestNrdDay is idempotent, so re-running a day already
  // ingested costs one download and inserts nothing.
  every('nrd feed', 3_600_000, async () => {
    const date = latestAvailableFeedDate();
    await enqueue(QUEUES.NRD_INGEST, { date }, { singletonKey: `nrd:${date}` });
  });

  // --- Stage pumps --------------------------------------------------------
  // The pipeline is pull-based: each pump claims whatever is ready for its
  // stage. Later stages are fanned out by the stage before them, so only the
  // first one needs a pump.
  every('dns pump', 60_000, async () => {
    let queued = 0;
    // Several batches per tick, so a large backlog drains rather than trickles.
    for (let i = 0; i < 5; i++) {
      const survivors = await runDnsStage();
      if (survivors === 0) break;
      queued += survivors;
    }
    if (queued > 0) log.info('dns pump', { queued_for_probe: queued });
  });

  // --- Scoring sweep ------------------------------------------------------
  // Catches anything that finished enrichment but missed its fan-out (a crash
  // between stages, say). The normal path is fan-out from the RDAP stage.
  every('scoring sweep', 300_000, async () => {
    const apexes = await claimDomainsForScoring(env.CLASSIFIER_MAX_PER_RUN);
    if (apexes.length > 0) {
      await enqueue(QUEUES.SCORE_RULES, { apexes });
      log.info('scoring sweep', { queued: apexes.length });
    }
  });

  // --- Delivery -----------------------------------------------------------
  every('webhooks', 300_000, async () => {
    for (const id of await activeWebhookIds()) {
      await enqueue(QUEUES.WEBHOOK_DELIVER, { webhookId: id }, { singletonKey: `wh:${id}` });
    }
  });

  every('digests', 900_000, async () => {
    for (const id of await digestsDueNow()) {
      await enqueue(QUEUES.DIGEST_SEND, { savedSearchId: id }, { singletonKey: `digest:${id}` });
    }
  });

  // --- Compliance ---------------------------------------------------------
  // Re-check pending opt-outs: DNS changes take time to propagate, and the
  // requester should not have to come back and press a button.
  every('opt-out verification', 900_000, async () => {
    for (const row of await pendingOptOuts()) {
      await enqueue(QUEUES.OPTOUT_VERIFY, { optOutId: row.id }, { singletonKey: `optout:${row.id}` });
    }
  });

  // --- Ops ----------------------------------------------------------------
  every('alerts', 120_000, async () => {
    await checkAndAlert();
  });

  every('maintenance', 6 * 3_600_000, async () => {
    const pruned = await pruneUsage();
    if (pruned > 0) log.info('pruned old usage rows', { rows: pruned });
  });
}

async function shutdown(signal: string): Promise<void> {
  if (shuttingDown) return;
  shuttingDown = true;
  log.info('shutting down', { signal });

  for (const t of intervals) clearInterval(t);
  ctPoller.stop();

  // Order matters. The queue must drain its in-flight handlers *before* the
  // HTTP agent and the database pool are torn down, or every running probe
  // fails on a closed connection during what should be a clean shutdown.
  await stopQueue().catch((err) => log.error('queue shutdown failed', err));
  await closeHttp().catch(() => {});
  await sql.end().catch(() => {});

  log.info('shutdown complete');
  process.exit(0);
}

async function main(): Promise<void> {
  log.info('worker starting', {
    node: process.version,
    ct_enabled: env.CT_ENABLED,
    classifier: env.CLASSIFIER_ENABLED && Boolean(env.ANTHROPIC_API_KEY) ? env.CLASSIFIER_MODEL : 'disabled',
  });

  await getBoss();
  await registerHandlers();
  startSchedule();

  process.on('SIGTERM', () => void shutdown('SIGTERM'));
  process.on('SIGINT', () => void shutdown('SIGINT'));
  // A rejection that reaches here is a bug; log it loudly but keep serving.
  process.on('unhandledRejection', (reason) => {
    log.error('unhandled rejection', reason);
  });

  if (env.CT_ENABLED) {
    // Never resolves while running; a failure inside must not stop the worker.
    void ctPoller.start().catch((err) => log.error('ct poller stopped', err));
  }

  log.info('worker ready');
}

main().catch(async (err) => {
  log.error('worker failed to start', err);
  await sql.end().catch(() => {});
  process.exit(1);
});
