import { eq, sql as raw } from 'drizzle-orm';
import { db, ctLogState, domains } from '@/db';
import { env } from '@/config/env';
import { fetchJson, HttpError } from '@/lib/http';
import { createLogger } from '@/lib/logger';
import { backoffDelay, sleep } from '@/lib/backoff';
import { TokenBucket } from '@/lib/token-bucket';
import { apexesFromSans, isApexLevelName } from '../apex';
import { Deduper } from '../dedupe';
import { dnsNamesFromLeafInput } from './der';
import { fetchUsableLogs, type CtLog } from './log-list';

/**
 * Certificate Transparency ingestion.
 *
 * This polls CT logs directly over RFC 6962 rather than consuming certstream.
 * The spec allows either and warns the public certstream server is flaky; its
 * own maintainers say it is a demo. Polling has no third party in the path and,
 * more importantly, is *checkpointed*: we store the next entry index per log, so
 * a crash resumes exactly where it stopped instead of losing whatever the
 * websocket was mid-flight. See DECISIONS.md.
 *
 * What a CT hit means: a TLS certificate was issued. That correlates with a new
 * site going up but proves nothing about registration age (spec §5b) — a cert on
 * a 10-year-old domain is a renewal. So a CT hit only ever creates a *candidate*
 * here; the RDAP creation date decides whether it is genuinely new.
 */

const log = createLogger('ingest.ct');

interface SthResponse {
  tree_size: number;
  timestamp: number;
  sha256_root_hash: string;
}

interface EntriesResponse {
  entries: { leaf_input: string; extra_data: string }[];
}

export interface CtHealth {
  lastEventAt: Date | null;
  secondsSinceLastEvent: number | null;
  activeLogs: number;
  entriesProcessed: number;
  apexesDiscovered: number;
  throttled: number;
  dedupeHitRate: number;
}

export class CtPoller {
  private deduper = new Deduper(env.CT_DEDUPE_LRU_SIZE);
  private lastEventAt: Date | null = null;
  private entriesProcessed = 0;
  private apexesDiscovered = 0;
  private throttled = 0;
  private running = false;
  private controller = new AbortController();
  private logs: CtLog[] = [];

  /**
   * Politeness limit, per log. Observed live: polling flat out earns HTTP 429
   * from both Google and DigiCert within seconds. Being throttled (or banned)
   * ingests nothing, so we self-limit below the threshold instead.
   */
  private rateLimiter = new TokenBucket(env.CT_REQUESTS_PER_SECOND_PER_LOG, env.CT_REQUESTS_PER_SECOND_PER_LOG);

  /** Seconds since the last entry was processed — the spec's staleness metric. */
  get secondsSinceLastEvent(): number | null {
    if (!this.lastEventAt) return null;
    return Math.floor((Date.now() - this.lastEventAt.getTime()) / 1000);
  }

  health(): CtHealth {
    return {
      lastEventAt: this.lastEventAt,
      secondsSinceLastEvent: this.secondsSinceLastEvent,
      activeLogs: this.logs.length,
      entriesProcessed: this.entriesProcessed,
      apexesDiscovered: this.apexesDiscovered,
      throttled: this.throttled,
      dedupeHitRate: this.deduper.snapshot().hitRate,
    };
  }

  async start(): Promise<void> {
    if (this.running) return;
    this.running = true;
    this.controller = new AbortController();

    this.logs = await fetchUsableLogs();
    if (this.logs.length === 0) {
      log.error('no usable CT logs found; CT ingestion disabled', undefined);
      this.running = false;
      return;
    }

    // Register each log and start at the current tree head. Backfilling a log
    // from index 0 would mean billions of historical entries; we want new certs.
    for (const l of this.logs) {
      await this.ensureLogState(l);
    }

    log.info('ct poller starting', { logs: this.logs.map((l) => l.description) });

    // One independent loop per log. A failing log backs off alone.
    await Promise.all(this.logs.map((l) => this.pollLoop(l)));
  }

  stop(): void {
    this.running = false;
    this.controller.abort();
  }

  private async ensureLogState(l: CtLog): Promise<void> {
    const existing = await db.select().from(ctLogState).where(eq(ctLogState.logUrl, l.url)).limit(1);
    if (existing.length > 0) return;

    // Start from the current head so we ingest new certificates only.
    let startIndex = 0;
    let treeSize = 0;
    try {
      const sth = await this.getSth(l.url);
      startIndex = sth.tree_size;
      treeSize = sth.tree_size;
    } catch (err) {
      log.warn('could not read initial STH; starting at 0', { log: l.url, error: String(err) });
    }

    await db
      .insert(ctLogState)
      .values({
        logUrl: l.url,
        description: l.description,
        nextIndex: startIndex,
        treeSize,
      })
      .onConflictDoNothing();
  }

  private async getSth(logUrl: string): Promise<SthResponse> {
    await this.rateLimiter.acquire(logUrl);
    return fetchJson<SthResponse>(`${logUrl}ct/v1/get-sth`, { timeoutMs: 20_000 });
  }

  private async getEntries(logUrl: string, start: number, end: number): Promise<EntriesResponse> {
    await this.rateLimiter.acquire(logUrl);
    return fetchJson<EntriesResponse>(`${logUrl}ct/v1/get-entries?start=${start}&end=${end}`, {
      timeoutMs: 30_000,
      maxBytes: 64 * 1024 * 1024,
    });
  }

  /** Poll one log until stopped. Each iteration is one get-entries call. */
  private async pollLoop(l: CtLog): Promise<void> {
    const logCtx = { log: l.description, url: l.url };

    while (this.running) {
      try {
        const state = await db
          .select()
          .from(ctLogState)
          .where(eq(ctLogState.logUrl, l.url))
          .limit(1);
        const current = state[0];
        if (!current || !current.enabled) {
          await sleep(30_000, this.controller.signal);
          continue;
        }

        let treeSize = current.treeSize;

        // Only ask for a new STH when we have caught up; the head moves fast
        // enough that re-reading it every iteration is wasted requests.
        if (current.nextIndex >= treeSize) {
          const sth = await this.getSth(l.url);
          treeSize = sth.tree_size;
          await db
            .update(ctLogState)
            .set({ treeSize, updatedAt: new Date() })
            .where(eq(ctLogState.logUrl, l.url));

          if (current.nextIndex >= treeSize) {
            // Caught up with the log. Wait for it to grow.
            await sleep(env.CT_POLL_INTERVAL_MS, this.controller.signal);
            continue;
          }
        }

        const start = current.nextIndex;
        const end = Math.min(start + env.CT_BATCH_SIZE - 1, treeSize - 1);

        const response = await this.getEntries(l.url, start, end);
        const entries = response.entries ?? [];

        if (entries.length === 0) {
          await sleep(env.CT_POLL_INTERVAL_MS, this.controller.signal);
          continue;
        }

        const discovered = await this.processEntries(entries, logCtx);

        // Logs may return fewer entries than requested — advance by what we
        // actually got, never by what we asked for, or we silently skip certs.
        await db
          .update(ctLogState)
          .set({
            nextIndex: start + entries.length,
            lastEventAt: new Date(),
            entriesProcessed: raw`${ctLogState.entriesProcessed} + ${entries.length}`,
            consecutiveFailures: 0,
            lastError: null,
            updatedAt: new Date(),
          })
          .where(eq(ctLogState.logUrl, l.url));

        this.lastEventAt = new Date();
        this.entriesProcessed += entries.length;
        this.apexesDiscovered += discovered;
      } catch (err) {
        if (!this.running) return;
        const message = err instanceof Error ? err.message : String(err);

        // A 429 is normal traffic shaping, not a fault. Back off quietly and
        // do not count it toward the failure streak, or a busy log would look
        // broken on the health endpoint.
        if (err instanceof HttpError && err.statusCode === 429) {
          this.throttled += 1;
          log.debug('ct log throttled us; slowing down', logCtx);
          try {
            await sleep(2_000 + Math.random() * 3_000, this.controller.signal);
          } catch {
            return;
          }
          continue;
        }

        const updated = await db
          .update(ctLogState)
          .set({
            consecutiveFailures: raw`${ctLogState.consecutiveFailures} + 1`,
            lastError: message,
            lastErrorAt: new Date(),
            updatedAt: new Date(),
          })
          .where(eq(ctLogState.logUrl, l.url))
          .returning({ failures: ctLogState.consecutiveFailures });

        const failures = updated[0]?.failures ?? 1;
        const delay = backoffDelay(failures, { baseMs: 2_000, maxMs: 300_000 });
        log.warn('ct poll failed; backing off', { ...logCtx, failures, delay_ms: delay, error: message });

        try {
          await sleep(delay, this.controller.signal);
        } catch {
          return; // aborted
        }
      }
    }
  }

  /**
   * Turn a batch of CT entries into domain candidates.
   * Returns how many new apexes were written.
   */
  private async processEntries(
    entries: { leaf_input: string }[],
    logCtx: Record<string, unknown>,
  ): Promise<number> {
    const candidates = new Map<string, { apex: string; tld: string; apexLevel: boolean }>();
    let parseErrors = 0;

    for (const entry of entries) {
      const { names, error } = dnsNamesFromLeafInput(entry.leaf_input);
      if (error) {
        parseErrors += 1;
        continue;
      }
      // One cert covers example.com + www.example.com + wildcards; they collapse.
      for (const result of apexesFromSans(names)) {
        const existing = candidates.get(result.apex);
        // A cert naming the apex itself is stronger evidence of a new site than
        // one naming only a deep subdomain.
        const apexLevel = names.some((n) => isApexLevelName(n));
        if (!existing) {
          candidates.set(result.apex, { ...result, apexLevel });
        } else if (apexLevel) {
          existing.apexLevel = true;
        }
      }
    }

    if (parseErrors > 0) {
      log.debug('ct entries failed to parse', { ...logCtx, parse_errors: parseErrors });
    }

    // Cheap in-process dedupe before any database round-trip.
    const fresh = this.deduper.filter([...candidates.keys()]);
    if (fresh.length === 0) return 0;

    const rows = fresh.map((apex) => candidates.get(apex)!);

    // CT tells us a cert exists, not that the domain is new. The row is a
    // candidate: no registration date is claimed here.
    const inserted = await db
      .insert(domains)
      .values(
        rows.map((r) => ({
          apex: r.apex,
          tld: r.tld,
          source: 'ct_log' as const,
          status: 'discovered' as const,
          ctHitCount: 1,
        })),
      )
      .onConflictDoUpdate({
        target: domains.apex,
        set: {
          lastSeenAt: raw`now()`,
          updatedAt: raw`now()`,
          ctHitCount: raw`${domains.ctHitCount} + 1`,
        },
      })
      .returning({ id: domains.id });

    return inserted.length;
  }
}

export const ctPoller = new CtPoller();
