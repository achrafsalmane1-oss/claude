import { describe, it, expect } from 'vitest';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import {
  parseMerkleTreeLeaf,
  extractDnsNames,
  dnsNamesFromLeafInput,
  CtParseError,
} from '@/ingest/ct/der';

/**
 * Fixtures are real `leaf_input` values captured from
 * `ct.googleapis.com/logs/us1/argon2026h2` on 2026-08-17 — one historical entry
 * and six from the tree head. They cover both `x509_entry` (full certificate)
 * and `precert_entry` (bare TBSCertificate), which is the asymmetry this parser
 * exists to handle.
 */
const leaves: string[] = JSON.parse(
  readFileSync(fileURLToPath(new URL('./fixtures/ct-leaves.json', import.meta.url)), 'utf8'),
);

describe('parseMerkleTreeLeaf', () => {
  it('parses every captured leaf', () => {
    for (const leaf of leaves) {
      const parsed = parseMerkleTreeLeaf(leaf);
      expect(['x509', 'precert']).toContain(parsed.entryType);
      expect(parsed.certBytes.length).toBeGreaterThan(100);
      // Timestamps are real SCT times, so sane epoch millis.
      expect(parsed.timestamp).toBeGreaterThan(1_400_000_000_000);
      expect(parsed.timestamp).toBeLessThan(4_000_000_000_000);
    }
  });

  it('covers both entry types in the fixture set', () => {
    const types = new Set(leaves.map((l) => parseMerkleTreeLeaf(l).entryType));
    expect(types.has('x509')).toBe(true);
    expect(types.has('precert')).toBe(true);
  });

  it('rejects a truncated leaf rather than reading past the buffer', () => {
    expect(() => parseMerkleTreeLeaf(Buffer.from([0, 0, 1]).toString('base64'))).toThrow(CtParseError);
  });

  it('rejects an unknown entry type', () => {
    // version, leaf_type, 8-byte timestamp, then entry_type = 0x0099.
    const buf = Buffer.alloc(14);
    buf.writeUInt16BE(0x0099, 10);
    expect(() => parseMerkleTreeLeaf(buf.toString('base64'))).toThrow(/unknown entry_type/);
  });

  it('rejects a certificate length that overruns the leaf', () => {
    const buf = Buffer.alloc(20);
    buf.writeUInt16BE(0, 10); // x509 entry
    buf[12] = 0xff; // absurd 3-byte length
    buf[13] = 0xff;
    buf[14] = 0xff;
    expect(() => parseMerkleTreeLeaf(buf.toString('base64'))).toThrow(/exceeds leaf/);
  });
});

describe('extractDnsNames', () => {
  it('extracts SANs from every captured leaf', () => {
    for (const leaf of leaves) {
      const { certBytes } = parseMerkleTreeLeaf(leaf);
      const names = extractDnsNames(certBytes);
      expect(names.length).toBeGreaterThan(0);
      for (const name of names) {
        // Either a hostname or a wildcard; never empty, never binary junk.
        expect(name).toMatch(/^[*a-z0-9.\-_]+$/i);
        expect(name).toContain('.');
      }
    }
  });

  it('extracts the exact SANs recorded from the live log', () => {
    // These were verified by hand against the live get-entries response.
    const all = leaves.map((l) => dnsNamesFromLeafInput(l).names);
    expect(all).toContainEqual(['flowers-to-the-world.com']);
    expect(all).toContainEqual(['selma-lagerloef-haus.org', 'www.selma-lagerloef-haus.org']);
    // A wildcard cert: both the wildcard and the apex are present.
    expect(all).toContainEqual(['*.powiatprzemysl.pl', 'powiatprzemysl.pl']);
    // A precert entry, parsed from a bare TBSCertificate.
    expect(all).toContainEqual(['www.marketingvideoezy.com']);
  });

  it('returns an empty array when there is no SAN extension', () => {
    expect(extractDnsNames(Buffer.from([0x30, 0x03, 0x02, 0x01, 0x00]))).toEqual([]);
  });

  it('does not throw on random bytes', () => {
    const random = Buffer.from(Array.from({ length: 512 }, (_, i) => (i * 37) % 256));
    expect(() => extractDnsNames(random)).not.toThrow();
  });
});

describe('dnsNamesFromLeafInput', () => {
  it('reports an error instead of throwing, so one bad entry cannot stall a log', () => {
    const result = dnsNamesFromLeafInput('bm90LWEtbGVhZg==');
    expect(result.names).toEqual([]);
    expect(result.error).toBeDefined();
    expect(result.entryType).toBeNull();
  });

  it('returns entry type and timestamp alongside the names', () => {
    const result = dnsNamesFromLeafInput(leaves[0]!);
    expect(result.error).toBeUndefined();
    expect(result.entryType).not.toBeNull();
    expect(result.timestamp).not.toBeNull();
  });
});
