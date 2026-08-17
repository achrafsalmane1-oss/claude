import { eq, and } from 'drizzle-orm';
import { db, domainRdap, domains } from '@/db';
import { env } from '@/config/env';
import { fetchJson, HttpError } from '@/lib/http';
import { createLogger } from '@/lib/logger';
import { TokenBucket } from '@/lib/token-bucket';

/**
 * RDAP lookup (spec §6.4).
 *
 * Response shape verified live against `rdap.verisign.com` (via the rdap.org
 * redirect) on 2026-08-17:
 *
 *   { objectClassName, handle, ldhName, status: [...], entities: [...],
 *     events: [{eventAction: "registration"|"expiration"|"last changed", eventDate}],
 *     nameservers: [...], secureDNS, notices }
 *
 * The registrant's contact data was fully redacted in that response — the
 * registrar entity's vCard carried only `version` and `fn`. That is the normal
 * case, not the exception, so nothing downstream may depend on registrant
 * identity. This parser drops anything marked redacted before it can reach the
 * database (spec §10), and never attempts to work around redaction.
 *
 * The registration date is the one field here worth real money: it is what
 * turns a CT hit into a confirmed *new* registration.
 */

const log = createLogger('enrich.rdap');

// Registries rate-limit per source IP and will ban a hot caller.
const limiter = new TokenBucket(env.RDAP_RPS_PER_REGISTRY, env.RDAP_BURST_PER_REGISTRY);

// --- Bootstrap -------------------------------------------------------------

interface BootstrapFile {
  publication?: string;
  services?: [string[], string[]][];
}

interface BootstrapCache {
  /** TLD -> base RDAP URLs. */
  map: Map<string, string[]>;
  fetchedAt: number;
}

let bootstrapCache: BootstrapCache | null = null;
/**
 * In-flight fetch, so N concurrent lookups on a cold cache make one request to
 * IANA rather than N. Observed during the first live run: five workers each
 * fetched the bootstrap file simultaneously.
 */
let bootstrapInFlight: Promise<Map<string, string[]>> | null = null;
const BOOTSTRAP_TTL_MS = 24 * 3600 * 1000;

/**
 * IANA's bootstrap file maps each TLD to its authoritative RDAP server.
 * Going direct is both faster and politer than routing everything through
 * rdap.org, which is a redirector we would otherwise be hammering.
 */
export async function loadBootstrap(force = false): Promise<Map<string, string[]>> {
  if (!force && bootstrapCache && Date.now() - bootstrapCache.fetchedAt < BOOTSTRAP_TTL_MS) {
    return bootstrapCache.map;
  }
  if (!force && bootstrapInFlight) return bootstrapInFlight;

  bootstrapInFlight = (async () => {
    try {
      const file = await fetchJson<BootstrapFile>(env.RDAP_BOOTSTRAP_URL, { timeoutMs: 30_000 });
      const map = new Map<string, string[]>();

      for (const [tlds, urls] of file.services ?? []) {
        const normalised = urls.map((u) => (u.endsWith('/') ? u : `${u}/`));
        for (const tld of tlds) map.set(tld.toLowerCase(), normalised);
      }

      bootstrapCache = { map, fetchedAt: Date.now() };
      log.info('rdap bootstrap loaded', { tlds: map.size, publication: file.publication });
      return map;
    } finally {
      bootstrapInFlight = null;
    }
  })();

  return bootstrapInFlight;
}

/**
 * Find the RDAP base URL for a domain.
 * Walks from the most specific suffix down, so `example.co.uk` tries `co.uk`
 * before `uk`, then falls back to the rdap.org redirector.
 */
export async function rdapServerFor(apex: string): Promise<{ base: string; viaFallback: boolean }> {
  const map = await loadBootstrap().catch(() => new Map<string, string[]>());
  const labels = apex.split('.');

  for (let i = 1; i < labels.length; i++) {
    const suffix = labels.slice(i).join('.');
    const urls = map.get(suffix);
    if (urls?.[0]) {
      // Prefer https where the registry offers both.
      const https = urls.find((u) => u.startsWith('https://'));
      return { base: https ?? urls[0], viaFallback: false };
    }
  }

  return { base: `${env.RDAP_FALLBACK_URL}/`, viaFallback: true };
}

// --- Response parsing ------------------------------------------------------

interface RdapEvent {
  eventAction?: string;
  eventDate?: string;
}

interface RdapEntity {
  roles?: string[];
  handle?: string;
  publicIds?: { type?: string; identifier?: string }[];
  vcardArray?: unknown;
  remarks?: { title?: string; type?: string; description?: string[] }[];
  entities?: RdapEntity[];
}

interface RdapResponse {
  ldhName?: string;
  handle?: string;
  status?: string[];
  events?: RdapEvent[];
  entities?: RdapEntity[];
  nameservers?: { ldhName?: string }[];
  remarks?: { title?: string; type?: string; description?: string[] }[];
  redacted?: { name?: { type?: string; description?: string } }[];
}

export interface RdapParseResult {
  registrar: string | null;
  registrarIanaId: string | null;
  createdDate: Date | null;
  expiresDate: Date | null;
  lastChangedDate: Date | null;
  statuses: string[];
  nameservers: string[];
  registrantCountry: string | null;
  registrantState: string | null;
  hadRedactions: boolean;
}

function parseDate(value: string | undefined): Date | null {
  if (!value) return null;
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/**
 * Pull a field out of a jCard (RFC 7095) vCard array.
 * Shape: ["vcard", [["version",{},"text","4.0"], ["fn",{},"text","Name"], ...]]
 */
function vcardField(vcardArray: unknown, field: string): string | null {
  if (!Array.isArray(vcardArray) || vcardArray.length < 2) return null;
  const entries = vcardArray[1];
  if (!Array.isArray(entries)) return null;

  for (const entry of entries) {
    if (!Array.isArray(entry) || entry.length < 4) continue;
    if (String(entry[0]).toLowerCase() !== field.toLowerCase()) continue;
    const value = entry[3];
    if (typeof value === 'string' && value.trim()) return value.trim();
  }
  return null;
}

/** Address components from a jCard `adr` entry: [pobox, ext, street, locality, region, code, country]. */
function vcardAddress(vcardArray: unknown): { country: string | null; state: string | null } {
  if (!Array.isArray(vcardArray) || vcardArray.length < 2) return { country: null, state: null };
  const entries = vcardArray[1];
  if (!Array.isArray(entries)) return { country: null, state: null };

  for (const entry of entries) {
    if (!Array.isArray(entry) || entry.length < 4) continue;
    if (String(entry[0]).toLowerCase() !== 'adr') continue;
    const value = entry[3];
    if (!Array.isArray(value)) continue;
    const state = typeof value[4] === 'string' && value[4].trim() ? value[4].trim() : null;
    const country = typeof value[6] === 'string' && value[6].trim() ? value[6].trim() : null;
    return { country, state };
  }
  return { country: null, state: null };
}

/**
 * True when a value is a redaction placeholder rather than real data.
 * Registries publish these in a dozen different spellings.
 */
export function isRedactedValue(value: string | null): boolean {
  if (!value) return true;
  const v = value.trim().toLowerCase();
  if (!v) return true;
  return (
    v.includes('redacted') ||
    v.includes('not disclosed') ||
    v.includes('withheld') ||
    v.includes('data protected') ||
    v.includes('privacy') ||
    v.includes('gdpr') ||
    v === 'n/a' ||
    v === 'not available' ||
    v === 'statutory masking enabled'
  );
}

export function parseRdapResponse(response: RdapResponse): RdapParseResult {
  const events = response.events ?? [];
  const findEvent = (action: string) =>
    parseDate(events.find((e) => e.eventAction?.toLowerCase() === action)?.eventDate);

  // --- Registrar ---
  const registrarEntity = (response.entities ?? []).find((e) =>
    e.roles?.some((r) => r.toLowerCase() === 'registrar'),
  );
  const registrarNameRaw = registrarEntity ? vcardField(registrarEntity.vcardArray, 'fn') : null;
  const registrar = isRedactedValue(registrarNameRaw) ? null : registrarNameRaw;
  const registrarIanaId =
    registrarEntity?.publicIds?.find((p) => p.type?.toLowerCase().includes('iana'))?.identifier ??
    registrarEntity?.handle ??
    null;

  // --- Registrant: country and state only, and only when not redacted ---
  // We deliberately never read `fn`, `email`, `tel` or the street lines here.
  const registrantEntity = (response.entities ?? []).find((e) =>
    e.roles?.some((r) => r.toLowerCase() === 'registrant'),
  );
  let registrantCountry: string | null = null;
  let registrantState: string | null = null;
  if (registrantEntity) {
    const address = vcardAddress(registrantEntity.vcardArray);
    registrantCountry = isRedactedValue(address.country) ? null : address.country;
    registrantState = isRedactedValue(address.state) ? null : address.state;
  }

  // --- Did the registry tell us it redacted things? ---
  const remarkText = [
    ...(response.remarks ?? []),
    ...(response.entities ?? []).flatMap((e) => e.remarks ?? []),
  ]
    .map((r) => `${r.title ?? ''} ${(r.description ?? []).join(' ')}`)
    .join(' ')
    .toLowerCase();

  const hadRedactions =
    (response.redacted?.length ?? 0) > 0 ||
    remarkText.includes('redacted') ||
    remarkText.includes('personal data') ||
    remarkText.includes('gdpr') ||
    // The near-universal case: a registrant entity exists but carries nothing.
    (registrantEntity !== undefined && registrantCountry === null && registrantState === null);

  return {
    registrar,
    registrarIanaId,
    createdDate: findEvent('registration'),
    expiresDate: findEvent('expiration'),
    lastChangedDate: findEvent('last changed'),
    statuses: (response.status ?? []).map((s) => s.toLowerCase()),
    nameservers: (response.nameservers ?? [])
      .map((n) => n.ldhName?.toLowerCase().replace(/\.$/, ''))
      .filter((n): n is string => Boolean(n)),
    registrantCountry,
    registrantState,
    hadRedactions,
  };
}

// --- Lookup ---------------------------------------------------------------

export interface RdapLookupResult extends RdapParseResult {
  apex: string;
  rdapServer: string | null;
  error?: string;
}

export async function lookupRdap(apex: string): Promise<RdapLookupResult> {
  const empty: RdapLookupResult = {
    apex,
    registrar: null,
    registrarIanaId: null,
    createdDate: null,
    expiresDate: null,
    lastChangedDate: null,
    statuses: [],
    nameservers: [],
    registrantCountry: null,
    registrantState: null,
    hadRedactions: false,
    rdapServer: null,
  };

  const { base } = await rdapServerFor(apex);
  const registryKey = new URL(base).host;

  // Politeness, per registry rather than globally.
  await limiter.acquire(registryKey);

  const url = `${base}domain/${encodeURIComponent(apex)}`;

  try {
    const response = await fetchJson<RdapResponse>(url, {
      timeoutMs: env.RDAP_TIMEOUT_MS,
      headers: { accept: 'application/rdap+json, application/json' },
      maxRedirects: 3,
    });
    return { ...empty, ...parseRdapResponse(response), rdapServer: registryKey };
  } catch (err) {
    // 404 is a real answer: the registry has no record. Anything else is a fault.
    if (err instanceof HttpError && err.statusCode === 404) {
      return { ...empty, rdapServer: registryKey, error: 'not found in registry' };
    }
    log.debug('rdap lookup failed', { apex, server: registryKey, error: String(err) });
    return { ...empty, rdapServer: registryKey, error: String(err) };
  }
}

/**
 * Persist an RDAP observation and, when the registry gives a creation date,
 * promote it to the domain's registration date — RDAP is the authoritative
 * source and outranks the feed date.
 */
export async function saveRdapResult(result: RdapLookupResult): Promise<void> {
  await db
    .update(domainRdap)
    .set({ isCurrent: false })
    .where(and(eq(domainRdap.apex, result.apex), eq(domainRdap.isCurrent, true)));

  await db.insert(domainRdap).values({
    apex: result.apex,
    registrar: result.registrar,
    registrarIanaId: result.registrarIanaId,
    createdDate: result.createdDate,
    expiresDate: result.expiresDate,
    lastChangedDate: result.lastChangedDate,
    statuses: result.statuses,
    nameservers: result.nameservers,
    registrantCountry: result.registrantCountry,
    registrantState: result.registrantState,
    hadRedactions: result.hadRedactions,
    rdapServer: result.rdapServer,
    isCurrent: true,
    failureCount: result.error ? 1 : 0,
    lastError: result.error ?? null,
  });

  if (result.createdDate) {
    await db
      .update(domains)
      .set({
        registrationDate: result.createdDate,
        registrationDateSource: 'rdap',
        updatedAt: new Date(),
      })
      .where(eq(domains.apex, result.apex));
  }
}
