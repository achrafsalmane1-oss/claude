import { env } from '@/config/env';
import type { RulesVerdict } from './rules';
import type { Classification } from './classifier';
import type { ScoreTier } from '@/db/schema';

/**
 * The composite 0-100 score (spec §7).
 *
 * A transparent weighted sum, on purpose. The spec calls being able to tell a
 * user *why* a domain surfaced "a real differentiator over the black-box
 * incumbents", and you cannot explain a model you cannot read. Every component
 * below turns into a clause of the reason string.
 *
 * Weights are a starting point, not received wisdom. Change them, then run
 * `npm run eval` and see whether precision moved. That loop is the point.
 */

export interface ScoreComponent {
  label: string;
  points: number;
  /** Shown to the user as part of the reason. */
  detail: string;
}

export interface CompositeScore {
  score: number;
  tier: ScoreTier;
  reason: string;
  components: ScoreComponent[];
}

export const WEIGHTS = {
  /** Business email on a real provider: the strongest single cheap signal. */
  businessMx: 22,
  /** Mail authentication configured — someone who set up SPF/DMARC means it. */
  mailAuth: 6,
  /** A deliberately built site (Webflow, Shopify, a real CMS). */
  buildSignal: 12,
  /** Real page content, scaled by how much of it there is. */
  content: 16,
  /** TLD band. */
  tldHighTrust: 8,
  tldCcBusiness: 6,
  tldLowTrust: -10,
  /** The classifier's verdict, scaled by its own confidence. */
  classifierReal: 34,
  classifierNotReal: -45,
  /** Machine-generated-looking name. */
  randomNamePenalty: -18,
  /** Confirmed recent registration — this is what makes it *news*. */
  freshRegistration: 8,
} as const;

/** A domain the rules layer killed. Score 0, with the reason preserved. */
export function killedScore(verdict: RulesVerdict): CompositeScore {
  return {
    score: 0,
    tier: 'junk',
    reason: verdict.explanation,
    components: [{ label: 'rules_kill', points: 0, detail: verdict.explanation }],
  };
}

export function tierFor(score: number): ScoreTier {
  if (score >= env.SCORE_TIER_HOT) return 'hot';
  if (score >= env.SCORE_TIER_WARM) return 'warm';
  if (score >= env.SCORE_TIER_COLD) return 'cold';
  return 'junk';
}

export interface CompositeInput {
  verdict: RulesVerdict;
  classification: Classification | null;
  mxProvider: string | null;
}

export function computeScore(input: CompositeInput): CompositeScore {
  const { verdict, classification, mxProvider } = input;

  if (verdict.verdict === 'kill') return killedScore(verdict);

  const s = verdict.signals;
  const components: ScoreComponent[] = [];

  // Start at a neutral base so a domain with no signal either way lands mid-cold
  // rather than at zero — zero should mean "we have a reason to reject it".
  let score = 30;
  components.push({ label: 'base', points: 30, detail: 'passed the rules layer' });

  // --- Business email ------------------------------------------------------
  if (s.hasBusinessMx) {
    score += WEIGHTS.businessMx;
    components.push({
      label: 'business_mx',
      points: WEIGHTS.businessMx,
      detail: mxProvider
        ? `business email configured on ${mxProvider}`
        : 'business email configured',
    });
  }

  // Mail authentication only counts alongside actual mail: SPF on a domain with
  // no MX is a registrar default, not a decision someone made.
  if (s.hasMailAuth && s.hasBusinessMx) {
    score += WEIGHTS.mailAuth;
    components.push({
      label: 'mail_auth',
      points: WEIGHTS.mailAuth,
      detail: 'SPF/DMARC records published',
    });
  }

  // --- Build signal --------------------------------------------------------
  if (s.buildSignals.length > 0) {
    score += WEIGHTS.buildSignal;
    components.push({
      label: 'build_signal',
      points: WEIGHTS.buildSignal,
      detail: `site built with ${s.buildSignals.join(', ')}`,
    });
  }

  // --- Content, scaled -----------------------------------------------------
  if (s.hasRealContent) {
    // Full marks by ~1,500 characters; a one-paragraph landing page gets part.
    const fraction = Math.min(1, s.contentLength / 1_500);
    const points = Math.round(WEIGHTS.content * fraction);
    score += points;
    components.push({
      label: 'content',
      points,
      detail: `${s.contentLength} characters of page content`,
    });
  }

  // --- TLD band ------------------------------------------------------------
  if (s.tldBand === 'high_trust') {
    score += WEIGHTS.tldHighTrust;
    components.push({ label: 'tld', points: WEIGHTS.tldHighTrust, detail: 'a TLD businesses choose' });
  } else if (s.tldBand === 'cctld_business') {
    score += WEIGHTS.tldCcBusiness;
    components.push({ label: 'tld', points: WEIGHTS.tldCcBusiness, detail: 'a national business TLD' });
  } else if (s.tldBand === 'low_trust') {
    score += WEIGHTS.tldLowTrust;
    components.push({
      label: 'tld',
      points: WEIGHTS.tldLowTrust,
      detail: 'a cheap TLD dominated by bulk registration',
    });
  }

  // --- Name quality --------------------------------------------------------
  if (s.randomness.score >= 0.5) {
    const points = Math.round(WEIGHTS.randomNamePenalty * s.randomness.score);
    score += points;
    components.push({
      label: 'random_name',
      points,
      detail: `name looks machine-generated (${s.randomness.reasons.join(', ')})`,
    });
  }

  // --- Freshness -----------------------------------------------------------
  // Registered in the last week and already showing signs of life is the exact
  // event this product exists to catch.
  if (s.ageDays !== null && s.ageDays <= 7) {
    score += WEIGHTS.freshRegistration;
    components.push({
      label: 'fresh',
      points: WEIGHTS.freshRegistration,
      detail: s.ageDays === 0 ? 'registered today' : `registered ${s.ageDays} days ago`,
    });
  }

  // --- Classifier ----------------------------------------------------------
  if (classification) {
    if (classification.isRealBusiness) {
      const points = Math.round(WEIGHTS.classifierReal * classification.confidence);
      score += points;
      components.push({
        label: 'classifier',
        points,
        detail: `assessed as a real business (${classification.category}, ${classification.stageGuess}, confidence ${classification.confidence.toFixed(2)})`,
      });
    } else {
      const points = Math.round(WEIGHTS.classifierNotReal * classification.confidence);
      score += points;
      components.push({
        label: 'classifier',
        points,
        detail: `assessed as not a real business (confidence ${classification.confidence.toFixed(2)})`,
      });
    }
  }

  let final = Math.max(0, Math.min(100, Math.round(score)));

  /**
   * A confident classifier rejection caps the score rather than merely
   * subtracting from it.
   *
   * Without this, a domain with every mechanical signal (business email, a
   * Webflow build, a .com, fresh registration) still lands mid-cold even when
   * the classifier is 95% sure the page is template spam — and mechanical
   * signals are exactly what a well-funded spam operation buys. The classifier
   * is the only component that reads what the page actually says, so when it is
   * sure, it governs.
   */
  if (classification && !classification.isRealBusiness && classification.confidence >= 0.7) {
    const cap = Math.round(env.SCORE_TIER_COLD * (1 - classification.confidence));
    if (final > cap) {
      components.push({
        label: 'classifier_cap',
        points: cap - final,
        detail: `capped at ${cap}: the classifier is ${(classification.confidence * 100).toFixed(0)}% confident this is not a real business`,
      });
      final = cap;
    }
  }

  // --- Reason string -------------------------------------------------------
  // Lead with the classifier's own words when we have them; they are the most
  // specific thing we can say. Then the mechanical evidence, strongest first.
  const positives = components
    .filter((c) => c.points > 0 && c.label !== 'base')
    .sort((a, b) => b.points - a.points)
    .map((c) => c.detail);
  const negatives = components.filter((c) => c.points < 0).map((c) => c.detail);

  const parts: string[] = [];
  if (classification?.reason && classification.reason !== 'no reason given') {
    parts.push(classification.reason);
  }
  if (positives.length > 0) parts.push(`Signals: ${positives.join('; ')}.`);
  if (negatives.length > 0) parts.push(`Against: ${negatives.join('; ')}.`);
  if (parts.length === 0) parts.push(verdict.explanation);

  return {
    score: final,
    tier: tierFor(final),
    reason: parts.join(' '),
    components,
  };
}
