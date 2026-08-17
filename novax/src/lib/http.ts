import { request, Agent, interceptors, type Dispatcher } from 'undici';
import { USER_AGENT, env } from '@/config/env';

/**
 * Outbound HTTP.
 *
 * Every request novaX makes to the outside world goes through here so that the
 * identifying User-Agent required by spec §10 cannot be forgotten, and so that
 * timeouts and body size caps are uniform. An unbounded read of a hostile page
 * is how a probe worker dies.
 */

const agent = new Agent({
  connectTimeout: 5_000,
  headersTimeout: 15_000,
  bodyTimeout: 20_000,
  // Enough sockets for the probe concurrency without exhausting file handles.
  connections: 128,
});

/**
 * undici v7 removed the per-request `maxRedirections` option in favour of an
 * interceptor. `fetchWithLimits` follows redirects by hand (it needs the chain
 * length and final URL), so only the bulk fetcher needs this.
 */
const redirectingAgent = agent.compose(interceptors.redirect({ maxRedirections: 5 }));

export interface FetchOptions {
  method?: 'GET' | 'POST' | 'HEAD';
  headers?: Record<string, string>;
  body?: string;
  timeoutMs?: number;
  maxBytes?: number;
  /** Number of redirects to follow. 0 means return the 3xx as-is. */
  maxRedirects?: number;
  signal?: AbortSignal;
  dispatcher?: Dispatcher;
}

export interface FetchResult {
  statusCode: number;
  headers: Record<string, string>;
  /** Decoded body, truncated at `maxBytes`. */
  body: string;
  bodyBytes: number;
  /** True when the body hit the cap and was cut short. */
  truncated: boolean;
  finalUrl: string;
  redirectCount: number;
  elapsedMs: number;
}

export class HttpError extends Error {
  constructor(
    message: string,
    readonly statusCode?: number,
  ) {
    super(message);
    this.name = 'HttpError';
  }
}

function headerString(v: string | string[] | undefined): string | undefined {
  if (v === undefined) return undefined;
  return Array.isArray(v) ? v.join(', ') : v;
}

/**
 * Fetch with a hard timeout, a hard body cap, and manual redirect handling so
 * we can record the redirect chain length and the final URL.
 */
export async function fetchWithLimits(url: string, options: FetchOptions = {}): Promise<FetchResult> {
  const {
    method = 'GET',
    headers = {},
    body,
    timeoutMs = env.HTTP_PROBE_TIMEOUT_MS,
    maxBytes = env.HTTP_PROBE_MAX_BYTES,
    maxRedirects = 0,
    signal,
    dispatcher,
  } = options;

  const started = Date.now();
  let currentUrl = url;
  let redirectCount = 0;

  while (true) {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), timeoutMs);
    const onAbort = () => controller.abort();
    signal?.addEventListener('abort', onAbort, { once: true });

    try {
      const res = await request(currentUrl, {
        method,
        headers: { 'user-agent': USER_AGENT, accept: '*/*', ...headers },
        ...(body !== undefined ? { body } : {}),
        signal: controller.signal,
        // We follow redirects ourselves, so the plain agent (no redirect
        // interceptor) is what we want here.
        dispatcher: dispatcher ?? agent,
      });

      const resHeaders: Record<string, string> = {};
      for (const [k, v] of Object.entries(res.headers)) {
        const s = headerString(v as string | string[] | undefined);
        if (s !== undefined) resHeaders[k.toLowerCase()] = s;
      }

      // --- Redirect handling ---
      const isRedirect = res.statusCode >= 300 && res.statusCode < 400;
      const location = resHeaders['location'];
      if (isRedirect && location && redirectCount < maxRedirects) {
        // Drain so the socket returns to the pool.
        await res.body.dump();
        redirectCount += 1;
        try {
          currentUrl = new URL(location, currentUrl).toString();
        } catch {
          throw new HttpError(`invalid redirect target: ${location}`, res.statusCode);
        }
        continue;
      }

      // --- Bounded body read ---
      const chunks: Buffer[] = [];
      let total = 0;
      let truncated = false;
      for await (const chunk of res.body) {
        const buf = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
        total += buf.length;
        if (total > maxBytes) {
          chunks.push(buf.subarray(0, buf.length - (total - maxBytes)));
          truncated = true;
          break;
        }
        chunks.push(buf);
      }
      if (truncated) {
        // Abandon the rest of the response rather than reading a hostile page.
        await res.body.dump().catch(() => {});
      }

      return {
        statusCode: res.statusCode,
        headers: resHeaders,
        body: Buffer.concat(chunks).toString('utf8'),
        bodyBytes: Math.min(total, maxBytes),
        truncated,
        finalUrl: currentUrl,
        redirectCount,
        elapsedMs: Date.now() - started,
      };
    } catch (err) {
      if (controller.signal.aborted) {
        throw new HttpError(`timeout after ${timeoutMs}ms fetching ${currentUrl}`);
      }
      throw err instanceof HttpError ? err : new HttpError(`fetch failed: ${String(err)}`);
    } finally {
      clearTimeout(timer);
      signal?.removeEventListener('abort', onAbort);
    }
  }
}

/** Fetch and JSON-parse, with a clear error when the response is not JSON. */
export async function fetchJson<T>(url: string, options: FetchOptions = {}): Promise<T> {
  const res = await fetchWithLimits(url, {
    maxBytes: 32 * 1024 * 1024,
    maxRedirects: 3,
    ...options,
    headers: { accept: 'application/json', ...options.headers },
  });
  if (res.statusCode < 200 || res.statusCode >= 300) {
    throw new HttpError(`HTTP ${res.statusCode} from ${url}`, res.statusCode);
  }
  try {
    return JSON.parse(res.body) as T;
  } catch {
    throw new HttpError(`non-JSON response from ${url}: ${res.body.slice(0, 200)}`, res.statusCode);
  }
}

/** Fetch raw bytes (for the NRD zip). Separate cap since feeds are multi-MB. */
export async function fetchBuffer(
  url: string,
  options: FetchOptions & { maxBytes?: number } = {},
): Promise<{ buffer: Buffer; statusCode: number; headers: Record<string, string> }> {
  const maxBytes = options.maxBytes ?? 512 * 1024 * 1024;
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), options.timeoutMs ?? 120_000);
  try {
    const res = await request(url, {
      method: options.method ?? 'GET',
      headers: { 'user-agent': USER_AGENT, ...options.headers },
      signal: controller.signal,
      dispatcher: redirectingAgent,
    });

    const chunks: Buffer[] = [];
    let total = 0;
    for await (const chunk of res.body) {
      const buf = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk);
      total += buf.length;
      if (total > maxBytes) throw new HttpError(`response exceeded ${maxBytes} bytes`);
      chunks.push(buf);
    }

    const headers: Record<string, string> = {};
    for (const [k, v] of Object.entries(res.headers)) {
      const s = headerString(v as string | string[] | undefined);
      if (s !== undefined) headers[k.toLowerCase()] = s;
    }

    return { buffer: Buffer.concat(chunks), statusCode: res.statusCode, headers };
  } finally {
    clearTimeout(timer);
  }
}

export async function closeHttp(): Promise<void> {
  await agent.close();
}
