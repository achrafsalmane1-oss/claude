import { randomBytes } from 'node:crypto';
import { Resolver } from 'node:dns/promises';
import { eq, sql as raw } from 'drizzle-orm';
import { db, optOuts } from '@/db';
import { env } from '@/config/env';
import { createLogger } from '@/lib/logger';
import { extractApex } from '@/ingest/apex';
import { markSuppressed } from './suppression';

/**
 * Domain owner opt-out (spec §10).
 *
 * Flow:
 *   1. Owner submits their domain, gets a token.
 *   2. Owner publishes `novax-verify=<token>` as a TXT record on the apex.
 *   3. We resolve TXT and, on a match, suppress the domain permanently.
 *
 * Why DNS TXT and not email: anyone can type a domain into a form, so the
 * request itself proves nothing. Email to the registrant is not an option
 * either — that address is redacted in RDAP, which is the entire premise of this
 * product's data model. Publishing a TXT record is the cheapest available proof
 * of actual control.
 */

const log = createLogger('compliance.opt-out');

export const TXT_PREFIX = 'novax-verify=';

export interface OptOutRequest {
  apex: string;
  token: string;
  txtRecord: string;
  alreadyVerified: boolean;
}

/** Create (or return the existing) opt-out request for a domain. */
export async function requestOptOut(
  domainInput: string,
  meta: { email?: string; note?: string } = {},
): Promise<OptOutRequest> {
  const parsed = extractApex(domainInput);
  if (!parsed) throw new Error(`"${domainInput}" is not a valid domain`);
  const apex = parsed.apex;

  const existing = await db.select().from(optOuts).where(eq(optOuts.apex, apex)).limit(1);
  if (existing[0]) {
    return {
      apex,
      token: existing[0].verificationToken,
      txtRecord: `${TXT_PREFIX}${existing[0].verificationToken}`,
      alreadyVerified: existing[0].verifiedAt !== null,
    };
  }

  const token = randomBytes(16).toString('hex');
  await db.insert(optOuts).values({
    apex,
    verificationToken: token,
    // Stored only to confirm the request; never treated as a data field and
    // never exposed through any output path.
    requesterEmail: meta.email ?? null,
    note: meta.note ?? null,
  });

  log.info('opt-out requested', { apex });
  return { apex, token, txtRecord: `${TXT_PREFIX}${token}`, alreadyVerified: false };
}

export interface VerifyResult {
  verified: boolean;
  apex: string;
  reason: string;
}

/**
 * Check the TXT record and suppress on success.
 *
 * Records are matched case-insensitively and checked on both the apex and the
 * conventional `_novax` subdomain, because some DNS panels refuse to put a TXT
 * record on the apex alongside an existing SPF record.
 */
export async function verifyOptOut(apex: string): Promise<VerifyResult> {
  const rows = await db.select().from(optOuts).where(eq(optOuts.apex, apex)).limit(1);
  const record = rows[0];
  if (!record) return { verified: false, apex, reason: 'no opt-out request for this domain' };
  if (record.verifiedAt) return { verified: true, apex, reason: 'already verified' };

  const resolver = new Resolver({ timeout: env.DNS_TIMEOUT_MS, tries: 2 });
  resolver.setServers(env.DNS_SERVERS);

  const expected = `${TXT_PREFIX}${record.verificationToken}`.toLowerCase();

  const collect = async (name: string): Promise<string[]> => {
    try {
      // resolveTxt returns string[][] because a TXT record can be split into
      // multiple character strings which must be concatenated.
      const results = await resolver.resolveTxt(name);
      return results.map((parts) => parts.join('').trim().toLowerCase());
    } catch {
      return [];
    }
  };

  const found = [...(await collect(apex)), ...(await collect(`_novax.${apex}`))];
  const matched = found.some((v) => v === expected);

  await db
    .update(optOuts)
    .set({
      verificationAttempts: raw`${optOuts.verificationAttempts} + 1`,
      lastAttemptedAt: new Date(),
      ...(matched
        ? { verifiedAt: new Date(), lastError: null }
        : { lastError: `TXT record not found (looked for ${expected})` }),
    })
    .where(eq(optOuts.apex, apex));

  if (matched) {
    await markSuppressed(apex);
    log.info('opt-out verified; domain suppressed permanently', { apex });
    return { verified: true, apex, reason: 'TXT record matched; domain suppressed' };
  }

  log.debug('opt-out verification failed', { apex, records_found: found.length });
  return {
    verified: false,
    apex,
    reason:
      found.length === 0
        ? `no TXT records found on ${apex} or _novax.${apex}`
        : 'TXT records found but none matched the verification token',
  };
}

/** Pending (unverified) opt-outs, for the retry job. */
export async function pendingOptOuts(limit = 100) {
  return db
    .select()
    .from(optOuts)
    .where(raw`${optOuts.verifiedAt} is null and ${optOuts.verificationAttempts} < 48`)
    .limit(limit);
}
