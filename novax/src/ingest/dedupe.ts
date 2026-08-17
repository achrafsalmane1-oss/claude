/**
 * In-process dedupe for the CT firehose.
 *
 * CT emits millions of SANs a day and most are repeats — renewals, subdomains
 * of the same site, wildcards issued alongside the apex. "A domain seen for the
 * 40th time this week is not new" (spec §5b). Absorbing those repeats here keeps
 * them from becoming database round-trips.
 *
 * This is a *performance* layer, not a correctness boundary: the unique index on
 * `domains.apex` plus `ON CONFLICT DO NOTHING` is what actually guarantees no
 * duplicates. Losing this cache to a restart costs throughput, never correctness.
 */

export class LruSet {
  // Map preserves insertion order, which is all an LRU needs: re-inserting on
  // hit moves a key to the end, and eviction takes from the front.
  private map = new Map<string, true>();

  constructor(private readonly maxSize: number) {}

  /**
   * Record `key`. Returns true if it was newly added, false if already present.
   * A `false` means "seen recently, skip it".
   */
  add(key: string): boolean {
    if (this.map.has(key)) {
      // Refresh recency so hot domains are not evicted under churn.
      this.map.delete(key);
      this.map.set(key, true);
      return false;
    }

    this.map.set(key, true);
    if (this.map.size > this.maxSize) {
      const oldest = this.map.keys().next();
      if (!oldest.done) this.map.delete(oldest.value);
    }
    return true;
  }

  has(key: string): boolean {
    return this.map.has(key);
  }

  get size(): number {
    return this.map.size;
  }

  clear(): void {
    this.map.clear();
  }
}

export interface DedupeStats {
  seen: number;
  passed: number;
  suppressed: number;
}

/** Wraps an LruSet with counters, so the poller can report its hit rate. */
export class Deduper {
  private lru: LruSet;
  private stats: DedupeStats = { seen: 0, passed: 0, suppressed: 0 };

  constructor(maxSize: number) {
    this.lru = new LruSet(maxSize);
  }

  /** Filter a list of apexes down to those not seen recently. */
  filter(apexes: readonly string[]): string[] {
    const out: string[] = [];
    for (const apex of apexes) {
      this.stats.seen += 1;
      if (this.lru.add(apex)) {
        this.stats.passed += 1;
        out.push(apex);
      } else {
        this.stats.suppressed += 1;
      }
    }
    return out;
  }

  snapshot(): DedupeStats & { cacheSize: number; hitRate: number } {
    return {
      ...this.stats,
      cacheSize: this.lru.size,
      hitRate: this.stats.seen === 0 ? 0 : this.stats.suppressed / this.stats.seen,
    };
  }
}
