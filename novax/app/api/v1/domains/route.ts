import { withApiAuth } from '@/api/handler';
import { parseFilters } from '@/api/filters';
import { queryDomains } from '@/api/serialize';

/**
 * GET /api/v1/domains
 *
 * The main endpoint, and the one designed to be pasted straight into a Clay
 * HTTP API column: flat JSON, one object per domain, stable snake_case keys.
 *
 * Filters (spec §8): from, to, days, registered_after, registered_before, tld,
 * country, mx_provider, category, tech, registrar, tier, source, min_score,
 * max_score, min_confidence, has_business_email, is_real_business, q.
 *
 * Comma-separate any categorical filter for an OR: `?tld=com,io&tech=shopify`.
 * Pagination is by keyset cursor, so deep pages stay fast.
 */

export const dynamic = 'force-dynamic';

export const GET = withApiAuth(async ({ url }) => {
  const filters = parseFilters(url.searchParams);
  const result = await queryDomains(filters);

  return {
    body: {
      data: result.domains,
      count: result.count,
      next_cursor: result.nextCursor,
      // Echo the filters back so a Clay user can see what actually applied.
      filters,
    },
    rowsReturned: result.count,
  };
});
