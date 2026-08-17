import { eq, desc } from 'drizzle-orm';
import { withApiAuth } from '@/api/handler';
import { queryDomain } from '@/api/serialize';
import { db, domainDns, domainHttp, domainRdap, domainScores } from '@/db';
import { extractApex } from '@/ingest/apex';

/**
 * GET /api/v1/domains/:domain
 *
 * The full enriched record, plus the observation history that produced it.
 * `?trail=1` includes the enrichment trail — every DNS, HTTP, RDAP and score
 * observation with its timestamp — which is what answers "where did this field
 * come from?" (spec §10).
 *
 * The top-level object stays flat and identical in shape to a row from the list
 * endpoint; the trail is a sibling key, so a Clay column reading the flat fields
 * is unaffected by asking for it.
 */

export const dynamic = 'force-dynamic';

export const GET = withApiAuth(async ({ url, request }) => {
  const segments = new URL(request.url).pathname.split('/');
  const raw = decodeURIComponent(segments[segments.length - 1] ?? '');

  const parsed = extractApex(raw);
  if (!parsed) {
    return {
      body: { error: 'invalid_domain', message: `"${raw}" is not a valid domain.` },
      status: 400,
    };
  }

  const domain = await queryDomain(parsed.apex);
  if (!domain) {
    // A suppressed domain is indistinguishable from an unknown one here, which
    // is the intended behaviour: an opt-out should not be discoverable.
    return {
      body: { error: 'not_found', message: `No record for ${parsed.apex}.` },
      status: 404,
    };
  }

  if (!url.searchParams.get('trail')) {
    return { body: { data: domain }, rowsReturned: 1 };
  }

  const [dnsHistory, httpHistory, rdapHistory, scoreHistory] = await Promise.all([
    db
      .select({
        resolved_at: domainDns.resolvedAt,
        a_records: domainDns.aRecords,
        mx_records: domainDns.mxRecords,
        ns_records: domainDns.nsRecords,
        mx_provider: domainDns.mxProvider,
        ns_changed: domainDns.nsChanged,
      })
      .from(domainDns)
      .where(eq(domainDns.apex, parsed.apex))
      .orderBy(desc(domainDns.resolvedAt))
      .limit(20),
    db
      .select({
        probed_at: domainHttp.probedAt,
        status_code: domainHttp.statusCode,
        final_url: domainHttp.finalUrl,
        title: domainHttp.title,
        is_parked: domainHttp.isParked,
        parking_vendor: domainHttp.parkingVendor,
        parking_reason: domainHttp.parkingReason,
        robots_allowed: domainHttp.robotsAllowed,
        tech: domainHttp.tech,
      })
      .from(domainHttp)
      .where(eq(domainHttp.apex, parsed.apex))
      .orderBy(desc(domainHttp.probedAt))
      .limit(20),
    db
      .select({
        fetched_at: domainRdap.fetchedAt,
        registrar: domainRdap.registrar,
        created_date: domainRdap.createdDate,
        statuses: domainRdap.statuses,
        had_redactions: domainRdap.hadRedactions,
        rdap_server: domainRdap.rdapServer,
      })
      .from(domainRdap)
      .where(eq(domainRdap.apex, parsed.apex))
      .orderBy(desc(domainRdap.fetchedAt))
      .limit(20),
    db
      .select({
        scored_at: domainScores.scoredAt,
        score: domainScores.score,
        tier: domainScores.tier,
        reason: domainScores.reason,
        rules_verdict: domainScores.rulesVerdict,
        rules_kill_reason: domainScores.rulesKillReason,
        classifier_reason: domainScores.classifierReason,
        scoring_version: domainScores.scoringVersion,
        model_version: domainScores.modelVersion,
      })
      .from(domainScores)
      .where(eq(domainScores.apex, parsed.apex))
      .orderBy(desc(domainScores.scoredAt))
      .limit(20),
  ]);

  return {
    body: {
      data: domain,
      trail: {
        dns: dnsHistory,
        http: httpHistory,
        rdap: rdapHistory,
        scores: scoreHistory,
      },
    },
    rowsReturned: 1,
  };
});

export const runtime = 'nodejs';
