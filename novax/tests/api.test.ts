import { describe, it, expect } from 'vitest';
import { parseFilters, encodeCursor, decodeCursor } from '@/api/filters';
import { toCsv, toFlatDomain, type FlatDomain } from '@/api/serialize';
import { extractKey, hashKey } from '@/api/auth';
import { signPayload, verifySignature, generateSecret } from '@/delivery/webhooks';
import { renderDigestHtml, renderDigestText } from '@/delivery/digest';

describe('filter parsing', () => {
  it('applies the documented defaults', () => {
    const f = parseFilters(new URLSearchParams(''));
    expect(f.limit).toBe(100);
  });

  it('coerces numeric params from strings', () => {
    const f = parseFilters(new URLSearchParams('min_score=70&limit=25&days=7'));
    expect(f.min_score).toBe(70);
    expect(f.limit).toBe(25);
    expect(f.days).toBe(7);
  });

  it('ignores empty params so ?tld= is not a filter on the empty string', () => {
    const f = parseFilters(new URLSearchParams('tld=&min_score=50'));
    expect(f.tld).toBeUndefined();
    expect(f.min_score).toBe(50);
  });

  it('caps limit at 1000 rather than letting a client ask for everything', () => {
    expect(() => parseFilters(new URLSearchParams('limit=100000'))).toThrow();
  });

  it('rejects an out-of-range score', () => {
    expect(() => parseFilters(new URLSearchParams('min_score=500'))).toThrow();
  });

  it('accepts every filter the spec lists', () => {
    const f = parseFilters(
      new URLSearchParams(
        'from=2026-08-01&to=2026-08-17&tld=com,io&country=US&mx_provider=business' +
          '&min_score=60&category=saas&tech=shopify,webflow&tier=hot&is_real_business=true',
      ),
    );
    expect(f.from).toBe('2026-08-01');
    expect(f.tld).toBe('com,io');
    expect(f.country).toBe('US');
    expect(f.mx_provider).toBe('business');
    expect(f.category).toBe('saas');
    expect(f.tech).toBe('shopify,webflow');
    expect(f.tier).toBe('hot');
    expect(f.is_real_business).toBe('true');
  });

  it('rejects an unknown tier rather than silently ignoring it', () => {
    expect(() => parseFilters(new URLSearchParams('tier=lukewarm'))).toThrow();
  });
});

describe('keyset cursor', () => {
  it('round-trips', () => {
    const cursor = { score: 72, id: 12345 };
    expect(decodeCursor(encodeCursor(cursor))).toEqual(cursor);
  });

  it('returns null for a malformed cursor instead of throwing', () => {
    expect(decodeCursor('not-a-cursor')).toBeNull();
    expect(decodeCursor('')).toBeNull();
  });

  it('is url-safe', () => {
    const encoded = encodeCursor({ score: 100, id: 999999 });
    expect(encoded).toMatch(/^[A-Za-z0-9_-]+$/);
  });
});

describe('API key handling', () => {
  it('reads a key from the Authorization bearer header', () => {
    const headers = new Headers({ authorization: 'Bearer nvx_live_abc123' });
    expect(extractKey(headers)).toBe('nvx_live_abc123');
  });

  it('reads a key from X-API-Key, which is easier to set in Clay', () => {
    const headers = new Headers({ 'x-api-key': 'nvx_live_abc123' });
    expect(extractKey(headers)).toBe('nvx_live_abc123');
  });

  it('tolerates a bare key in the Authorization header', () => {
    const headers = new Headers({ authorization: 'nvx_live_abc123' });
    expect(extractKey(headers)).toBe('nvx_live_abc123');
  });

  it('returns null when no key is present', () => {
    expect(extractKey(new Headers())).toBeNull();
    expect(extractKey(new Headers({ authorization: 'Basic dXNlcjpwYXNz' }))).toBeNull();
  });

  it('hashes deterministically and never returns the plaintext', () => {
    const hash = hashKey('nvx_live_secret');
    expect(hash).toHaveLength(64);
    expect(hash).toBe(hashKey('nvx_live_secret'));
    expect(hash).not.toContain('secret');
  });
});

describe('webhook signing', () => {
  const secret = 'whsec_test_secret';
  const body = JSON.stringify({ event: 'domains.matched', count: 1 });

  it('produces a verifiable signature', () => {
    const ts = Math.floor(Date.now() / 1000);
    const sig = signPayload(secret, body, ts);
    expect(sig).toMatch(/^sha256=[0-9a-f]{64}$/);
    expect(verifySignature(secret, body, ts, sig)).toBe(true);
  });

  it('rejects a signature made with the wrong secret', () => {
    const ts = Math.floor(Date.now() / 1000);
    const sig = signPayload('whsec_other', body, ts);
    expect(verifySignature(secret, body, ts, sig)).toBe(false);
  });

  it('rejects a tampered body', () => {
    const ts = Math.floor(Date.now() / 1000);
    const sig = signPayload(secret, body, ts);
    expect(verifySignature(secret, `${body} `, ts, sig)).toBe(false);
  });

  it('rejects a replayed signature outside the tolerance window', () => {
    const old = Math.floor(Date.now() / 1000) - 3600;
    const sig = signPayload(secret, body, old);
    expect(verifySignature(secret, body, old, sig)).toBe(false);
    // ...but accepts it inside a wide enough window.
    expect(verifySignature(secret, body, old, sig, 7200)).toBe(true);
  });

  it('generates distinct, prefixed secrets', () => {
    const a = generateSecret();
    const b = generateSecret();
    expect(a).toMatch(/^whsec_/);
    expect(a).not.toBe(b);
  });
});

// A representative row, matching what the serializer produces.
function makeDomain(overrides: Partial<FlatDomain> = {}): FlatDomain {
  return {
    domain: 'northwind.com',
    tld: 'com',
    score: 84,
    tier: 'hot',
    reason: 'Specific freight-forwarding offer. Signals: business email configured on Google Workspace.',
    company_name: 'Northwind Logistics',
    description: 'Freight forwarding for mid-sized importers',
    category: 'logistics',
    stage: 'just_launched',
    country: 'US',
    website: 'https://northwind.com',
    confidence: 0.9,
    is_real_business: true,
    mx_provider: 'Google Workspace',
    mx_provider_kind: 'business',
    has_business_email: true,
    has_spf: true,
    has_dmarc: true,
    tech: ['webflow', 'stripe'],
    tech_list: 'webflow, stripe',
    page_title: 'Northwind Logistics',
    meta_description: 'Freight forwarding',
    http_status: 200,
    final_url: 'https://northwind.com/',
    is_parked: false,
    registrar: 'Namecheap',
    registration_date: '2026-08-15T00:00:00.000Z',
    registration_date_source: 'rdap',
    expires_date: '2027-08-15T00:00:00.000Z',
    nameservers: ['ns1.example.com'],
    nameserver_list: 'ns1.example.com',
    source: 'nrd_feed',
    first_seen_at: '2026-08-15T02:00:00.000Z',
    last_seen_at: '2026-08-17T02:00:00.000Z',
    dns_resolved_at: '2026-08-17T02:05:00.000Z',
    http_probed_at: '2026-08-17T02:06:00.000Z',
    rdap_fetched_at: '2026-08-17T02:07:00.000Z',
    scored_at: '2026-08-17T02:08:00.000Z',
    scoring_version: 'rules-1.0.0',
    model_version: 'claude-opus-5',
    ...overrides,
  };
}

describe('response shape — the Clay contract', () => {
  /**
   * The distribution wedge is Clay's HTTP API column, which maps JSON keys onto
   * spreadsheet columns and handles nesting badly. These tests are the contract.
   */
  it('is flat: every value is a scalar or an array of scalars, never an object', () => {
    const row = makeDomain() as unknown as Record<string, unknown>;
    for (const [key, value] of Object.entries(row)) {
      if (Array.isArray(value)) {
        for (const item of value) {
          expect(typeof item, `${key}[] must contain scalars`).toBe('string');
        }
        continue;
      }
      expect(['string', 'number', 'boolean', 'object'], key).toContain(typeof value);
      if (typeof value === 'object') expect(value, `${key} must be null, not an object`).toBeNull();
    }
  });

  it('uses stable snake_case keys', () => {
    for (const key of Object.keys(makeDomain())) {
      expect(key, `${key} should be snake_case`).toMatch(/^[a-z][a-z0-9_]*$/);
    }
  });

  it('exposes multi-valued fields as a pre-joined string as well as an array', () => {
    const row = makeDomain();
    expect(row.tech_list).toBe('webflow, stripe');
    expect(row.nameserver_list).toBe('ns1.example.com');
  });

  it('carries provenance for every enrichment stage', () => {
    const row = makeDomain();
    expect(row.dns_resolved_at).toBeTruthy();
    expect(row.http_probed_at).toBeTruthy();
    expect(row.rdap_fetched_at).toBeTruthy();
    expect(row.scored_at).toBeTruthy();
    expect(row.scoring_version).toBeTruthy();
    expect(row.registration_date_source).toBe('rdap');
  });

  it('never exposes registrant personal data', () => {
    const keys = Object.keys(makeDomain()).join(' ');
    for (const forbidden of ['registrant_name', 'registrant_email', 'phone', 'street', 'address']) {
      expect(keys).not.toContain(forbidden);
    }
  });
});

describe('serialization from a database row', () => {
  it('derives has_business_email from the MX kind', () => {
    expect(toFlatDomain({ apex: 'a.com', tld: 'com', mxProviderKind: 'business', source: 'nrd_feed', firstSeenAt: new Date(), lastSeenAt: new Date() }).has_business_email).toBe(true);
    expect(toFlatDomain({ apex: 'a.com', tld: 'com', mxProviderKind: 'security', source: 'nrd_feed', firstSeenAt: new Date(), lastSeenAt: new Date() }).has_business_email).toBe(true);
    expect(toFlatDomain({ apex: 'a.com', tld: 'com', mxProviderKind: 'parking', source: 'nrd_feed', firstSeenAt: new Date(), lastSeenAt: new Date() }).has_business_email).toBe(false);
  });

  it('falls back to a derived website when no company record exists', () => {
    const row = toFlatDomain({ apex: 'a.com', tld: 'com', source: 'nrd_feed', firstSeenAt: new Date(), lastSeenAt: new Date() });
    expect(row.website).toBe('https://a.com');
  });

  it('defaults missing arrays to empty rather than null', () => {
    const row = toFlatDomain({ apex: 'a.com', tld: 'com', source: 'nrd_feed', firstSeenAt: new Date(), lastSeenAt: new Date() });
    expect(row.tech).toEqual([]);
    expect(row.tech_list).toBe('');
  });
});

describe('CSV export', () => {
  it('emits a header plus one row per domain', () => {
    const csv = toCsv([makeDomain(), makeDomain({ domain: 'other.com' })]);
    const lines = csv.split('\n');
    expect(lines).toHaveLength(3);
    expect(lines[0]).toContain('domain,tld,score');
  });

  it('drops the array columns in favour of their joined form', () => {
    const header = toCsv([makeDomain()]).split('\n')[0]!;
    expect(header).toContain('tech_list');
    expect(header.split(',')).not.toContain('tech');
    expect(header.split(',')).not.toContain('nameservers');
  });

  it('quotes fields containing commas, quotes or newlines', () => {
    const csv = toCsv([
      makeDomain({ reason: 'Sells things, cheaply. Said "hello".', company_name: 'Line\nBreak Ltd' }),
    ]);
    expect(csv).toContain('"Sells things, cheaply. Said ""hello""."');
    expect(csv).toContain('"Line\nBreak Ltd"');
  });

  it('returns an empty string for no rows rather than a bare header', () => {
    expect(toCsv([])).toBe('');
  });
});

describe('digest rendering', () => {
  it('leads with the reason, which is what makes the email worth opening', () => {
    const html = renderDigestHtml({
      searchName: 'UK SaaS',
      domains: [makeDomain()],
      baseUrl: 'https://novax.example',
    });
    expect(html).toContain('northwind.com');
    expect(html).toContain('freight-forwarding');
    expect(html).toContain('Northwind Logistics');
  });

  it('escapes HTML so a hostile page title cannot inject markup into the email', () => {
    const html = renderDigestHtml({
      searchName: 'x',
      domains: [makeDomain({ company_name: '<script>alert(1)</script>' })],
      baseUrl: 'https://novax.example',
    });
    expect(html).not.toContain('<script>alert(1)</script>');
    expect(html).toContain('&lt;script&gt;');
  });

  it('links to the opt-out page, which every outbound email should', () => {
    const html = renderDigestHtml({ searchName: 'x', domains: [makeDomain()], baseUrl: 'https://novax.example' });
    expect(html).toContain('/opt-out');
  });

  it('renders a plain-text alternative', () => {
    const text = renderDigestText('UK SaaS', [makeDomain()]);
    expect(text).toContain('northwind.com');
    expect(text).toContain('[hot 84]');
  });
});
