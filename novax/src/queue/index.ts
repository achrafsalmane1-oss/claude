import PgBoss from 'pg-boss';
import { env } from '@/config/env';
import { createLogger } from '@/lib/logger';
import { QUEUES, QUEUE_POLICIES, type JobPayloads, type QueueName } from './jobs';

/**
 * Queue wrapper around pg-boss.
 *
 * Everything queue-related goes through this file so that swapping to BullMQ +
 * Redis (if throughput ever demands it — see DECISIONS.md) touches one module.
 */

const log = createLogger('queue');

let boss: PgBoss | null = null;

export async function getBoss(): Promise<PgBoss> {
  if (boss) return boss;

  const instance = new PgBoss({
    connectionString: env.DATABASE_URL,
    schema: env.QUEUE_SCHEMA,
    // Keep completed jobs for a day so a failed run can be inspected, then bin them.
    deleteAfterHours: 24,
    archiveCompletedAfterSeconds: 3600,
    // pg-boss owns its own schema and migrates it on start.
    migrate: true,
  });

  instance.on('error', (err) => log.error('pg-boss error', err));

  await instance.start();

  // v10 requires queues to exist before send/work.
  for (const name of Object.values(QUEUES)) {
    await instance.createQueue(name);
  }

  boss = instance;
  log.info('queue started', { queues: Object.values(QUEUES).length });
  return instance;
}

export async function stopQueue(): Promise<void> {
  if (!boss) return;
  await boss.stop({ graceful: true, wait: true });
  boss = null;
}

/** Enqueue one job. */
export async function enqueue<N extends QueueName>(
  name: N,
  data: JobPayloads[N],
  options: { startAfterSeconds?: number; singletonKey?: string; priority?: number } = {},
): Promise<string | null> {
  const b = await getBoss();
  const policy = QUEUE_POLICIES[name];
  return b.send(name, data as object, {
    retryLimit: policy.retryLimit,
    retryDelay: policy.retryDelay,
    retryBackoff: true,
    expireInSeconds: policy.expireInSeconds,
    ...(options.startAfterSeconds ? { startAfter: options.startAfterSeconds } : {}),
    // A singleton key collapses duplicate work — e.g. two CT hits both trying
    // to queue an HTTP probe for the same apex.
    ...(options.singletonKey ? { singletonKey: options.singletonKey } : {}),
    ...(options.priority !== undefined ? { priority: options.priority } : {}),
  });
}

/** Enqueue many jobs in one round trip. Used when fanning out after a gate. */
export async function enqueueMany<N extends QueueName>(
  name: N,
  items: JobPayloads[N][],
  options: { singletonKeyOf?: (item: JobPayloads[N]) => string } = {},
): Promise<void> {
  if (items.length === 0) return;
  const b = await getBoss();
  const policy = QUEUE_POLICIES[name];
  await b.insert(
    items.map((data) => ({
      name,
      data: data as object,
      retryLimit: policy.retryLimit,
      retryDelay: policy.retryDelay,
      retryBackoff: true,
      expireInSeconds: policy.expireInSeconds,
      ...(options.singletonKeyOf ? { singletonKey: options.singletonKeyOf(data) } : {}),
    })),
  );
}

/**
 * Register a handler.
 *
 * pg-boss v10 hands the handler an array of jobs; we unwrap to one-at-a-time
 * because every handler here is independently retryable and a partial failure
 * inside a fetched batch would otherwise retry the successes too.
 */
export async function work<N extends QueueName>(
  name: N,
  handler: (data: JobPayloads[N]) => Promise<void>,
  options: { concurrency?: number; pollIntervalSeconds?: number } = {},
): Promise<void> {
  const b = await getBoss();
  const jobLog = log.child(name);

  await b.work<JobPayloads[N]>(
    name,
    {
      batchSize: options.concurrency ?? env.QUEUE_CONCURRENCY,
      pollingIntervalSeconds: options.pollIntervalSeconds ?? 2,
    },
    async (jobs) => {
      for (const job of jobs) {
        const started = Date.now();
        try {
          await handler(job.data);
          jobLog.debug('job done', { job_id: job.id, ms: Date.now() - started });
        } catch (err) {
          jobLog.error('job failed', err, { job_id: job.id, ms: Date.now() - started });
          // Rethrow so pg-boss records the failure and applies the retry policy.
          throw err;
        }
      }
    },
  );

  log.info('handler registered', { queue: name });
}

/** Queue depth per job type, for `/health` (spec §11). */
export async function queueDepths(): Promise<Record<string, number>> {
  const b = await getBoss();
  const out: Record<string, number> = {};
  for (const name of Object.values(QUEUES)) {
    try {
      out[name] = await b.getQueueSize(name);
    } catch {
      out[name] = -1; // queue not yet created; -1 distinguishes it from empty
    }
  }
  return out;
}

export { QUEUES, type QueueName, type JobPayloads };
