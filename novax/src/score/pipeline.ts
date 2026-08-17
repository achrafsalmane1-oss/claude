import { eq, and, inArray, sql as raw } from 'drizzle-orm';
import {
  db,
  domains,
  domainDns,
  domainHttp,
  domainRdap,
  domainScores,
  companies,
} from '@/db';
import { env, SCORING_VERSION } from '@/config/env';
import { createLogger } from '@/lib/logger';
import { recordCost } from '@/enrich/pipeline';
import { applyRules, type RulesInput, type RulesVerdict } from './rules';
import { classifyBatch, type ClassifierInput, type Classification } from './classifier';
import { computeScore } from './composite';

/**
 * Scoring orchestration (spec §7).
 *
 *   rules layer (free, runs on everything)
 *        │ most domains die here, before any LLM cost
 *        ▼
 *   classifier (batched LLM, survivors only)
 *        │
 *        ▼
 *   composite 0-100 + tier + reason  →  domain_scores, companies
 */

const log = createLogger('score.pipeline');

/**
 * Estimated classifier cost per domain in micro-dollars, for the cost ledger.
 *
 * ~1,500 input + ~150 output tokens. At Claude Opus 5 list price ($5/MTok in,
 * $25/MTok out) that is 7,500 + 3,750 = 11,250 micro-USD... which is why we use
 * the Batch API (50% off) and cache the system prefix. The figure below is the
 * batched, cache-discounted estimate. Adjust if you change CLASSIFIER_MODEL.
 */
const CLASSIFIER_COST_MICRO_USD = 5_600;

/** Everything the rules layer needs, assembled in one query. */
export async function loadRulesInputs(apexes: string[]): Promise<RulesInput[]> {
  if (apexes.length === 0) return [];

  const rows = await db
    .select({
      apex: domains.apex,
      tld: domains.tld,
      source: domains.source,
      ctHitCount: domains.ctHitCount,
      firstSeenAt: domains.firstSeenAt,
      registrationDate: domains.registrationDate,

      aRecords: domainDns.aRecords,
      mxRecords: domainDns.mxRecords,
      nsRecords: domainDns.nsRecords,
      mxProvider: domainDns.mxProvider,
      mxProviderKind: domainDns.mxProviderKind,
      hasSpf: domainDns.hasSpf,
      hasDmarc: domainDns.hasDmarc,

      httpStatus: domainHttp.statusCode,
      isParked: domainHttp.isParked,
      parkingVendor: domainHttp.parkingVendor,
      title: domainHttp.title,
      metaDescription: domainHttp.metaDescription,
      bodySnippet: domainHttp.bodySnippet,
      tech: domainHttp.tech,
      redirectedOffDomain: domainHttp.redirectedOffDomain,
      robotsAllowed: domainHttp.robotsAllowed,

      registrar: domainRdap.registrar,
    })
    .from(domains)
    .leftJoin(domainDns, and(eq(domainDns.apex, domains.apex), eq(domainDns.isCurrent, true)))
    .leftJoin(domainHttp, and(eq(domainHttp.apex, domains.apex), eq(domainHttp.isCurrent, true)))
    .leftJoin(domainRdap, and(eq(domainRdap.apex, domains.apex), eq(domainRdap.isCurrent, true)))
    .where(inArray(domains.apex, apexes));

  return rows.map((r) => ({
    apex: r.apex,
    tld: r.tld,
    hasA: (r.aRecords ?? []).length > 0,
    hasMx: (r.mxRecords ?? []).length > 0,
    mxProvider: r.mxProvider ?? null,
    mxProviderKind: r.mxProviderKind ?? null,
    hasSpf: r.hasSpf ?? false,
    hasDmarc: r.hasDmarc ?? false,
    nsProviders: r.nsRecords ?? [],
    httpStatus: r.httpStatus ?? null,
    isParked: r.isParked ?? false,
    parkingVendor: r.parkingVendor ?? null,
    title: r.title ?? null,
    metaDescription: r.metaDescription ?? null,
    bodySnippet: r.bodySnippet ?? null,
    tech: r.tech ?? [],
    redirectedOffDomain: r.redirectedOffDomain ?? false,
    robotsAllowed: r.robotsAllowed ?? true,
    registrar: r.registrar ?? null,
    registrationDate: r.registrationDate ?? null,
    source: r.source,
    ctHitCount: r.ctHitCount,
    firstSeenAt: r.firstSeenAt,
  }));
}

/** Persist one score, retiring any previous current score for the apex. */
async function saveScore(
  apex: string,
  verdict: RulesVerdict,
  classification: Classification | null,
  mxProvider: string | null,
): Promise<{ score: number; tier: string }> {
  const composite = computeScore({ verdict, classification, mxProvider });

  await db
    .update(domainScores)
    .set({ isCurrent: false })
    .where(and(eq(domainScores.apex, apex), eq(domainScores.isCurrent, true)));

  await db.insert(domainScores).values({
    apex,
    score: composite.score,
    tier: composite.tier,
    reason: composite.reason,
    rulesVerdict: verdict.verdict,
    rulesKillReason: verdict.killReason,
    rulesSignals: {
      ...verdict.signals,
      // Dates do not survive jsonb round-tripping as Date objects.
      components: composite.components,
    },
    classifierRan: classification !== null,
    isRealBusiness: classification?.isRealBusiness ?? null,
    category: classification?.category ?? null,
    stageGuess: classification?.stageGuess ?? null,
    confidence: classification?.confidence ?? null,
    classifierReason: classification?.reason ?? null,
    modelVersion: classification ? env.CLASSIFIER_MODEL : null,
    scoringVersion: SCORING_VERSION,
    isCurrent: true,
  });

  await db
    .update(domains)
    .set({
      status: verdict.verdict === 'kill' ? 'rejected' : 'scored',
      updatedAt: new Date(),
    })
    .where(eq(domains.apex, apex));

  return { score: composite.score, tier: composite.tier };
}

/**
 * Resolve the company record for a scored domain.
 *
 * Company-level only: name, description, category, country, website. No
 * personal contact data, per spec §10 — we sell the company signal, not people.
 */
async function upsertCompany(
  apex: string,
  classification: Classification,
  details: { title: string | null; metaDescription: string | null; country: string | null },
): Promise<void> {
  // Titles routinely carry a tagline after a separator; the first segment is
  // almost always the name.
  const name = details.title
    ? details.title.split(/\s+[|\-–—·]\s+/)[0]?.trim().slice(0, 200) || null
    : null;

  await db
    .insert(companies)
    .values({
      apex,
      name,
      description: details.metaDescription?.slice(0, 1000) ?? classification.reason.slice(0, 1000),
      category: classification.category,
      country: details.country,
      website: `https://${apex}`,
      confidence: classification.confidence,
      fieldSources: {
        name: 'http_title',
        description: details.metaDescription ? 'http_meta_description' : 'classifier',
        category: 'classifier',
        country: details.country ? 'rdap' : 'none',
        website: 'derived',
      },
    })
    .onConflictDoUpdate({
      target: companies.apex,
      set: {
        name,
        description: details.metaDescription?.slice(0, 1000) ?? classification.reason.slice(0, 1000),
        category: classification.category,
        country: details.country,
        confidence: classification.confidence,
        updatedAt: new Date(),
      },
    });
}

export interface ScoringRunResult {
  scored: number;
  killedByRules: number;
  sentToClassifier: number;
  classifiedReal: number;
  byTier: Record<string, number>;
}

/**
 * Score a set of domains end to end.
 *
 * The rules layer runs first and its kills are written immediately — that is
 * what keeps the LLM bill proportional to survivors rather than to volume.
 */
export async function runScoring(
  apexes: string[],
  options: { useClassifier?: boolean } = {},
): Promise<ScoringRunResult> {
  const useClassifier = options.useClassifier ?? (env.CLASSIFIER_ENABLED && Boolean(env.ANTHROPIC_API_KEY));

  const inputs = await loadRulesInputs(apexes);
  if (inputs.length === 0) {
    return { scored: 0, killedByRules: 0, sentToClassifier: 0, classifiedReal: 0, byTier: {} };
  }

  // --- Layer 1: rules -----------------------------------------------------
  const verdicts = new Map<string, RulesVerdict>();
  const inputByApex = new Map(inputs.map((i) => [i.apex, i]));
  for (const input of inputs) verdicts.set(input.apex, applyRules(input));

  const killed = inputs.filter((i) => verdicts.get(i.apex)!.verdict === 'kill');
  const survivors = inputs.filter((i) => verdicts.get(i.apex)!.verdict === 'pass');

  log.info('rules layer', {
    in: inputs.length,
    killed: killed.length,
    survived: survivors.length,
    kill_rate: (killed.length / inputs.length).toFixed(3),
    kill_reasons: killed.reduce<Record<string, number>>((acc, i) => {
      const reason = verdicts.get(i.apex)!.killReason ?? 'unknown';
      acc[reason] = (acc[reason] ?? 0) + 1;
      return acc;
    }, {}),
  });

  const byTier: Record<string, number> = {};
  const record = (tier: string) => {
    byTier[tier] = (byTier[tier] ?? 0) + 1;
  };

  // Write the kills straight away; no LLM cost was incurred for any of them.
  for (const input of killed) {
    const result = await saveScore(input.apex, verdicts.get(input.apex)!, null, null);
    record(result.tier);
  }

  // --- Layer 2: classifier (survivors only) -------------------------------
  let classifications = new Map<string, Classification>();
  const toClassify = survivors.slice(0, env.CLASSIFIER_MAX_PER_RUN);

  if (useClassifier && toClassify.length > 0) {
    const classifierInputs: ClassifierInput[] = toClassify.map((i) => ({
      apex: i.apex,
      tld: i.tld,
      title: i.title,
      metaDescription: i.metaDescription,
      bodySnippet: i.bodySnippet,
      mxProvider: i.mxProvider,
      tech: i.tech,
      registrar: i.registrar,
      country: null,
    }));

    const batch = await classifyBatch(classifierInputs);
    classifications = batch.results;

    for (const input of toClassify) {
      await recordCost(input.apex, 'classifier', CLASSIFIER_COST_MICRO_USD, {
        model: env.CLASSIFIER_MODEL,
        batch_id: batch.batchId,
      });
    }
  } else if (toClassify.length > 0) {
    log.warn('classifier disabled; scoring on rules signals alone', { survivors: toClassify.length });
  }

  // --- Composite + persist ------------------------------------------------
  let classifiedReal = 0;
  for (const input of survivors) {
    const classification = classifications.get(input.apex) ?? null;
    if (classification?.isRealBusiness) classifiedReal += 1;

    const result = await saveScore(
      input.apex,
      verdicts.get(input.apex)!,
      classification,
      input.mxProvider,
    );
    record(result.tier);

    if (classification?.isRealBusiness) {
      const details = inputByApex.get(input.apex)!;
      await upsertCompany(input.apex, classification, {
        title: details.title,
        metaDescription: details.metaDescription,
        country: null,
      });
    }
  }

  const result: ScoringRunResult = {
    scored: inputs.length,
    killedByRules: killed.length,
    sentToClassifier: useClassifier ? toClassify.length : 0,
    classifiedReal,
    byTier,
  };

  log.info('scoring run complete', { ...result, by_tier: byTier });
  return result;
}

/** Claim enriched domains that have no current score. */
export async function claimDomainsForScoring(limit: number): Promise<string[]> {
  const rows = await db.execute<{ apex: string }>(raw`
    select d.apex
      from domains d
      left join domain_scores s on s.apex = d.apex and s.is_current
     where d.status = 'enriched'
       and d.is_suppressed = false
       and s.id is null
     order by d.first_seen_at
     limit ${limit}
  `);
  return [...rows].map((r) => r.apex);
}
