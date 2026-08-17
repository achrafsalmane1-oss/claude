import { NextResponse } from 'next/server';
import { authenticate, recordUsage, type AuthenticatedKey } from './auth';
import { checkRateLimit, rateLimitHeaders } from './rate-limit';
import { createLogger } from '@/lib/logger';

/**
 * Shared plumbing for every authenticated v1 endpoint: key auth, rate limiting,
 * usage accounting, error shaping and timing.
 *
 * Wrapping it here rather than repeating it per route is what stops the fourth
 * endpoint someone adds from quietly skipping the rate limiter.
 */

const log = createLogger('api');

export interface ApiContext {
  key: AuthenticatedKey;
  request: Request;
  url: URL;
}

export type ApiHandler = (ctx: ApiContext) => Promise<{
  body: unknown;
  rowsReturned?: number;
  headers?: Record<string, string>;
  status?: number;
}>;

const AUTH_HELP =
  'Provide your key as "Authorization: Bearer nvx_live_..." or "X-API-Key: nvx_live_...".';

export function withApiAuth(handler: ApiHandler) {
  return async (request: Request): Promise<Response> => {
    const started = Date.now();
    const url = new URL(request.url);

    const key = await authenticate(request.headers);
    if (!key) {
      return NextResponse.json(
        { error: 'unauthorized', message: `Missing or invalid API key. ${AUTH_HELP}` },
        { status: 401 },
      );
    }

    const limit = await checkRateLimit(key);
    if (!limit.allowed) {
      log.warn('rate limited', { key_id: key.id, window: limit.window });
      return NextResponse.json(
        {
          error: 'rate_limited',
          message: `Rate limit of ${limit.limit} requests per ${limit.window} exceeded. Retry in ${limit.resetSeconds}s.`,
        },
        { status: 429, headers: rateLimitHeaders(limit) },
      );
    }

    try {
      const result = await handler({ key, request, url });
      await recordUsage(key.id, result.rowsReturned ?? 0);

      const elapsed = Date.now() - started;
      log.info('api request', {
        key_id: key.id,
        path: url.pathname,
        rows: result.rowsReturned ?? 0,
        ms: elapsed,
      });

      return NextResponse.json(result.body, {
        status: result.status ?? 200,
        headers: {
          ...rateLimitHeaders(limit),
          'X-Response-Time-Ms': String(elapsed),
          ...(result.headers ?? {}),
        },
      });
    } catch (err) {
      // A Zod failure is the caller's problem and should say what was wrong.
      const isValidation = err instanceof Error && err.name === 'ZodError';
      if (isValidation) {
        return NextResponse.json(
          { error: 'invalid_request', message: 'Invalid query parameters', detail: JSON.parse((err as Error).message) },
          { status: 400, headers: rateLimitHeaders(limit) },
        );
      }

      log.error('api request failed', err, { key_id: key.id, path: url.pathname });
      return NextResponse.json(
        { error: 'internal_error', message: 'Something went wrong handling this request.' },
        { status: 500, headers: rateLimitHeaders(limit) },
      );
    }
  };
}
