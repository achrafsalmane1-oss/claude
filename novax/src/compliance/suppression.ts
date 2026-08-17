import { eq, and, isNotNull, type SQL } from 'drizzle-orm';
import { db, domains, optOuts } from '@/db';

/**
 * The suppression gate.
 *
 * A verified opt-out means the apex is excluded from **every** output path:
 * API, CSV, webhooks, digests, dashboard. A compliance control with two code
 * paths has one code path that is wrong, so every read of scored domains goes
 * through `suppressionCondition()` and nothing else.
 *
 * `domains.is_suppressed` is denormalised from `opt_outs` so the filter is a
 * single-table predicate on the query's hot path; `markSuppressed()` is the only
 * writer and it sets both.
 */

/** The predicate every output query must include. */
export function suppressionCondition(): SQL {
  return eq(domains.isSuppressed, false);
}

/**
 * Compose a caller's filters with the suppression gate.
 * Written so a caller cannot accidentally build a query that omits it.
 */
export function applySuppression(...conditions: (SQL | undefined)[]): SQL {
  const all = [suppressionCondition(), ...conditions.filter((c): c is SQL => c !== undefined)];
  // `and` returns undefined only for an empty list, which cannot happen here.
  return and(...all)!;
}

/** Flip a domain to suppressed. Called after an opt-out verifies. */
export async function markSuppressed(apex: string): Promise<void> {
  await db
    .update(domains)
    .set({ isSuppressed: true, updatedAt: new Date() })
    .where(eq(domains.apex, apex));
}

/**
 * Rebuild the denormalised flag from `opt_outs`.
 * Run after a restore, or on a schedule, to guarantee the two agree.
 */
export async function reconcileSuppression(): Promise<number> {
  const verified = await db
    .select({ apex: optOuts.apex })
    .from(optOuts)
    .where(isNotNull(optOuts.verifiedAt));

  let updated = 0;
  for (const row of verified) {
    const result = await db
      .update(domains)
      .set({ isSuppressed: true, updatedAt: new Date() })
      .where(and(eq(domains.apex, row.apex), eq(domains.isSuppressed, false)))
      .returning({ id: domains.id });
    updated += result.length;
  }
  return updated;
}

/** True when this apex must not appear in any output. */
export async function isSuppressed(apex: string): Promise<boolean> {
  const rows = await db
    .select({ suppressed: domains.isSuppressed })
    .from(domains)
    .where(eq(domains.apex, apex))
    .limit(1);
  return rows[0]?.suppressed ?? false;
}
