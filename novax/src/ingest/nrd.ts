import { unzipSync } from 'fflate';
import { sql as raw } from 'drizzle-orm';
import { db, domains, feedRuns } from '@/db';
import { env } from '@/config/env';
import { fetchBuffer } from '@/lib/http';
import { createLogger } from '@/lib/logger';
import { extractApex } from './apex';

/**
 * Daily newly-registered-domain feed (whoisds).
 *
 * URL format, verified live on 2026-08-17 rather than recalled:
 *
 *   {base}/{base64("YYYY-MM-DD.zip") with trailing "=" padding stripped}/nrd
 *
 * The response is a ZIP containing a single `domain-names.txt`, one apex per
 * line. A real day is 250k-450k domains (2026-08-13 was 413,661).
 *
 * Free-tier caveat, observed live: some days return a suspiciously round file —
 * 2026-08-15 came back with exactly 70,000 lines. That is a truncated free-tier
 * export, not a quiet day. `NRD_MIN_EXPECTED_DOMAINS` catches it and the run is
 * recorded with a warning rather than being silently trusted.
 */

const log = createLogger('ingest.nrd');

export interface NrdParseResult {
  domains: { apex: string; tld: string }[];
  totalLines: number;
  skipped: number;
}

/** Build the download URL for a given YYYY-MM-DD. */
export function nrdUrlForDate(date: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(date)) {
    throw new Error(`invalid feed date "${date}", expected YYYY-MM-DD`);
  }
  // base64 of "YYYY-MM-DD.zip", '=' padding removed — matches the live service.
  const encoded = Buffer.from(`${date}.zip`, 'utf8').toString('base64').replace(/=+$/, '');
  return `${env.NRD_FEED_BASE_URL}/${encoded}/nrd`;
}

/** The most recent feed date that is reliably published, per NRD_LAG_DAYS. */
export function latestAvailableFeedDate(now = new Date()): string {
  const d = new Date(now.getTime() - env.NRD_LAG_DAYS * 86_400_000);
  return d.toISOString().slice(0, 10);
}

/**
 * Parse the ZIP into normalised apexes.
 *
 * Lines are bare domains. We still run each through the PSL rather than trusting
 * the feed's own idea of an apex, because the feed occasionally contains
 * subdomains and always contains CRLF line endings.
 */
export function parseNrdArchive(zipBuffer: Buffer): NrdParseResult {
  const files = unzipSync(new Uint8Array(zipBuffer));
  const names = Object.keys(files);

  // The archive has held exactly one `domain-names.txt`, but pick the largest
  // .txt rather than hardcoding the name in case they rename it.
  const txtName =
    names.find((n) => n.toLowerCase().endsWith('domain-names.txt')) ??
    names
      .filter((n) => n.toLowerCase().endsWith('.txt'))
      .sort((a, b) => (files[b]?.length ?? 0) - (files[a]?.length ?? 0))[0];

  if (!txtName) {
    throw new Error(`no .txt file in NRD archive; contents: ${names.join(', ') || '(empty)'}`);
  }

  const text = Buffer.from(files[txtName]!).toString('utf8');
  const lines = text.split('\n');

  const seen = new Map<string, { apex: string; tld: string }>();
  let skipped = 0;

  for (const line of lines) {
    // Feed uses CRLF; strip the carriage return and any stray whitespace.
    const trimmed = line.trim();
    if (!trimmed) continue;

    const result = extractApex(trimmed);
    if (!result) {
      skipped += 1;
      continue;
    }
    if (!seen.has(result.apex)) seen.set(result.apex, result);
  }

  return {
    domains: [...seen.values()],
    totalLines: lines.filter((l) => l.trim().length > 0).length,
    skipped,
  };
}

/**
 * Bulk insert, idempotently.
 *
 * `ON CONFLICT DO NOTHING` on the apex unique index is what makes re-running the
 * same day a no-op (spec §5a). An existing row has its `last_seen_at` refreshed
 * but keeps its original `first_seen_at` and source — a domain first seen in CT
 * and later confirmed by the feed is still first seen in CT.
 */
export async function insertDomains(
  rows: { apex: string; tld: string }[],
  opts: { source: 'nrd_feed' | 'ct_log' | 'czds'; registrationDate?: Date | null; chunkSize?: number },
): Promise<number> {
  if (rows.length === 0) return 0;
  const chunkSize = opts.chunkSize ?? 2_000;
  let inserted = 0;

  for (let i = 0; i < rows.length; i += chunkSize) {
    const chunk = rows.slice(i, i + chunkSize);
    const result = await db
      .insert(domains)
      .values(
        chunk.map((r) => ({
          apex: r.apex,
          tld: r.tld,
          source: opts.source,
          status: 'discovered' as const,
          ...(opts.registrationDate
            ? {
                registrationDate: opts.registrationDate,
                registrationDateSource: opts.source,
              }
            : {}),
        })),
      )
      .onConflictDoUpdate({
        target: domains.apex,
        set: {
          lastSeenAt: raw`now()`,
          updatedAt: raw`now()`,
          // Fill in the registration date only if we did not already know it —
          // the feed date is a weaker source than the RDAP creation event.
          registrationDate: raw`coalesce(${domains.registrationDate}, excluded.registration_date)`,
          registrationDateSource: raw`coalesce(${domains.registrationDateSource}, excluded.registration_date_source)`,
        },
      })
      // `returning` yields every *touched* row, inserted or updated. Postgres
      // sets xmax = 0 on a fresh insert, so this distinguishes the two — the
      // difference is exactly what makes a re-run visibly a no-op.
      .returning({ id: domains.id, wasInserted: raw<boolean>`(xmax = 0)` });

    inserted += result.filter((r) => r.wasInserted).length;
  }

  return inserted;
}

export interface NrdRunResult {
  date: string;
  domainsInFile: number;
  newDomains: number;
  skipped: number;
  bytes: number;
  warning?: string;
}

/** Download, parse and ingest one day of the feed. */
export async function ingestNrdDay(date: string): Promise<NrdRunResult> {
  const url = nrdUrlForDate(date);
  log.info('nrd download starting', { date, url });

  // Mark the run as started so a crash mid-download is visible in /health.
  await db
    .insert(feedRuns)
    .values({ feed: 'nrd', feedDate: date, status: 'running' })
    .onConflictDoUpdate({
      target: [feedRuns.feed, feedRuns.feedDate],
      set: { status: 'running', startedAt: raw`now()`, error: null, warning: null },
    });

  try {
    const { buffer, statusCode, headers } = await fetchBuffer(url, { timeoutMs: 180_000 });

    if (statusCode !== 200) {
      throw new Error(`feed returned HTTP ${statusCode}`);
    }
    // The service answers 200 with an HTML error page when a date is unavailable.
    const contentType = headers['content-type'] ?? '';
    if (contentType.includes('text/html')) {
      throw new Error(`feed returned HTML, not a ZIP (date ${date} probably not published yet)`);
    }

    const parsed = parseNrdArchive(buffer);

    let warning: string | undefined;
    if (parsed.domains.length < env.NRD_MIN_EXPECTED_DOMAINS) {
      warning =
        `only ${parsed.domains.length} domains (expected >= ${env.NRD_MIN_EXPECTED_DOMAINS}); ` +
        `the free tier serves truncated files on some days — treat this day as incomplete`;
      log.warn('nrd file looks truncated', { date, count: parsed.domains.length });
    }

    // The feed date is the registration date for these domains — that is what
    // the feed is. It is a weaker source than RDAP and is marked as such.
    const registrationDate = new Date(`${date}T00:00:00Z`);
    const newlyInserted = await insertDomains(parsed.domains, {
      source: 'nrd_feed',
      registrationDate,
    });

    await db
      .insert(feedRuns)
      .values({
        feed: 'nrd',
        feedDate: date,
        status: 'success',
        domainsInFile: parsed.domains.length,
        domainsInserted: newlyInserted,
        bytesDownloaded: buffer.length,
        warning: warning ?? null,
        finishedAt: new Date(),
      })
      .onConflictDoUpdate({
        target: [feedRuns.feed, feedRuns.feedDate],
        set: {
          status: 'success',
          domainsInFile: parsed.domains.length,
          domainsInserted: newlyInserted,
          bytesDownloaded: buffer.length,
          warning: warning ?? null,
          error: null,
          finishedAt: new Date(),
        },
      });

    log.info('nrd ingest complete', {
      date,
      in_file: parsed.domains.length,
      new_domains: newlyInserted,
      skipped: parsed.skipped,
      bytes: buffer.length,
    });

    return {
      date,
      domainsInFile: parsed.domains.length,
      newDomains: newlyInserted,
      skipped: parsed.skipped,
      bytes: buffer.length,
      ...(warning ? { warning } : {}),
    };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    await db
      .insert(feedRuns)
      .values({ feed: 'nrd', feedDate: date, status: 'failed', error: message, finishedAt: new Date() })
      .onConflictDoUpdate({
        target: [feedRuns.feed, feedRuns.feedDate],
        set: { status: 'failed', error: message, finishedAt: new Date() },
      });
    log.error('nrd ingest failed', err, { date });
    throw err;
  }
}
