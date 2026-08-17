import { eq, and } from 'drizzle-orm';
import {
  db,
  domains,
  domainDns,
  domainHttp,
  domainRdap,
  domainScores,
  companies,
} from '@/db';
import { buildWhere, orderBy, encodeCursor, type DomainFilters } from './filters';

/**
 * The response shape.
 *
 * **Flat, on purpose.** The distribution wedge (spec §8) is Clay's HTTP API
 * column, which maps JSON keys onto spreadsheet columns and handles nested
 * objects badly. `mx_provider` is a column a GTM person can use; `dns.mx.provider`
 * is a support ticket. So: one object per domain, every value a scalar, stable
 * snake_case keys, no nesting anywhere.
 *
 * Arrays are the one compromise — `tech` is genuinely multi-valued — so it is
 * also emitted pre-joined as `tech_list` for tools that cannot read an array.
 */

export interface FlatDomain {
  // --- Identity ---
  domain: string;
  tld: string;

  // --- Score: what a buyer sorts by ---
  score: number | null;
  tier: string | null;
  reason: string | null;

  // --- Company ---
  company_name: string | null;
  description: string | null;
  category: string | null;
  stage: string | null;
  country: string | null;
  website: string | null;
  confidence: number | null;
  is_real_business: boolean | null;

  // --- Signals ---
  mx_provider: string | null;
  mx_provider_kind: string | null;
  has_business_email: boolean;
  has_spf: boolean;
  has_dmarc: boolean;
  tech: string[];
  tech_list: string;
  page_title: string | null;
  meta_description: string | null;
  http_status: number | null;
  final_url: string | null;
  is_parked: boolean;

  // --- Registration ---
  registrar: string | null;
  registration_date: string | null;
  registration_date_source: string | null;
  expires_date: string | null;
  nameservers: string[];
  nameserver_list: string;

  // --- Provenance (spec §10: source and timestamp for every field group) ---
  source: string;
  first_seen_at: string;
  last_seen_at: string;
  dns_resolved_at: string | null;
  http_probed_at: string | null;
  rdap_fetched_at: string | null;
  scored_at: string | null;
  scoring_version: string | null;
  model_version: string | null;
}

function iso(value: Date | null | undefined): string | null {
  return value ? value.toISOString() : null;
}

/** The joined row shape every read path shares. */
const selection = {
  apex: domains.apex,
  tld: domains.tld,
  source: domains.source,
  firstSeenAt: domains.firstSeenAt,
  lastSeenAt: domains.lastSeenAt,
  registrationDate: domains.registrationDate,
  registrationDateSource: domains.registrationDateSource,

  score: domainScores.score,
  scoreId: domainScores.id,
  tier: domainScores.tier,
  reason: domainScores.reason,
  category: domainScores.category,
  stageGuess: domainScores.stageGuess,
  confidence: domainScores.confidence,
  isRealBusiness: domainScores.isRealBusiness,
  scoredAt: domainScores.scoredAt,
  scoringVersion: domainScores.scoringVersion,
  modelVersion: domainScores.modelVersion,

  companyName: companies.name,
  companyDescription: companies.description,
  companyCountry: companies.country,
  companyWebsite: companies.website,

  mxProvider: domainDns.mxProvider,
  mxProviderKind: domainDns.mxProviderKind,
  hasSpf: domainDns.hasSpf,
  hasDmarc: domainDns.hasDmarc,
  dnsResolvedAt: domainDns.resolvedAt,

  title: domainHttp.title,
  metaDescription: domainHttp.metaDescription,
  httpStatus: domainHttp.statusCode,
  finalUrl: domainHttp.finalUrl,
  tech: domainHttp.tech,
  isParked: domainHttp.isParked,
  httpProbedAt: domainHttp.probedAt,

  registrar: domainRdap.registrar,
  registrantCountry: domainRdap.registrantCountry,
  expiresDate: domainRdap.expiresDate,
  nameservers: domainRdap.nameservers,
  rdapFetchedAt: domainRdap.fetchedAt,
};

type Row = { [K in keyof typeof selection]: unknown };

export function toFlatDomain(r: Record<string, unknown>): FlatDomain {
  const tech = (r['tech'] as string[] | null) ?? [];
  const nameservers = (r['nameservers'] as string[] | null) ?? [];
  const mxKind = r['mxProviderKind'] as string | null;

  return {
    domain: r['apex'] as string,
    tld: r['tld'] as string,

    score: (r['score'] as number | null) ?? null,
    tier: (r['tier'] as string | null) ?? null,
    reason: (r['reason'] as string | null) ?? null,

    company_name: (r['companyName'] as string | null) ?? null,
    description: (r['companyDescription'] as string | null) ?? (r['metaDescription'] as string | null) ?? null,
    category: (r['category'] as string | null) ?? null,
    stage: (r['stageGuess'] as string | null) ?? null,
    country: ((r['companyCountry'] as string | null) ?? (r['registrantCountry'] as string | null)) ?? null,
    website: (r['companyWebsite'] as string | null) ?? `https://${r['apex'] as string}`,
    confidence: (r['confidence'] as number | null) ?? null,
    is_real_business: (r['isRealBusiness'] as boolean | null) ?? null,

    mx_provider: (r['mxProvider'] as string | null) ?? null,
    mx_provider_kind: mxKind,
    has_business_email: mxKind === 'business' || mxKind === 'security',
    has_spf: (r['hasSpf'] as boolean | null) ?? false,
    has_dmarc: (r['hasDmarc'] as boolean | null) ?? false,
    tech,
    tech_list: tech.join(', '),
    page_title: (r['title'] as string | null) ?? null,
    meta_description: (r['metaDescription'] as string | null) ?? null,
    http_status: (r['httpStatus'] as number | null) ?? null,
    final_url: (r['finalUrl'] as string | null) ?? null,
    is_parked: (r['isParked'] as boolean | null) ?? false,

    registrar: (r['registrar'] as string | null) ?? null,
    registration_date: iso(r['registrationDate'] as Date | null),
    registration_date_source: (r['registrationDateSource'] as string | null) ?? null,
    expires_date: iso(r['expiresDate'] as Date | null),
    nameservers,
    nameserver_list: nameservers.join(', '),

    source: r['source'] as string,
    first_seen_at: iso(r['firstSeenAt'] as Date)!,
    last_seen_at: iso(r['lastSeenAt'] as Date)!,
    dns_resolved_at: iso(r['dnsResolvedAt'] as Date | null),
    http_probed_at: iso(r['httpProbedAt'] as Date | null),
    rdap_fetched_at: iso(r['rdapFetchedAt'] as Date | null),
    scored_at: iso(r['scoredAt'] as Date | null),
    scoring_version: (r['scoringVersion'] as string | null) ?? null,
    model_version: (r['modelVersion'] as string | null) ?? null,
  };
}

export interface DomainQueryResult {
  domains: FlatDomain[];
  nextCursor: string | null;
  count: number;
}

/**
 * The one query every list endpoint uses.
 *
 * `inner join domain_scores` is deliberate: an unscored domain is not a product
 * of this system yet, and returning it would be returning raw feed data, which
 * is the commodity we are explicitly not selling.
 */
export async function queryDomains(filters: DomainFilters): Promise<DomainQueryResult> {
  const rows = await db
    .select(selection)
    .from(domains)
    .innerJoin(domainScores, and(eq(domainScores.apex, domains.apex), eq(domainScores.isCurrent, true)))
    .leftJoin(domainDns, and(eq(domainDns.apex, domains.apex), eq(domainDns.isCurrent, true)))
    .leftJoin(domainHttp, and(eq(domainHttp.apex, domains.apex), eq(domainHttp.isCurrent, true)))
    .leftJoin(domainRdap, and(eq(domainRdap.apex, domains.apex), eq(domainRdap.isCurrent, true)))
    .leftJoin(companies, eq(companies.apex, domains.apex))
    .where(buildWhere(filters))
    .orderBy(...orderBy())
    .limit(filters.limit);

  const flat = rows.map((r) => toFlatDomain(r as Record<string, unknown>));

  // A full page implies there may be more; a short page is definitively the end.
  const last = rows[rows.length - 1];
  const nextCursor =
    rows.length === filters.limit && last
      ? encodeCursor({ score: last.score as number, id: last.scoreId as number })
      : null;

  return { domains: flat, nextCursor, count: flat.length };
}

/** Single domain, with the full enrichment trail. */
export async function queryDomain(apex: string): Promise<FlatDomain | null> {
  const rows = await db
    .select(selection)
    .from(domains)
    .leftJoin(domainScores, and(eq(domainScores.apex, domains.apex), eq(domainScores.isCurrent, true)))
    .leftJoin(domainDns, and(eq(domainDns.apex, domains.apex), eq(domainDns.isCurrent, true)))
    .leftJoin(domainHttp, and(eq(domainHttp.apex, domains.apex), eq(domainHttp.isCurrent, true)))
    .leftJoin(domainRdap, and(eq(domainRdap.apex, domains.apex), eq(domainRdap.isCurrent, true)))
    .leftJoin(companies, eq(companies.apex, domains.apex))
    // Suppression applies to single lookups too, or the gate would have a hole
    // you could walk through by knowing the domain name.
    .where(and(eq(domains.apex, apex.toLowerCase()), eq(domains.isSuppressed, false)))
    .limit(1);

  const row = rows[0];
  return row ? toFlatDomain(row as Record<string, unknown>) : null;
}

/** CSV export. Arrays are joined; the array columns themselves are dropped. */
export function toCsv(rows: FlatDomain[]): string {
  if (rows.length === 0) return '';

  const columns = (Object.keys(rows[0]!) as (keyof FlatDomain)[]).filter(
    (k) => k !== 'tech' && k !== 'nameservers',
  );

  const escape = (value: unknown): string => {
    if (value === null || value === undefined) return '';
    const s = String(value);
    if (/[",\n\r]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
    return s;
  };

  const lines = [columns.join(',')];
  for (const row of rows) {
    lines.push(columns.map((c) => escape(row[c])).join(','));
  }
  return lines.join('\n');
}

export type { Row };
