/**
 * Exponential backoff with full jitter.
 *
 * Used by the CT poller (spec §5b requires reconnection with exponential backoff)
 * and by webhook delivery retries.
 */

export interface BackoffOptions {
  baseMs?: number;
  maxMs?: number;
  factor?: number;
}

/** Delay for attempt `n` (0-indexed), with full jitter to avoid thundering herds. */
export function backoffDelay(attempt: number, opts: BackoffOptions = {}): number {
  const { baseMs = 1_000, maxMs = 300_000, factor = 2 } = opts;
  const ceiling = Math.min(maxMs, baseMs * factor ** Math.max(0, attempt));
  return Math.floor(Math.random() * ceiling);
}

export function sleep(ms: number, signal?: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) return reject(new Error('aborted'));
    const t = setTimeout(resolve, ms);
    signal?.addEventListener(
      'abort',
      () => {
        clearTimeout(t);
        reject(new Error('aborted'));
      },
      { once: true },
    );
  });
}

/** Retry an async operation with exponential backoff. Rethrows the last error. */
export async function withRetry<T>(
  fn: (attempt: number) => Promise<T>,
  opts: BackoffOptions & { attempts?: number; onRetry?: (attempt: number, err: unknown) => void } = {},
): Promise<T> {
  const { attempts = 4, onRetry, ...backoff } = opts;
  let lastError: unknown;
  for (let attempt = 0; attempt < attempts; attempt++) {
    try {
      return await fn(attempt);
    } catch (err) {
      lastError = err;
      if (attempt === attempts - 1) break;
      onRetry?.(attempt, err);
      await sleep(backoffDelay(attempt, backoff));
    }
  }
  throw lastError;
}

/** Run `items` through `fn` with bounded concurrency, preserving input order. */
export async function mapLimit<T, R>(
  items: readonly T[],
  limit: number,
  fn: (item: T, index: number) => Promise<R>,
): Promise<R[]> {
  const results = new Array<R>(items.length);
  let cursor = 0;
  const workers = Array.from({ length: Math.max(1, Math.min(limit, items.length)) }, async () => {
    while (true) {
      const i = cursor++;
      if (i >= items.length) return;
      results[i] = await fn(items[i]!, i);
    }
  });
  await Promise.all(workers);
  return results;
}
