import { tldBand, type TldBand } from './data/blocked-tlds';
import { detectTyposquat, type TyposquatMatch } from './data/top-domains';

/**
 * The deterministic rules layer (spec §7).
 *
 * Runs on everything, costs nothing, and must eliminate the large majority
 * before any LLM call is made. Every function here is pure over a plain input
 * object — no database, no network — which is the only way the eval harness
 * stays fast enough to run on every change.
 *
 * The bar for a *kill* is deliberately high. A false kill is invisible (the
 * domain silently never surfaces) whereas a false pass merely costs a fraction
 * of a cent and gets caught by the classifier. So: kill only on evidence, and
 * let everything ambiguous through to be scored down instead.
 */

export interface RulesInput {
  apex: string;
  tld: string;

  // --- DNS ---
  hasA: boolean;
  hasMx: boolean;
  /** Provider name, e.g. "Google Workspace". Used in the reason string. */
  mxProvider: string | null;
  mxProviderKind: string | null;
  hasSpf: boolean;
  hasDmarc: boolean;
  nsProviders?: string[];

  // --- HTTP ---
  httpStatus: number | null;
  isParked: boolean;
  parkingVendor: string | null;
  title: string | null;
  metaDescription: string | null;
  bodySnippet: string | null;
  tech: string[];
  redirectedOffDomain: boolean;
  robotsAllowed: boolean;

  // --- RDAP ---
  registrar: string | null;
  registrationDate: Date | null;

  // --- Ingest ---
  source: string;
  ctHitCount: number;
  firstSeenAt: Date;
}

export type KillReason =
  | 'parked'
  | 'no_mx_no_site'
  | 'blocked_tld'
  | 'typosquat'
  | 'random_name'
  | 'redirects_off_domain'
  | 'dead_site';

export interface RulesVerdict {
  verdict: 'pass' | 'kill';
  killReason: KillReason | null;
  /** Human-readable explanation, stored and shown to the user. */
  explanation: string;
  signals: RulesSignals;
}

export interface RulesSignals {
  tldBand: TldBand;
  typosquat: TyposquatMatch | null;
  randomness: RandomnessScore;
  hasBusinessMx: boolean;
  /** SPF or DMARC published — someone configured mail deliberately. */
  hasMailAuth: boolean;
  hasRealContent: boolean;
  contentLength: number;
  buildSignals: string[];
  ageDays: number | null;
}

// --- Random-name detection -------------------------------------------------

/**
 * "Has a name that is random-character noise" (spec §7).
 *
 * Algorithmically generated domains (`nh2rpr8p.top`, `zrvem5gibnl6x32dm-2u.com`)
 * are a large share of every day's feed. The signals below are combined rather
 * than used alone, because each has obvious false positives on its own: plenty
 * of real startups have vowel-light names, and plenty have digits.
 */
export interface RandomnessScore {
  /** 0 = clearly human-chosen, 1 = clearly machine-generated. */
  score: number;
  reasons: string[];
}

const VOWELS = new Set(['a', 'e', 'i', 'o', 'u', 'y']);

export function randomnessScore(apex: string): RandomnessScore {
  const label = apex.split('.')[0]!.toLowerCase();
  const letters = label.replace(/[^a-z]/g, '');
  const reasons: string[] = [];
  let score = 0;

  if (label.length === 0) return { score: 1, reasons: ['empty label'] };

  // --- Vowel ratio: human words are roughly 35-45% vowels ---
  if (letters.length >= 6) {
    const vowelCount = [...letters].filter((c) => VOWELS.has(c)).length;
    const ratio = vowelCount / letters.length;
    if (ratio < 0.15) {
      score += 0.4;
      reasons.push(`almost no vowels (${(ratio * 100).toFixed(0)}%)`);
    } else if (ratio < 0.25) {
      score += 0.2;
      reasons.push(`vowel-light (${(ratio * 100).toFixed(0)}%)`);
    } else if (ratio > 0.72) {
      score += 0.25;
      reasons.push(`almost all vowels (${(ratio * 100).toFixed(0)}%)`);
    }
  }

  // --- Consonant runs: "zrvem5gibnl" has runs no English word has ---
  const longestConsonantRun = Math.max(0, ...(letters.match(/[^aeiouy]+/g) ?? []).map((r) => r.length));
  if (longestConsonantRun >= 5) {
    score += 0.35;
    reasons.push(`${longestConsonantRun} consecutive consonants`);
  } else if (longestConsonantRun === 4) {
    score += 0.15;
    reasons.push('4 consecutive consonants');
  }

  // --- Digits mixed into letters, e.g. "2138g-vlkep" ---
  const digitCount = (label.match(/\d/g) ?? []).length;
  const digitRatio = digitCount / label.length;
  if (digitRatio > 0.3) {
    score += 0.35;
    reasons.push(`${(digitRatio * 100).toFixed(0)}% digits`);
  } else if (digitCount > 0 && /[a-z]\d[a-z]/.test(label)) {
    // Digits *inside* a word rather than as a suffix ("mycompany2026" is fine,
    // "nh2rpr8p" is not).
    score += 0.2;
    reasons.push('digits interleaved with letters');
  }

  // --- Character-pair entropy: no repeated bigrams in a long label is odd ---
  if (letters.length >= 10) {
    const bigrams = new Set<string>();
    for (let i = 0; i < letters.length - 1; i++) bigrams.add(letters.slice(i, i + 2));
    if (bigrams.size === letters.length - 1) {
      score += 0.15;
      reasons.push('no repeated character pairs');
    }
  }

  // --- Very long labels with no separators are usually generated ---
  if (label.length >= 20 && !label.includes('-')) {
    score += 0.15;
    reasons.push(`${label.length} characters with no separator`);
  }

  return { score: Math.min(1, score), reasons };
}

// --- Content assessment ----------------------------------------------------

/**
 * Does the site show real content? Deliberately generous: a one-page site with
 * a title and a paragraph is a real early-stage company, and that is precisely
 * the thing we are selling.
 */
export function hasRealContent(input: RulesInput): { yes: boolean; length: number } {
  const body = (input.bodySnippet ?? '').trim();
  const title = (input.title ?? '').trim();
  const meta = (input.metaDescription ?? '').trim();
  const length = body.length;

  if (input.httpStatus === null) return { yes: false, length: 0 };
  if (input.httpStatus >= 400) return { yes: false, length };

  // A title plus any body, or a decent body alone, counts as content.
  const yes = (title.length > 0 && length >= 40) || length >= 200 || (title.length > 3 && meta.length > 20);
  return { yes, length };
}

// --- The rules -------------------------------------------------------------

export function applyRules(input: RulesInput): RulesVerdict {
  const band = tldBand(input.tld);
  const typosquat = detectTyposquat(input.apex);
  const randomness = randomnessScore(input.apex);
  const content = hasRealContent(input);
  const hasBusinessMx = input.mxProviderKind === 'business' || input.mxProviderKind === 'security';
  const buildSignals = input.tech.filter(
    (t) => !['cloudflare', 'nginx', 'apache', 'fastly', 'vercel', 'netlify', 'github-pages'].includes(t),
  );

  const ageDays = input.registrationDate
    ? Math.floor((Date.now() - input.registrationDate.getTime()) / 86_400_000)
    : null;

  const signals: RulesSignals = {
    tldBand: band,
    typosquat,
    randomness,
    hasBusinessMx,
    hasMailAuth: input.hasSpf || input.hasDmarc,
    hasRealContent: content.yes,
    contentLength: content.length,
    buildSignals,
    ageDays,
  };

  const kill = (reason: KillReason, explanation: string): RulesVerdict => ({
    verdict: 'kill',
    killReason: reason,
    explanation,
    signals,
  });

  // --- Kill 1: parked. Conclusive, and the highest-volume kill. ------------
  if (input.isParked) {
    return kill(
      'parked',
      input.parkingVendor
        ? `Parked page served by ${input.parkingVendor}.`
        : 'Serving a parking or placeholder page rather than a site.',
    );
  }

  // --- Kill 2: a TLD that is effectively never a real company --------------
  if (band === 'hard_kill') {
    return kill('blocked_tld', `Registered on .${input.tld}, a TLD dominated by throwaway registrations.`);
  }

  // --- Kill 3: targeting a known brand -------------------------------------
  if (typosquat) {
    if (typosquat.kind === 'lure_combo') {
      return kill(
        'typosquat',
        `Combines the brand "${typosquat.brand}" with phishing lure words — a squat, not a company.`,
      );
    }
    if (typosquat.kind === 'edit_distance') {
      return kill(
        'typosquat',
        `Within ${typosquat.distance} character edits of "${typosquat.brand}" — a typosquat.`,
      );
    }
    // `contains` alone is weaker: "shopifyexperts.com" may be a real agency.
    // Kill it only when there is nothing else going for the domain.
    if (!hasBusinessMx && !content.yes) {
      return kill(
        'typosquat',
        `Contains the brand "${typosquat.brand}" with no business email and no site content.`,
      );
    }
  }

  // --- Kill 4: an algorithmically generated name with nothing behind it ----
  // Note the conjunction. A random-looking name alone is not enough: real
  // companies do pick strange names. A random name with no mail, no content
  // and no build signal is not a company.
  if (randomness.score >= 0.6 && !hasBusinessMx && !content.yes) {
    return kill(
      'random_name',
      `Name looks machine-generated (${randomness.reasons.join(', ')}) with no business email and no site content.`,
    );
  }

  // --- Kill 5: a dead site with no mail ------------------------------------
  // Checked before the no-MX-no-site rule below, which would otherwise swallow
  // it: a 5xx page never counts as content, so the generic rule would fire
  // first and give a vaguer reason. The reason string is the product here, so
  // the more specific rule goes first.
  if (input.httpStatus !== null && input.httpStatus >= 500 && !input.hasMx) {
    return kill('dead_site', `Site returns HTTP ${input.httpStatus} and no mail is configured.`);
  }

  // --- Kill 6: a bare redirect to a different domain -----------------------
  // The intent is to catch a domain that exists only to forward traffic — a
  // redirect asset, not a company.
  //
  // The `!content.yes` condition is load-bearing and was added after the eval
  // set caught this rule killing three real businesses. When a redirect lands
  // on a page with real content, that content *is* the company's site (a site
  // builder or a hosting domain serving it), and killing it loses a genuine
  // lead. Only a redirect with nothing behind it is a redirect asset.
  if (input.redirectedOffDomain && !hasBusinessMx && !content.yes) {
    return kill('redirects_off_domain', 'Redirects to a different domain, with no content and no mail of its own.');
  }

  // --- Kill 7: no mail and no site. The spec's explicit rule. --------------
  if (!input.hasMx && !content.yes) {
    return kill(
      'no_mx_no_site',
      input.hasA
        ? 'Resolves but serves no meaningful content and has no mail configured.'
        : 'No mail configured and no website.',
    );
  }

  // --- Survived ------------------------------------------------------------
  const positives: string[] = [];
  if (hasBusinessMx) positives.push('business email configured');
  if (content.yes) positives.push(`${content.length} characters of page content`);
  if (buildSignals.length > 0) positives.push(`built with ${buildSignals.join(', ')}`);
  if (band === 'high_trust') positives.push(`.${input.tld} domain`);
  if (input.hasSpf || input.hasDmarc) positives.push('mail authentication records present');

  return {
    verdict: 'pass',
    killReason: null,
    explanation:
      positives.length > 0
        ? `Survived the rules layer: ${positives.join('; ')}.`
        : 'Survived the rules layer with no strong signal either way.',
    signals,
  };
}
