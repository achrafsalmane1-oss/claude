import { Resolver } from 'node:dns/promises';
import { eq, and, inArray, sql as raw } from 'drizzle-orm';
import { db, domains, domainDns } from '@/db';
import { env } from '@/config/env';
import { createLogger } from '@/lib/logger';
import { mapLimit } from '@/lib/backoff';
import { classifyMx, type MxRecord } from './mx';

/**
 * DNS resolution — the cheapest check, and therefore the first gate (spec §6.1).
 *
 * "If no A record and no MX, the domain is unconfigured — park it in a
 * low-priority requeue for 72h and stop." That single rule removes the large
 * majority of a day's feed before anything expensive runs, which is what makes
 * the unit economics work.
 *
 * Observations are append-only: nameserver changes are themselves a signal
 * (spec §4), so a re-resolve never overwrites the previous row.
 */

const log = createLogger('enrich.dns');

export interface DnsObservation {
  apex: string;
  a: string[];
  aaaa: string[];
  mx: MxRecord[];
  ns: string[];
  txt: string[];
  hasSpf: boolean;
  hasDmarc: boolean;
  error?: string;
}

function createResolver(): Resolver {
  const resolver = new Resolver({ timeout: env.DNS_TIMEOUT_MS, tries: 2 });
  resolver.setServers(env.DNS_SERVERS);
  return resolver;
}

/** Resolve one name, treating "no such record" as empty rather than an error. */
async function tryResolve<T>(fn: () => Promise<T>, fallback: T): Promise<T> {
  try {
    return await fn();
  } catch (err) {
    const code = (err as NodeJS.ErrnoException).code;
    // ENODATA/ENOTFOUND mean the record type does not exist, which is a valid
    // answer. Anything else (SERVFAIL, timeout) is a genuine failure and we
    // still degrade to the fallback rather than failing the whole domain.
    if (code !== 'ENODATA' && code !== 'ENOTFOUND') {
      log.debug('dns query failed', { code, error: String(err) });
    }
    return fallback;
  }
}

/** Resolve every record type we care about for one apex. */
export async function resolveDomain(apex: string, resolver = createResolver()): Promise<DnsObservation> {
  const [a, aaaa, mxRaw, ns, txtRaw, dmarcRaw] = await Promise.all([
    tryResolve(() => resolver.resolve4(apex), [] as string[]),
    tryResolve(() => resolver.resolve6(apex), [] as string[]),
    tryResolve(() => resolver.resolveMx(apex), [] as { exchange: string; priority: number }[]),
    tryResolve(() => resolver.resolveNs(apex), [] as string[]),
    tryResolve(() => resolver.resolveTxt(apex), [] as string[][]),
    // DMARC lives at _dmarc.<domain>, not on the apex.
    tryResolve(() => resolver.resolveTxt(`_dmarc.${apex}`), [] as string[][]),
  ]);

  // A TXT record can be split into multiple character strings that must be
  // concatenated before interpretation.
  const txt = txtRaw.map((parts) => parts.join(''));
  const dmarc = dmarcRaw.map((parts) => parts.join(''));

  return {
    apex,
    a,
    aaaa,
    mx: mxRaw.map((r) => ({ exchange: r.exchange.toLowerCase().replace(/\.$/, ''), priority: r.priority })),
    ns: ns.map((n) => n.toLowerCase().replace(/\.$/, '')),
    // We store TXT records because SPF/DKIM presence is a signal, but the
    // booleans below are what the pipeline actually reads.
    txt,
    hasSpf: txt.some((t) => t.toLowerCase().startsWith('v=spf1')),
    hasDmarc: dmarc.some((t) => t.toLowerCase().startsWith('v=dmarc1')),
  };
}

export interface DnsGateResult {
  apex: string;
  /** True when the domain has an A/AAAA record or an MX record. */
  passed: boolean;
  observation: DnsObservation;
  mxProvider: string | null;
  mxKind: string;
}

/**
 * Resolve a batch and persist the observations.
 *
 * Batched deliberately: one queue job per 500 apexes rather than one per apex
 * keeps pg-boss at hundreds of jobs a day instead of hundreds of thousands.
 */
export async function resolveBatch(apexes: string[]): Promise<DnsGateResult[]> {
  if (apexes.length === 0) return [];
  const resolver = createResolver();
  const started = Date.now();

  const observations = await mapLimit(apexes, env.DNS_CONCURRENCY, (apex) =>
    resolveDomain(apex, resolver),
  );

  const results: DnsGateResult[] = [];

  // Previous observations, so we can flag nameserver changes.
  const previous = await db
    .select({ apex: domainDns.apex, ns: domainDns.nsRecords, mx: domainDns.mxRecords })
    .from(domainDns)
    .where(and(inArray(domainDns.apex, apexes), eq(domainDns.isCurrent, true)));
  const previousByApex = new Map(previous.map((p) => [p.apex, p]));

  for (const obs of observations) {
    const mxClass = classifyMx(obs.mx);
    const passed = obs.a.length > 0 || obs.aaaa.length > 0 || obs.mx.length > 0;

    const prev = previousByApex.get(obs.apex);
    const nsChanged =
      prev !== undefined && JSON.stringify([...prev.ns].sort()) !== JSON.stringify([...obs.ns].sort());
    const changed =
      prev !== undefined &&
      (nsChanged ||
        JSON.stringify(prev.mx.map((m) => m.exchange).sort()) !==
          JSON.stringify(obs.mx.map((m) => m.exchange).sort()));

    // Retire the previous current row before inserting the new one, so the
    // partial unique index on (apex) where is_current always holds.
    if (prev) {
      await db
        .update(domainDns)
        .set({ isCurrent: false })
        .where(and(eq(domainDns.apex, obs.apex), eq(domainDns.isCurrent, true)));
    }

    await db.insert(domainDns).values({
      apex: obs.apex,
      aRecords: obs.a,
      aaaaRecords: obs.aaaa,
      mxRecords: obs.mx,
      nsRecords: obs.ns,
      txtRecords: obs.txt,
      hasSpf: obs.hasSpf,
      hasDmarc: obs.hasDmarc,
      mxProvider: mxClass.provider,
      mxProviderKind: mxClass.kind,
      changedFromPrevious: changed,
      nsChanged,
      isCurrent: true,
    });

    results.push({
      apex: obs.apex,
      passed,
      observation: obs,
      mxProvider: mxClass.provider,
      mxKind: mxClass.kind,
    });
  }

  // --- Apply the gate -----------------------------------------------------
  const passedApexes = results.filter((r) => r.passed).map((r) => r.apex);
  const failedApexes = results.filter((r) => !r.passed).map((r) => r.apex);

  if (passedApexes.length > 0) {
    await db
      .update(domains)
      .set({ status: 'enriching', requeueAfter: null, updatedAt: new Date() })
      .where(inArray(domains.apex, passedApexes));
  }

  if (failedApexes.length > 0) {
    // Unconfigured: check again in 72h. Many domains are registered days before
    // anything is pointed at them, so this is a "not yet", not a "no".
    const requeueAt = new Date(Date.now() + 72 * 3600 * 1000);
    await db
      .update(domains)
      .set({ status: 'unconfigured', requeueAfter: requeueAt, updatedAt: new Date() })
      .where(inArray(domains.apex, failedApexes));
  }

  log.info('dns batch resolved', {
    batch: apexes.length,
    passed: passedApexes.length,
    unconfigured: failedApexes.length,
    gate_kill_rate: apexes.length === 0 ? 0 : failedApexes.length / apexes.length,
    ms: Date.now() - started,
  });

  return results;
}

/**
 * Claim the next batch of domains needing DNS, oldest first.
 *
 * One statement, with `FOR UPDATE SKIP LOCKED`, so two workers racing for work
 * cannot claim the same rows. Doing this as a SELECT followed by an UPDATE
 * would look fine in development and double-resolve in production.
 *
 * Suppressed domains are excluded here as well as at read time — there is no
 * reason to spend enrichment budget on a domain we may never output.
 */
export async function claimDomainsForDns(limit: number): Promise<string[]> {
  const rows = await db.execute<{ apex: string }>(raw`
    update domains
       set status = 'dns_pending', updated_at = now()
     where id in (
       select id from domains
        where is_suppressed = false
          and (
            status in ('discovered', 'dns_pending')
            or (status = 'unconfigured' and requeue_after <= now())
          )
        order by first_seen_at
        limit ${limit}
        for update skip locked
     )
    returning apex
  `);

  return [...rows].map((r) => r.apex);
}
