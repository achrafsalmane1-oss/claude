import { createHash, randomBytes, timingSafeEqual } from 'node:crypto';
import { eq, and, isNull, or, gt, sql as raw } from 'drizzle-orm';
import { db, apiKeys } from '@/db';
import { createLogger } from '@/lib/logger';

/**
 * API key authentication.
 *
 * Keys are machine credentials with a different lifetime and blast radius from
 * a human session, so they are a separate mechanism rather than a reused
 * cookie — and a cookie would be unusable from Clay, which is the channel this
 * API exists to serve.
 *
 * Only a SHA-256 hash of the key is stored. A database leak therefore leaks no
 * working credentials. SHA-256 rather than a password hash is the right call
 * here: the key is 32 bytes of CSPRNG output, so there is no dictionary to
 * attack and the lookup has to be fast enough to run on every request.
 */

const log = createLogger('api.auth');

const KEY_PREFIX = 'nvx_live_';

export interface IssuedKey {
  /** Shown to the user exactly once. */
  key: string;
  id: number;
  prefix: string;
}

export function hashKey(key: string): string {
  return createHash('sha256').update(key, 'utf8').digest('hex');
}

/** Mint a new key. The plaintext is returned once and never stored. */
export async function issueApiKey(options: {
  name: string;
  userId?: string | null;
  rateLimitPerMinute?: number;
  rateLimitPerDay?: number;
  expiresAt?: Date | null;
}): Promise<IssuedKey> {
  const secret = randomBytes(32).toString('base64url');
  const key = `${KEY_PREFIX}${secret}`;
  const prefix = key.slice(0, 16);

  const rows = await db
    .insert(apiKeys)
    .values({
      name: options.name,
      userId: options.userId ?? null,
      keyHash: hashKey(key),
      keyPrefix: prefix,
      ...(options.rateLimitPerMinute ? { rateLimitPerMinute: options.rateLimitPerMinute } : {}),
      ...(options.rateLimitPerDay ? { rateLimitPerDay: options.rateLimitPerDay } : {}),
      expiresAt: options.expiresAt ?? null,
    })
    .returning({ id: apiKeys.id });

  log.info('api key issued', { id: rows[0]!.id, name: options.name, prefix });
  return { key, id: rows[0]!.id, prefix };
}

export interface AuthenticatedKey {
  id: number;
  name: string;
  userId: string | null;
  rateLimitPerMinute: number;
  rateLimitPerDay: number;
}

/**
 * Resolve an Authorization header to a key record.
 *
 * Accepts `Authorization: Bearer <key>` and the bare `X-API-Key: <key>` form,
 * because Clay's HTTP column makes the second easier to configure.
 */
export function extractKey(headers: Headers): string | null {
  const authorization = headers.get('authorization');
  if (authorization) {
    const match = /^Bearer\s+(.+)$/i.exec(authorization.trim());
    if (match?.[1]) return match[1].trim();
    // Tolerate a bare key in the Authorization header.
    if (authorization.startsWith(KEY_PREFIX)) return authorization.trim();
  }
  const header = headers.get('x-api-key');
  return header?.trim() || null;
}

export async function authenticate(headers: Headers): Promise<AuthenticatedKey | null> {
  const key = extractKey(headers);
  if (!key || !key.startsWith(KEY_PREFIX)) return null;

  const hash = hashKey(key);
  const rows = await db
    .select({
      id: apiKeys.id,
      name: apiKeys.name,
      userId: apiKeys.userId,
      keyHash: apiKeys.keyHash,
      rateLimitPerMinute: apiKeys.rateLimitPerMinute,
      rateLimitPerDay: apiKeys.rateLimitPerDay,
    })
    .from(apiKeys)
    .where(
      and(
        eq(apiKeys.keyHash, hash),
        isNull(apiKeys.revokedAt),
        or(isNull(apiKeys.expiresAt), gt(apiKeys.expiresAt, new Date())),
      ),
    )
    .limit(1);

  const record = rows[0];
  if (!record) return null;

  // The unique index already made this an exact-match lookup; the constant-time
  // compare is belt and braces against any future change to that query.
  const a = Buffer.from(hash, 'utf8');
  const b = Buffer.from(record.keyHash, 'utf8');
  if (a.length !== b.length || !timingSafeEqual(a, b)) return null;

  return {
    id: record.id,
    name: record.name,
    userId: record.userId,
    rateLimitPerMinute: record.rateLimitPerMinute,
    rateLimitPerDay: record.rateLimitPerDay,
  };
}

/** Usage accounting, per spec §8: counted from day one. */
export async function recordUsage(keyId: number, rowsReturned: number): Promise<void> {
  await db
    .update(apiKeys)
    .set({
      totalRequests: raw`${apiKeys.totalRequests} + 1`,
      totalRowsReturned: raw`${apiKeys.totalRowsReturned} + ${rowsReturned}`,
      lastUsedAt: new Date(),
    })
    .where(eq(apiKeys.id, keyId));
}

export async function revokeApiKey(id: number): Promise<void> {
  await db.update(apiKeys).set({ revokedAt: new Date() }).where(eq(apiKeys.id, id));
  log.info('api key revoked', { id });
}
