import { env } from '@/config/env';
import { fetchJson } from '@/lib/http';
import { createLogger } from '@/lib/logger';

/**
 * CT log discovery.
 *
 * Verified live: `https://www.gstatic.com/ct/log_list/v3/log_list.json` returns
 * `{ version, log_list_timestamp, operators: [{ name, logs: [...] }] }` where
 * each log carries `url`, `description`, `state` (one of `usable`/`qualified`/
 * `pending`/`readonly`/`retired`), and a `temporal_interval` naming the cert
 * validity window it shards.
 *
 * We only want logs that are (a) usable and (b) currently accepting certs — a
 * log whose temporal interval ended is full of last year's certificates and
 * polling it is wasted work.
 */

const log = createLogger('ingest.ct.loglist');

interface RawLog {
  description?: string;
  log_id?: string;
  url?: string;
  state?: Record<string, { timestamp?: string }>;
  temporal_interval?: { start_inclusive?: string; end_exclusive?: string };
}

interface RawLogList {
  version?: string;
  log_list_timestamp?: string;
  operators?: { name?: string; logs?: RawLog[] }[];
}

export interface CtLog {
  url: string;
  description: string;
  operator: string;
}

/** Normalise the log URL to always end in a single slash. */
function normaliseLogUrl(url: string): string {
  return url.replace(/\/+$/, '') + '/';
}

function isCurrentlyAccepting(entry: RawLog, now: Date): boolean {
  const interval = entry.temporal_interval;
  // A log without a temporal interval accepts everything.
  if (!interval) return true;
  if (interval.start_inclusive && new Date(interval.start_inclusive) > now) return false;
  if (interval.end_exclusive && new Date(interval.end_exclusive) <= now) return false;
  return true;
}

/**
 * Fetch the log list and return the logs worth polling, newest-shard first.
 * `limit` caps how many we poll concurrently (`CT_MAX_LOGS`).
 */
export async function fetchUsableLogs(limit = env.CT_MAX_LOGS, now = new Date()): Promise<CtLog[]> {
  const list = await fetchJson<RawLogList>(env.CT_LOG_LIST_URL, { timeoutMs: 30_000 });

  const usable: CtLog[] = [];
  for (const operator of list.operators ?? []) {
    for (const entry of operator.logs ?? []) {
      if (!entry.url) continue;
      // `state` is an object keyed by the state name; only `usable` logs are
      // guaranteed to serve get-entries reliably.
      if (!entry.state || !('usable' in entry.state)) continue;
      if (!isCurrentlyAccepting(entry, now)) continue;

      usable.push({
        url: normaliseLogUrl(entry.url),
        description: entry.description ?? entry.url,
        operator: operator.name ?? 'unknown',
      });
    }
  }

  // Spread across operators so one operator's outage does not silence us.
  const byOperator = new Map<string, CtLog[]>();
  for (const l of usable) {
    const bucket = byOperator.get(l.operator) ?? [];
    bucket.push(l);
    byOperator.set(l.operator, bucket);
  }

  const selected: CtLog[] = [];
  const operators = [...byOperator.values()];
  let round = 0;
  while (selected.length < limit) {
    let addedThisRound = false;
    for (const bucket of operators) {
      const candidate = bucket[round];
      if (candidate) {
        selected.push(candidate);
        addedThisRound = true;
        if (selected.length >= limit) break;
      }
    }
    if (!addedThisRound) break;
    round += 1;
  }

  log.info('ct log list fetched', {
    version: list.version,
    total_usable: usable.length,
    selected: selected.length,
  });

  return selected;
}
