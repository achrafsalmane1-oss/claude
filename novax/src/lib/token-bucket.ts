/**
 * Per-key token bucket rate limiter.
 *
 * RDAP registries rate-limit per source IP and will ban a caller that hammers
 * them. This keeps us to a documented, polite rate per registry.
 */

interface Bucket {
  tokens: number;
  lastRefill: number;
}

export class TokenBucket {
  private buckets = new Map<string, Bucket>();

  constructor(
    private readonly ratePerSecond: number,
    private readonly burst: number,
  ) {}

  /** Milliseconds the caller must wait before a token is available. 0 = go now. */
  private reserve(key: string): number {
    const now = Date.now();
    let b = this.buckets.get(key);
    if (!b) {
      b = { tokens: this.burst, lastRefill: now };
      this.buckets.set(key, b);
    }

    const elapsedSec = (now - b.lastRefill) / 1000;
    if (elapsedSec > 0) {
      b.tokens = Math.min(this.burst, b.tokens + elapsedSec * this.ratePerSecond);
      b.lastRefill = now;
    }

    if (b.tokens >= 1) {
      b.tokens -= 1;
      return 0;
    }

    const deficit = 1 - b.tokens;
    // Consume ahead so concurrent callers queue behind each other rather than
    // all being told to wait the same amount and then all firing at once.
    b.tokens -= 1;
    return Math.ceil((deficit / this.ratePerSecond) * 1000);
  }

  /** Resolves when the caller is allowed to make a request against `key`. */
  async acquire(key: string): Promise<void> {
    const waitMs = this.reserve(key);
    if (waitMs > 0) await new Promise((r) => setTimeout(r, waitMs));
  }

  /** Drop buckets untouched for an hour so long-lived processes don't leak. */
  prune(maxAgeMs = 3_600_000): void {
    const cutoff = Date.now() - maxAgeMs;
    for (const [key, b] of this.buckets) {
      if (b.lastRefill < cutoff) this.buckets.delete(key);
    }
  }
}
