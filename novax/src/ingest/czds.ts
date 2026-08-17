import { gunzipSync } from 'fflate';
import { env } from '@/config/env';
import { fetchBuffer, fetchJson, HttpError } from '@/lib/http';
import { createLogger } from '@/lib/logger';
import { extractApex } from './apex';

/**
 * ICANN CZDS (Centralized Zone Data Service).
 *
 * Built, deliberately not scheduled. The spec calls this a phase-1 stretch and
 * explicitly not a v1 blocker: approval per-TLD takes days to weeks, and the
 * `.com` zone alone is multi-GB. This module is the request-and-diff tooling so
 * the upgrade is a config change, not a build.
 *
 * What CZDS gives you and does not: complete gTLD coverage, but only a daily
 * snapshot of *what exists*, with no ownership data and no registration dates.
 * "New today" therefore means "in today's zone and not yesterday's", which is
 * why the diff below is the actual product of this module.
 *
 * Note this is authenticated and unavailable without ICANN approval, so unlike
 * the NRD feed and the CT endpoints it could not be verified against the live
 * service during the build. The request shapes follow ICANN's published API
 * (`/api/authenticate` returns `{accessToken}`; `/czds/downloads/links` returns
 * a JSON array of zone URLs; each URL serves a gzipped zone file) and are
 * marked in PHASE-REPORTS.md as unverified.
 */

const log = createLogger('ingest.czds');

export interface CzdsCredentials {
  username: string;
  password: string;
}

function requireCredentials(): CzdsCredentials {
  if (!env.CZDS_USERNAME || !env.CZDS_PASSWORD) {
    throw new Error('CZDS_USERNAME and CZDS_PASSWORD must be set to use CZDS');
  }
  return { username: env.CZDS_USERNAME, password: env.CZDS_PASSWORD };
}

/** Exchange credentials for a bearer token. */
export async function authenticate(): Promise<string> {
  const creds = requireCredentials();
  const response = await fetchJson<{ accessToken?: string }>(env.CZDS_AUTH_URL, {
    method: 'POST',
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(creds),
    timeoutMs: 30_000,
  });
  if (!response.accessToken) throw new Error('CZDS authentication returned no accessToken');
  return response.accessToken;
}

/** Zone file download links this account is approved for. */
export async function listApprovedZones(token: string): Promise<string[]> {
  return fetchJson<string[]>(`${env.CZDS_BASE_URL}/czds/downloads/links`, {
    headers: { authorization: `Bearer ${token}` },
    timeoutMs: 60_000,
  });
}

/**
 * Parse a zone file into the set of apexes it delegates.
 *
 * A zone file is DNS master format. We care only about NS records at the second
 * level — their owner name is a registered domain. Every other record type
 * (A/AAAA glue, DS, SOA) is noise for this purpose, and taking NS owners rather
 * than every name is what stops glue records inflating the set.
 */
export function parseZoneFile(content: string): Set<string> {
  const apexes = new Set<string>();

  for (const line of content.split('\n')) {
    if (!line || line.startsWith(';')) continue;

    // Master format: <owner> <ttl> <class> <type> <rdata>, whitespace-separated.
    const fields = line.split(/\s+/).filter(Boolean);
    if (fields.length < 4) continue;

    // Find the record type; TTL and class are both optional in places.
    const typeIndex = fields.findIndex((f, i) => i > 0 && /^(NS|A|AAAA|DS|SOA|RRSIG|NSEC3?)$/i.test(f));
    if (typeIndex < 0) continue;
    if (fields[typeIndex]!.toUpperCase() !== 'NS') continue;

    const owner = fields[0]!.replace(/\.$/, '').toLowerCase();
    if (!owner) continue;

    const parsed = extractApex(owner);
    // Only keep names that are themselves the registrable apex — a zone file
    // contains delegations for subdomains too.
    if (parsed && parsed.apex === owner) apexes.add(owner);
  }

  return apexes;
}

/** Download and decompress one zone. */
export async function downloadZone(token: string, url: string): Promise<string> {
  log.info('czds zone download starting', { url });
  const { buffer, statusCode } = await fetchBuffer(url, {
    headers: { authorization: `Bearer ${token}` },
    timeoutMs: 1_800_000, // multi-GB files
    maxBytes: 8 * 1024 * 1024 * 1024,
  });
  if (statusCode !== 200) throw new HttpError(`CZDS zone download returned ${statusCode}`, statusCode);

  // Zone files are served gzipped.
  const decompressed = gunzipSync(new Uint8Array(buffer));
  log.info('czds zone downloaded', { url, compressed: buffer.length, decompressed: decompressed.length });
  return Buffer.from(decompressed).toString('utf8');
}

export interface ZoneDiff {
  added: string[];
  removed: string[];
  unchanged: number;
}

/**
 * Day-over-day diff. `added` is the newly-delegated set — the closest thing
 * CZDS gives to "newly registered".
 */
export function diffZones(previous: Set<string>, current: Set<string>): ZoneDiff {
  const added: string[] = [];
  const removed: string[] = [];
  let unchanged = 0;

  for (const apex of current) {
    if (previous.has(apex)) unchanged += 1;
    else added.push(apex);
  }
  for (const apex of previous) {
    if (!current.has(apex)) removed.push(apex);
  }

  return { added, removed, unchanged };
}
