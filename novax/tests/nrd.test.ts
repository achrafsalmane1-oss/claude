import { describe, it, expect } from 'vitest';
import { zipSync, strToU8 } from 'fflate';
import { nrdUrlForDate, parseNrdArchive } from '@/ingest/nrd';

/**
 * The URL shape here was verified against the live service on 2026-08-17 (see
 * DECISIONS.md); this test locks in the encoding so a refactor cannot silently
 * change it.
 */
describe('nrdUrlForDate', () => {
  it('base64-encodes the filename and strips padding', () => {
    // base64("2026-08-13.zip") === "MjAyNi0wOC0xMy56aXA=" -> padding stripped.
    expect(nrdUrlForDate('2026-08-13')).toBe(
      'https://www.whoisds.com/whois-database/newly-registered-domains/MjAyNi0wOC0xMy56aXA/nrd',
    );
  });

  it('matches the verified encoding for other dates', () => {
    expect(nrdUrlForDate('2026-08-15')).toContain('MjAyNi0wOC0xNS56aXA');
    expect(nrdUrlForDate('2026-08-14')).toContain('MjAyNi0wOC0xNC56aXA');
  });

  it('rejects a malformed date rather than fetching a nonsense URL', () => {
    expect(() => nrdUrlForDate('13-08-2026')).toThrow(/invalid feed date/);
    expect(() => nrdUrlForDate('2026-8-13')).toThrow(/invalid feed date/);
    expect(() => nrdUrlForDate('')).toThrow(/invalid feed date/);
  });
});

function makeArchive(lines: string, filename = 'domain-names.txt'): Buffer {
  return Buffer.from(zipSync({ [filename]: strToU8(lines) }));
}

describe('parseNrdArchive', () => {
  it('parses the real archive layout: one apex per line in domain-names.txt', () => {
    const zip = makeArchive('springdaleportapotty.com\nbuyacerage.online\nnh2rpr8p.top\n');
    const result = parseNrdArchive(zip);
    expect(result.domains.map((d) => d.apex)).toEqual([
      'springdaleportapotty.com',
      'buyacerage.online',
      'nh2rpr8p.top',
    ]);
    expect(result.totalLines).toBe(3);
  });

  it('handles the CRLF line endings the live feed uses', () => {
    const zip = makeArchive('example.com\r\nexample.org\r\n');
    const result = parseNrdArchive(zip);
    expect(result.domains.map((d) => d.apex)).toEqual(['example.com', 'example.org']);
  });

  it('records the public-suffix TLD, not the last label', () => {
    const zip = makeArchive('example.co.uk\nexample.com.au\n');
    const result = parseNrdArchive(zip);
    expect(result.domains).toEqual([
      { apex: 'example.co.uk', tld: 'co.uk' },
      { apex: 'example.com.au', tld: 'com.au' },
    ]);
  });

  it('deduplicates within a single file', () => {
    const zip = makeArchive('example.com\nEXAMPLE.COM\nwww.example.com\n');
    const result = parseNrdArchive(zip);
    expect(result.domains).toHaveLength(1);
    expect(result.domains[0]!.apex).toBe('example.com');
  });

  it('skips unparseable lines and counts them', () => {
    const zip = makeArchive('good-domain.com\nlocalhost\n192.168.0.1\n\nanother.io\n');
    const result = parseNrdArchive(zip);
    expect(result.domains.map((d) => d.apex)).toEqual(['good-domain.com', 'another.io']);
    expect(result.skipped).toBe(2);
  });

  it('finds the text file even if it is renamed', () => {
    const zip = makeArchive('example.com\n', 'domains-2026-08-13.txt');
    expect(parseNrdArchive(zip).domains).toHaveLength(1);
  });

  it('fails loudly when the archive holds no text file', () => {
    const zip = Buffer.from(zipSync({ 'readme.pdf': strToU8('nope') }));
    expect(() => parseNrdArchive(zip)).toThrow(/no \.txt file/);
  });

  it('handles an empty file without throwing', () => {
    const result = parseNrdArchive(makeArchive(''));
    expect(result.domains).toEqual([]);
    expect(result.totalLines).toBe(0);
  });
});
