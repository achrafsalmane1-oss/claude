import { describe, it, expect } from 'vitest';
import { LruSet, Deduper } from '@/ingest/dedupe';
import { diffZones, parseZoneFile } from '@/ingest/czds';

describe('LruSet', () => {
  it('reports first insert as new and repeats as seen', () => {
    const lru = new LruSet(10);
    expect(lru.add('a.com')).toBe(true);
    expect(lru.add('a.com')).toBe(false);
    expect(lru.add('b.com')).toBe(true);
  });

  it('evicts the least recently used entry at capacity', () => {
    const lru = new LruSet(2);
    lru.add('a.com');
    lru.add('b.com');
    lru.add('c.com'); // evicts a.com
    expect(lru.has('a.com')).toBe(false);
    expect(lru.has('b.com')).toBe(true);
    expect(lru.has('c.com')).toBe(true);
    expect(lru.size).toBe(2);
  });

  it('refreshes recency on a hit so hot domains survive churn', () => {
    const lru = new LruSet(2);
    lru.add('a.com');
    lru.add('b.com');
    lru.add('a.com'); // touch a.com -> b.com is now the oldest
    lru.add('c.com'); // evicts b.com, not a.com
    expect(lru.has('a.com')).toBe(true);
    expect(lru.has('b.com')).toBe(false);
  });
});

describe('Deduper', () => {
  it('filters repeats out of a CT batch', () => {
    const d = new Deduper(1000);
    expect(d.filter(['a.com', 'b.com', 'a.com'])).toEqual(['a.com', 'b.com']);
    // The classic case: the same apex seen again on the next batch.
    expect(d.filter(['a.com', 'c.com'])).toEqual(['c.com']);
  });

  it('tracks a hit rate for the health metric', () => {
    const d = new Deduper(1000);
    d.filter(['a.com', 'b.com']);
    d.filter(['a.com', 'b.com']);
    const stats = d.snapshot();
    expect(stats.seen).toBe(4);
    expect(stats.passed).toBe(2);
    expect(stats.suppressed).toBe(2);
    expect(stats.hitRate).toBe(0.5);
  });
});

describe('CZDS zone parsing and diffing', () => {
  const zone = `
; sample zone
com.	900	IN	SOA	a.gtld-servers.net. nstld.verisign-grs.com. 1 1800 900 604800 86400
newco.com.	172800	IN	NS	ns1.example-dns.com.
newco.com.	172800	IN	NS	ns2.example-dns.com.
oldco.com.	172800	IN	NS	ns1.other.com.
ns1.example-dns.com.	172800	IN	A	192.0.2.1
sub.newco.com.	172800	IN	NS	ns1.delegated.com.
`;

  it('takes NS owner names only, not glue records', () => {
    const apexes = parseZoneFile(zone);
    expect([...apexes].sort()).toEqual(['newco.com', 'oldco.com']);
    // A record owners must not appear.
    expect(apexes.has('ns1.example-dns.com')).toBe(false);
    // Sub-delegations are not registrations.
    expect(apexes.has('sub.newco.com')).toBe(false);
  });

  it('deduplicates a domain with multiple NS records', () => {
    // newco.com appears twice in the zone above.
    expect(parseZoneFile(zone).size).toBe(2);
  });

  it('diffs day over day to produce the newly-delegated set', () => {
    const yesterday = new Set(['a.com', 'b.com']);
    const today = new Set(['b.com', 'c.com']);
    const diff = diffZones(yesterday, today);
    expect(diff.added).toEqual(['c.com']);
    expect(diff.removed).toEqual(['a.com']);
    expect(diff.unchanged).toBe(1);
  });

  it('treats an empty previous day as everything being new', () => {
    const diff = diffZones(new Set(), new Set(['a.com', 'b.com']));
    expect(diff.added.sort()).toEqual(['a.com', 'b.com']);
    expect(diff.removed).toEqual([]);
  });
});
