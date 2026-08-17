import { describe, it, expect } from 'vitest';
import { applyRules, randomnessScore, hasRealContent, type RulesInput } from '@/score/rules';
import { detectTyposquat, editDistance } from '@/score/data/top-domains';
import { tldBand } from '@/score/data/blocked-tlds';
import { computeScore, tierFor } from '@/score/composite';
import { parseClassification, FALLBACK_CLASSIFICATION, buildUserPrompt } from '@/score/classifier';

/** A domain with nothing going for it, as the base for each case. */
function makeInput(overrides: Partial<RulesInput> = {}): RulesInput {
  return {
    apex: 'example.com',
    tld: 'com',
    hasA: true,
    hasMx: false,
    mxProvider: null,
    mxProviderKind: null,
    hasSpf: false,
    hasDmarc: false,
    httpStatus: 200,
    isParked: false,
    parkingVendor: null,
    title: null,
    metaDescription: null,
    bodySnippet: null,
    tech: [],
    redirectedOffDomain: false,
    robotsAllowed: true,
    registrar: null,
    registrationDate: null,
    source: 'nrd_feed',
    ctHitCount: 0,
    firstSeenAt: new Date(),
    ...overrides,
  };
}

/** A plausible real company, for the "must not be killed" cases. */
function realCompany(overrides: Partial<RulesInput> = {}): RulesInput {
  return makeInput({
    apex: 'northwindlogistics.com',
    tld: 'com',
    hasMx: true,
    mxProviderKind: 'business',
    hasSpf: true,
    hasDmarc: true,
    title: 'Northwind Logistics',
    metaDescription: 'Freight forwarding and customs brokerage for mid-sized importers.',
    bodySnippet:
      'Northwind Logistics helps mid-sized importers move freight from Shenzhen to the US East Coast. '.repeat(
        8,
      ),
    tech: ['webflow', 'google-analytics'],
    registrar: 'Namecheap',
    registrationDate: new Date(Date.now() - 2 * 86_400_000),
    ...overrides,
  });
}

describe('randomness detection', () => {
  it('flags machine-generated names seen in the real feed', () => {
    // These are actual domains observed in the 2026-08-13 feed.
    expect(randomnessScore('nh2rpr8p.top').score).toBeGreaterThanOrEqual(0.5);
    expect(randomnessScore('zrvem5gibnl6x32dm-2u.com').score).toBeGreaterThanOrEqual(0.5);
    expect(randomnessScore('2138g-vlkep-zbxemx.work').score).toBeGreaterThanOrEqual(0.5);
  });

  it('does not flag real company names', () => {
    for (const name of [
      'northwindlogistics.com',
      'stripe.com',
      'basecamp.com',
      'linear.app',
      'vercel.com',
      'anthropic.com',
      'cibelesventanas.com',
    ]) {
      expect(randomnessScore(name).score).toBeLessThan(0.5);
    }
  });

  it('tolerates the vowel-light names real startups pick', () => {
    // Deliberate brandable names must survive: dropping vowels is a naming
    // fashion, not evidence of automation.
    expect(randomnessScore('flickr.com').score).toBeLessThan(0.6);
    expect(randomnessScore('tumblr.com').score).toBeLessThan(0.6);
    expect(randomnessScore('grndwrk.io').score).toBeLessThan(0.8);
  });

  it('gives a reason for every flag, so the score is explainable', () => {
    const result = randomnessScore('nh2rpr8p.top');
    expect(result.reasons.length).toBeGreaterThan(0);
  });
});

describe('typosquat detection', () => {
  it('catches brand plus lure words', () => {
    const match = detectTyposquat('paypal-secure-login.com');
    expect(match?.kind).toBe('lure_combo');
    expect(match?.brand).toBe('paypal');
  });

  it('catches near-miss spellings', () => {
    expect(detectTyposquat('paypa1.com')?.kind).toBe('edit_distance');
    expect(detectTyposquat('micros0ft.com')?.kind).toBe('edit_distance');
  });

  it('catches brands embedded in longer names', () => {
    expect(detectTyposquat('securecoinbaseupdate.com')?.brand).toBe('coinbase');
  });

  it('does not flag the brand its own domain', () => {
    expect(detectTyposquat('paypal.com')).toBeNull();
    expect(detectTyposquat('stripe.com')).toBeNull();
  });

  it('does not flag ordinary words that contain a short brand string', () => {
    // "ups" inside "startups", "att" inside "attention" — the reason short
    // brands are excluded from substring matching.
    expect(detectTyposquat('startupsdaily.com')).toBeNull();
    expect(detectTyposquat('attentionlab.io')).toBeNull();
  });

  it('caps edit distance early rather than computing the full matrix', () => {
    expect(editDistance('paypal', 'paypa1')).toBe(1);
    expect(editDistance('google', 'gogle')).toBe(1);
    expect(editDistance('short', 'averyverylongstring', 2)).toBe(3); // capped
  });
});

describe('TLD banding', () => {
  it('bands TLDs as expected', () => {
    expect(tldBand('com')).toBe('high_trust');
    expect(tldBand('io')).toBe('high_trust');
    expect(tldBand('co.uk')).toBe('cctld_business');
    expect(tldBand('xyz')).toBe('low_trust');
    expect(tldBand('zip')).toBe('hard_kill');
    expect(tldBand('tk')).toBe('hard_kill');
    // Demoted after the eval set found a real business on .cyou.
    expect(tldBand('cyou')).toBe('low_trust');
    expect(tldBand('bananas')).toBe('neutral');
  });
});

describe('content assessment', () => {
  it('accepts a small but real landing page', () => {
    const result = hasRealContent(
      makeInput({ title: 'Acme Co', bodySnippet: 'We build custom furniture in Leeds. Get in touch.' }),
    );
    expect(result.yes).toBe(true);
  });

  it('rejects an empty page', () => {
    expect(hasRealContent(makeInput({ title: null, bodySnippet: '' })).yes).toBe(false);
  });

  it('rejects an error page', () => {
    expect(hasRealContent(makeInput({ httpStatus: 503, bodySnippet: 'x'.repeat(500) })).yes).toBe(false);
  });
});

describe('rules layer — kills', () => {
  it('kills a parked domain', () => {
    const verdict = applyRules(makeInput({ isParked: true, parkingVendor: 'Sedo' }));
    expect(verdict.verdict).toBe('kill');
    expect(verdict.killReason).toBe('parked');
    expect(verdict.explanation).toContain('Sedo');
  });

  it('kills a hard-blocked TLD', () => {
    const verdict = applyRules(makeInput({ apex: 'thing.zip', tld: 'zip' }));
    expect(verdict.killReason).toBe('blocked_tld');
  });

  it('kills a typosquat even when it has a site', () => {
    const verdict = applyRules(
      realCompany({ apex: 'paypal-verify-account.com', tld: 'com' }),
    );
    expect(verdict.verdict).toBe('kill');
    expect(verdict.killReason).toBe('typosquat');
  });

  it('kills a machine-generated name with nothing behind it', () => {
    const verdict = applyRules(
      makeInput({ apex: 'zrvem5gibnl6x32dm-2u.com', bodySnippet: '', title: null }),
    );
    expect(verdict.verdict).toBe('kill');
    expect(verdict.killReason).toBe('random_name');
  });

  it('kills no-MX-and-no-site, the spec rule', () => {
    const verdict = applyRules(makeInput({ hasMx: false, bodySnippet: '', title: null }));
    expect(verdict.verdict).toBe('kill');
    expect(verdict.killReason).toBe('no_mx_no_site');
  });

  it('kills a bare redirect with nothing behind it', () => {
    const verdict = applyRules(
      makeInput({ redirectedOffDomain: true, hasMx: false, title: null, bodySnippet: '' }),
    );
    expect(verdict.killReason).toBe('redirects_off_domain');
  });

  /**
   * Regression: the eval set caught this rule killing three real businesses
   * (a listing agent, a Rotary club, a Thai scrap dealer) because their sites
   * are served from a builder/hosting domain. A redirect that lands on real
   * content is the company's site, not a redirect asset.
   */
  it('does NOT kill a redirect that lands on real content', () => {
    const verdict = applyRules(
      makeInput({
        redirectedOffDomain: true,
        hasMx: false,
        title: 'The Ritz-Carlton Residences | 15701 Collins Ave',
        bodySnippet: 'Listing agent for the Ritz-Carlton Residences in Sunny Isles. '.repeat(10),
      }),
    );
    expect(verdict.verdict).toBe('pass');
  });

  it('kills a 5xx site with no mail', () => {
    const verdict = applyRules(makeInput({ httpStatus: 503, hasMx: false, bodySnippet: 'x'.repeat(300) }));
    expect(verdict.killReason).toBe('dead_site');
  });
});

describe('rules layer — must not kill', () => {
  /**
   * False kills are the expensive error: the domain silently never surfaces and
   * nobody finds out. These cases guard the boundary.
   */
  it('passes a plausible real company', () => {
    const verdict = applyRules(realCompany());
    expect(verdict.verdict).toBe('pass');
    expect(verdict.signals.hasBusinessMx).toBe(true);
  });

  it('passes a machine-generated-looking name that has business email', () => {
    // A real company can pick a strange name. The kill requires the conjunction.
    const verdict = applyRules(
      makeInput({
        apex: 'zxqvt.io',
        tld: 'io',
        hasMx: true,
        mxProviderKind: 'business',
        title: 'zxqvt',
        bodySnippet: 'Infrastructure monitoring for Kubernetes clusters. '.repeat(6),
      }),
    );
    expect(verdict.verdict).toBe('pass');
  });

  it('passes a pre-launch company with mail configured but no site yet', () => {
    // Exactly the moment the product exists to catch.
    const verdict = applyRules(
      makeInput({
        apex: 'northwindfreight.com',
        hasMx: true,
        mxProviderKind: 'business',
        title: null,
        bodySnippet: '',
        httpStatus: 404,
      }),
    );
    expect(verdict.verdict).toBe('pass');
  });

  it('passes an agency whose name contains a brand but which is clearly real', () => {
    const verdict = applyRules(
      realCompany({
        apex: 'shopifyexperts.co.uk',
        tld: 'co.uk',
        title: 'Shopify Experts UK',
      }),
    );
    expect(verdict.verdict).toBe('pass');
  });

  it('passes a low-trust TLD when the domain is otherwise real', () => {
    const verdict = applyRules(realCompany({ apex: 'northwind.xyz', tld: 'xyz' }));
    expect(verdict.verdict).toBe('pass');
    expect(verdict.signals.tldBand).toBe('low_trust');
  });
});

describe('composite score', () => {
  it('scores a killed domain at zero and keeps the reason', () => {
    const verdict = applyRules(makeInput({ isParked: true, parkingVendor: 'Sedo' }));
    const result = computeScore({ verdict, classification: null, mxProvider: null });
    expect(result.score).toBe(0);
    expect(result.tier).toBe('junk');
    expect(result.reason).toContain('Sedo');
  });

  it('scores a strong domain highly when the classifier agrees', () => {
    const verdict = applyRules(realCompany());
    const result = computeScore({
      verdict,
      classification: {
        isRealBusiness: true,
        category: 'logistics',
        stageGuess: 'just_launched',
        confidence: 0.9,
        reason: 'Specific freight-forwarding offer with named trade lanes.',
      },
      mxProvider: 'Google Workspace',
    });
    expect(result.score).toBeGreaterThanOrEqual(80);
    expect(result.tier).toBe('hot');
    // The classifier's own words lead the reason string.
    expect(result.reason).toContain('freight-forwarding');
    expect(result.reason).toContain('Google Workspace');
  });

  it('drops the score sharply when the classifier says it is not a business', () => {
    const verdict = applyRules(realCompany());
    const result = computeScore({
      verdict,
      classification: {
        isRealBusiness: false,
        category: 'parked_or_spam',
        stageGuess: 'unknown',
        confidence: 0.95,
        reason: 'Generic filler copy matching thousands of template sites.',
      },
      mxProvider: 'Google Workspace',
    });
    expect(result.score).toBeLessThan(50);
  });

  it('never leaves the 0-100 range', () => {
    const strong = computeScore({
      verdict: applyRules(realCompany()),
      classification: {
        isRealBusiness: true,
        category: 'saas',
        stageGuess: 'operating',
        confidence: 1,
        reason: 'x',
      },
      mxProvider: 'Google Workspace',
    });
    expect(strong.score).toBeLessThanOrEqual(100);
    expect(strong.score).toBeGreaterThanOrEqual(0);
  });

  it('always produces a non-empty, human-readable reason', () => {
    const verdict = applyRules(makeInput({ hasMx: true, mxProviderKind: 'unknown', title: 'Thing', bodySnippet: 'A thing. '.repeat(20) }));
    const result = computeScore({ verdict, classification: null, mxProvider: null });
    expect(result.reason.length).toBeGreaterThan(10);
  });

  it('maps scores to tiers at the configured thresholds', () => {
    expect(tierFor(95)).toBe('hot');
    expect(tierFor(70)).toBe('warm');
    expect(tierFor(45)).toBe('cold');
    expect(tierFor(10)).toBe('junk');
  });
});

describe('classifier output parsing — must be defensive', () => {
  const valid = {
    is_real_business: true,
    category: 'saas',
    stage_guess: 'just_launched',
    confidence: 0.82,
    reason: 'Clear product description with pricing.',
  };

  it('parses well-formed JSON', () => {
    const result = parseClassification(JSON.stringify(valid));
    expect(result.isRealBusiness).toBe(true);
    expect(result.category).toBe('saas');
    expect(result.confidence).toBeCloseTo(0.82);
  });

  it('parses JSON wrapped in a markdown fence', () => {
    const result = parseClassification('```json\n' + JSON.stringify(valid) + '\n```');
    expect(result.isRealBusiness).toBe(true);
  });

  it('parses JSON with prose around it', () => {
    const result = parseClassification(`Here is my assessment:\n${JSON.stringify(valid)}\nHope that helps.`);
    expect(result.category).toBe('saas');
  });

  it('falls back safely on unparseable output rather than throwing', () => {
    expect(parseClassification('I cannot determine this.')).toEqual(FALLBACK_CLASSIFICATION);
    expect(parseClassification('')).toEqual(FALLBACK_CLASSIFICATION);
    expect(parseClassification('{ truncated json')).toEqual(FALLBACK_CLASSIFICATION);
  });

  it('never returns a true verdict from unparseable output', () => {
    // The safe direction: a broken response must not manufacture a lead.
    expect(parseClassification('garbage').isRealBusiness).toBe(false);
  });

  it('recovers partial objects field by field', () => {
    const result = parseClassification('{"is_real_business": true, "reason": "Has a real product page."}');
    expect(result.isRealBusiness).toBe(true);
    expect(result.reason).toBe('Has a real product page.');
    expect(result.category).toBe('unknown');
    expect(result.confidence).toBe(0);
  });

  it('clamps an out-of-range confidence', () => {
    expect(parseClassification('{"is_real_business":true,"confidence":5}').confidence).toBe(1);
    expect(parseClassification('{"is_real_business":true,"confidence":-2}').confidence).toBe(0);
    expect(parseClassification('{"is_real_business":true,"confidence":"high"}').confidence).toBe(0);
  });

  it('preserves an unexpected category rather than hiding it', () => {
    const result = parseClassification('{"is_real_business":true,"category":"veterinary"}');
    expect(result.category).toContain('veterinary');
  });
});

describe('classifier prompt construction', () => {
  it('includes every signal the spec lists', () => {
    const prompt = buildUserPrompt({
      apex: 'northwind.com',
      tld: 'com',
      title: 'Northwind',
      metaDescription: 'Freight forwarding',
      bodySnippet: 'We move freight.',
      mxProvider: 'Google Workspace',
      tech: ['webflow'],
      registrar: 'Namecheap',
      country: 'GB',
    });
    expect(prompt).toContain('northwind.com');
    expect(prompt).toContain('Northwind');
    expect(prompt).toContain('Freight forwarding');
    expect(prompt).toContain('Google Workspace');
    expect(prompt).toContain('webflow');
    expect(prompt).toContain('We move freight.');
  });

  it('marks missing fields explicitly rather than leaving blanks', () => {
    const prompt = buildUserPrompt({
      apex: 'x.com',
      tld: 'com',
      title: null,
      metaDescription: null,
      bodySnippet: null,
      mxProvider: null,
      tech: [],
      registrar: null,
      country: null,
    });
    expect(prompt).toContain('(none)');
    expect(prompt).toContain('(none configured)');
    expect(prompt).toContain('(page had no readable text)');
  });
});
