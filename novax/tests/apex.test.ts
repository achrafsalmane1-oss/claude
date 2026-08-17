import { describe, it, expect } from 'vitest';
import { extractApex, apexesFromSans, normaliseHostname, isApexLevelName } from '@/ingest/apex';

describe('normaliseHostname', () => {
  it('lowercases and trims', () => {
    expect(normaliseHostname('  ExAmPle.COM  ')).toBe('example.com');
  });

  it('strips wildcards, including nested ones', () => {
    expect(normaliseHostname('*.example.com')).toBe('example.com');
    expect(normaliseHostname('*.*.example.com')).toBe('example.com');
  });

  it('strips trailing dots and ports', () => {
    expect(normaliseHostname('example.com.')).toBe('example.com');
    expect(normaliseHostname('example.com:443')).toBe('example.com');
  });

  it('rejects non-hostnames', () => {
    expect(normaliseHostname('')).toBeNull();
    expect(normaliseHostname('localhost')).toBeNull(); // no dot
    expect(normaliseHostname('has space.com')).toBeNull();
    expect(normaliseHostname('user@example.com')).toBeNull();
    expect(normaliseHostname('http://example.com/path')).toBeNull();
  });
});

describe('extractApex — public suffix handling', () => {
  it('handles plain two-label domains', () => {
    expect(extractApex('example.com')).toEqual({ apex: 'example.com', tld: 'com' });
  });

  it('handles subdomains', () => {
    expect(extractApex('www.example.com')).toEqual({ apex: 'example.com', tld: 'com' });
    expect(extractApex('deep.nested.sub.example.com')).toEqual({ apex: 'example.com', tld: 'com' });
  });

  // This is the case naive last-two-labels splitting gets wrong, per spec §5b.
  it('handles multi-label public suffixes', () => {
    expect(extractApex('shop.example.co.uk')).toEqual({ apex: 'example.co.uk', tld: 'co.uk' });
    expect(extractApex('example.com.au')).toEqual({ apex: 'example.com.au', tld: 'com.au' });
    expect(extractApex('www.example.co.jp')).toEqual({ apex: 'example.co.jp', tld: 'co.jp' });
    expect(extractApex('foo.bar.org.uk')).toEqual({ apex: 'bar.org.uk', tld: 'org.uk' });
  });

  it('handles new gTLDs', () => {
    expect(extractApex('startup.io')).toEqual({ apex: 'startup.io', tld: 'io' });
    expect(extractApex('www.thing.ventures')).toEqual({ apex: 'thing.ventures', tld: 'ventures' });
  });

  it('rejects IP addresses, which CT certificates do carry', () => {
    expect(extractApex('192.168.1.1')).toBeNull();
    expect(extractApex('8.8.8.8')).toBeNull();
  });

  it('rejects unlisted suffixes', () => {
    expect(extractApex('server.local')).toBeNull();
    expect(extractApex('box.internal')).toBeNull();
  });

  /**
   * The deliberate PSL choice, documented in DECISIONS.md: we run with the
   * private section disabled, because we want the domain someone paid a
   * registrar for. `myapp.github.io` is not a registration; `github.io` is.
   * Enabling the private section would make every Vercel/Pages subdomain look
   * like a new company.
   */
  it('collapses platform subdomains to the platform apex, then drops them', () => {
    expect(extractApex('myapp.github.io')).toBeNull();
    expect(extractApex('my-startup.vercel.app')).toBeNull();
    expect(extractApex('shop.myshopify.com')).toBeNull();
    expect(extractApex('tenant.herokuapp.com')).toBeNull();
    expect(extractApex('preview.pages.dev')).toBeNull();
    // Including the bare platform apex itself.
    expect(extractApex('github.io')).toBeNull();
  });

  it('does not confuse a real domain that merely contains a platform name', () => {
    expect(extractApex('github.io.example.com')).toEqual({ apex: 'example.com', tld: 'com' });
    expect(extractApex('notgithub.io')).toEqual({ apex: 'notgithub.io', tld: 'io' });
  });
});

describe('apexesFromSans', () => {
  it('collapses the common apex + www + wildcard cert to one apex', () => {
    expect(apexesFromSans(['example.com', 'www.example.com', '*.example.com'])).toEqual([
      { apex: 'example.com', tld: 'com' },
    ]);
  });

  it('keeps genuinely distinct apexes on a multi-domain cert', () => {
    const result = apexesFromSans(['a.com', 'www.b.co.uk', '*.c.io']);
    expect(result.map((r) => r.apex).sort()).toEqual(['a.com', 'b.co.uk', 'c.io']);
  });

  it('drops junk without dropping the rest of the cert', () => {
    const result = apexesFromSans(['10.0.0.1', 'localhost', 'real-company.com', 'app.vercel.app']);
    expect(result).toEqual([{ apex: 'real-company.com', tld: 'com' }]);
  });

  it('returns an empty array for an empty SAN list', () => {
    expect(apexesFromSans([])).toEqual([]);
  });
});

describe('isApexLevelName', () => {
  it('is true for the apex and www', () => {
    expect(isApexLevelName('example.com')).toBe(true);
    expect(isApexLevelName('www.example.com')).toBe(true);
    expect(isApexLevelName('example.co.uk')).toBe(true);
  });

  it('is false for deeper subdomains, which are weaker evidence of a new site', () => {
    expect(isApexLevelName('mail.example.com')).toBe(false);
    expect(isApexLevelName('staging.app.example.com')).toBe(false);
  });
});
