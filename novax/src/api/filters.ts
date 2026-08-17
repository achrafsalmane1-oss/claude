import { z } from 'zod';
import { and, eq, gte, lte, inArray, ilike, or, lt, desc, type SQL, sql as raw } from 'drizzle-orm';
import { domains, domainDns, domainHttp, domainRdap, domainScores, companies } from '@/db';
import { applySuppression } from '@/compliance/suppression';

/**
 * Query parameters → SQL.
 *
 * Every filter the spec names in §8 (date range, TLD, country, MX provider,
 * score threshold, category, tech) plus the handful that fall out for free.
 *
 * All of it goes through `applySuppression`, which is the only way a query in
 * this codebase is allowed to read scored domains.
 */

export const filterSchema = z.object({
  // --- Date range (on first_seen_at, the "when did we find it" axis) -------
  from: z.string().optional(),
  to: z.string().optional(),
  /** Convenience: domains first seen in the last N days. */
  days: z.coerce.number().int().min(1).max(365).optional(),

  // --- Registration date, which is a different axis from discovery ---------
  registered_after: z.string().optional(),
  registered_before: z.string().optional(),

  // --- Categorical ---------------------------------------------------------
  tld: z.string().optional(),
  country: z.string().optional(),
  mx_provider: z.string().optional(),
  category: z.string().optional(),
  tech: z.string().optional(),
  registrar: z.string().optional(),
  tier: z.enum(['hot', 'warm', 'cold', 'junk']).optional(),
  source: z.enum(['ct_log', 'nrd_feed', 'czds', 'manual']).optional(),

  // --- Numeric -------------------------------------------------------------
  min_score: z.coerce.number().int().min(0).max(100).optional(),
  max_score: z.coerce.number().int().min(0).max(100).optional(),
  min_confidence: z.coerce.number().min(0).max(1).optional(),

  // --- Boolean -------------------------------------------------------------
  has_business_email: z.enum(['true', 'false']).optional(),
  is_real_business: z.enum(['true', 'false']).optional(),

  // --- Search --------------------------------------------------------------
  q: z.string().max(200).optional(),

  // --- Pagination ----------------------------------------------------------
  limit: z.coerce.number().int().min(1).max(1000).default(100),
  /** Opaque keyset cursor from the previous page. */
  cursor: z.string().optional(),
});

export type DomainFilters = z.infer<typeof filterSchema>;

export function parseFilters(params: URLSearchParams | Record<string, unknown>): DomainFilters {
  const raw =
    params instanceof URLSearchParams ? Object.fromEntries(params.entries()) : params;
  // Drop empty strings so `?tld=` does not become a filter on the empty string.
  const cleaned = Object.fromEntries(
    Object.entries(raw).filter(([, v]) => v !== '' && v !== null && v !== undefined),
  );
  return filterSchema.parse(cleaned);
}

/** Comma-separated values become an IN clause: `?tld=com,io,ai`. */
function list(value: string): string[] {
  return value
    .split(',')
    .map((v) => v.trim().toLowerCase())
    .filter(Boolean);
}

function parseDate(value: string): Date | null {
  const d = new Date(value.length === 10 ? `${value}T00:00:00Z` : value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/**
 * Keyset cursor.
 *
 * Encodes the sort key of the last row seen. Keyset rather than OFFSET because
 * the spec demands sub-2-second responses and `OFFSET 50000` on a table growing
 * by 300k rows a day is not that.
 */
export interface Cursor {
  score: number;
  id: number;
}

export function encodeCursor(c: Cursor): string {
  return Buffer.from(`${c.score}:${c.id}`, 'utf8').toString('base64url');
}

export function decodeCursor(value: string): Cursor | null {
  try {
    const [score, id] = Buffer.from(value, 'base64url').toString('utf8').split(':');
    const parsed = { score: Number(score), id: Number(id) };
    if (!Number.isFinite(parsed.score) || !Number.isFinite(parsed.id)) return null;
    return parsed;
  } catch {
    return null;
  }
}

/**
 * Build the WHERE clause.
 *
 * Note the first condition is always the suppression gate — see
 * `src/compliance/suppression.ts` for why that is not optional.
 */
export function buildWhere(filters: DomainFilters): SQL {
  const conditions: (SQL | undefined)[] = [];

  // --- Discovery date ---
  if (filters.days !== undefined) {
    conditions.push(gte(domains.firstSeenAt, new Date(Date.now() - filters.days * 86_400_000)));
  }
  if (filters.from) {
    const d = parseDate(filters.from);
    if (d) conditions.push(gte(domains.firstSeenAt, d));
  }
  if (filters.to) {
    const d = parseDate(filters.to);
    if (d) conditions.push(lte(domains.firstSeenAt, d));
  }

  // --- Registration date ---
  if (filters.registered_after) {
    const d = parseDate(filters.registered_after);
    if (d) conditions.push(gte(domains.registrationDate, d));
  }
  if (filters.registered_before) {
    const d = parseDate(filters.registered_before);
    if (d) conditions.push(lte(domains.registrationDate, d));
  }

  // --- Categorical ---
  if (filters.tld) conditions.push(inArray(domains.tld, list(filters.tld)));
  if (filters.source) conditions.push(eq(domains.source, filters.source));
  if (filters.tier) conditions.push(eq(domainScores.tier, filters.tier));

  if (filters.category) {
    conditions.push(inArray(domainScores.category, list(filters.category)));
  }

  if (filters.country) {
    // Country can come from RDAP or from the resolved company record.
    const countries = list(filters.country).map((c) => c.toUpperCase());
    conditions.push(
      or(
        inArray(raw`upper(${domainRdap.registrantCountry})`, countries),
        inArray(raw`upper(${companies.country})`, countries),
      ),
    );
  }

  if (filters.mx_provider) {
    const providers = list(filters.mx_provider);
    // Match the provider name or the kind, so `?mx_provider=business` works as
    // a shorthand for "any business email provider".
    conditions.push(
      or(
        inArray(raw`lower(${domainDns.mxProvider})`, providers),
        inArray(raw`lower(${domainDns.mxProviderKind})`, providers),
      ),
    );
  }

  if (filters.tech) {
    // `tech` is a jsonb array of slugs; `?tech=shopify,webflow` matches any.
    const techs = list(filters.tech);
    conditions.push(raw`${domainHttp.tech} ?| ${techs}`);
  }

  if (filters.registrar) {
    conditions.push(ilike(domainRdap.registrar, `%${filters.registrar}%`));
  }

  // --- Numeric ---
  if (filters.min_score !== undefined) conditions.push(gte(domainScores.score, filters.min_score));
  if (filters.max_score !== undefined) conditions.push(lte(domainScores.score, filters.max_score));
  if (filters.min_confidence !== undefined) {
    conditions.push(gte(domainScores.confidence, filters.min_confidence));
  }

  // --- Boolean ---
  if (filters.has_business_email !== undefined) {
    const wants = filters.has_business_email === 'true';
    const isBusiness = inArray(domainDns.mxProviderKind, ['business', 'security']);
    conditions.push(wants ? isBusiness : raw`not (${isBusiness})`);
  }
  if (filters.is_real_business !== undefined) {
    conditions.push(eq(domainScores.isRealBusiness, filters.is_real_business === 'true'));
  }

  // --- Free text ---
  if (filters.q) {
    const needle = `%${filters.q.toLowerCase()}%`;
    conditions.push(
      or(
        ilike(domains.apex, needle),
        ilike(domainHttp.title, needle),
        ilike(domainHttp.metaDescription, needle),
        ilike(companies.name, needle),
      ),
    );
  }

  // --- Keyset pagination ---
  if (filters.cursor) {
    const cursor = decodeCursor(filters.cursor);
    if (cursor) {
      // Ordered by (score desc, id desc), so "after" means strictly lower.
      conditions.push(
        or(
          lt(domainScores.score, cursor.score),
          and(eq(domainScores.score, cursor.score), lt(domainScores.id, cursor.id)),
        ),
      );
    }
  }

  // The suppression gate is applied here and only here.
  return applySuppression(...conditions);
}

/** Stable ordering, matching the keyset cursor. */
export function orderBy() {
  return [desc(domainScores.score), desc(domainScores.id)];
}
