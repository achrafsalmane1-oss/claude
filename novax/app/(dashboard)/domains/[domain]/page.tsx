import Link from 'next/link';
import { notFound } from 'next/navigation';
import { eq, desc } from 'drizzle-orm';
import { db, domainDns, domainHttp, domainRdap, domainScores, enrichmentCosts } from '@/db';
import { queryDomain } from '@/api/serialize';
import { requireUser } from '@/auth/session';
import { extractApex } from '@/ingest/apex';

/**
 * Domain detail: the full enrichment trail and the classifier's reason (spec §9).
 *
 * This page is the answer to "why am I seeing this domain?" and to "where did
 * this field come from?" — the provenance requirement in spec §10. Every
 * observation is shown with its timestamp and its source.
 */

export const dynamic = 'force-dynamic';

export default async function DomainDetailPage({ params }: { params: Promise<{ domain: string }> }) {
  await requireUser();
  const { domain: rawDomain } = await params;

  const parsed = extractApex(decodeURIComponent(rawDomain));
  if (!parsed) notFound();

  const domain = await queryDomain(parsed.apex);
  if (!domain) notFound();

  const [dns, http, rdap, scores, costs] = await Promise.all([
    db.select().from(domainDns).where(eq(domainDns.apex, parsed.apex)).orderBy(desc(domainDns.resolvedAt)).limit(10),
    db.select().from(domainHttp).where(eq(domainHttp.apex, parsed.apex)).orderBy(desc(domainHttp.probedAt)).limit(10),
    db.select().from(domainRdap).where(eq(domainRdap.apex, parsed.apex)).orderBy(desc(domainRdap.fetchedAt)).limit(10),
    db.select().from(domainScores).where(eq(domainScores.apex, parsed.apex)).orderBy(desc(domainScores.scoredAt)).limit(10),
    db.select().from(enrichmentCosts).where(eq(enrichmentCosts.apex, parsed.apex)).orderBy(desc(enrichmentCosts.incurredAt)),
  ]);

  const currentScore = scores[0];
  const totalCost = costs.reduce((sum, c) => sum + c.microUsd, 0);

  return (
    <main className="wrap">
      <p className="small">
        <Link href="/domains">← All domains</Link>
      </p>
      <h1>
        {domain.domain}{' '}
        <span className={`tier tier-${domain.tier ?? 'junk'}`}>
          {domain.tier ?? 'unscored'} {domain.score ?? ''}
        </span>
      </h1>
      <p className="muted small">
        <a href={`https://${domain.domain}`} rel="noreferrer nofollow" target="_blank">
          Visit site ↗
        </a>
      </p>

      <h2>Why it surfaced</h2>
      <div className="panel">
        <p style={{ margin: 0 }}>{domain.reason ?? 'Not yet scored.'}</p>
        {currentScore?.classifierReason && (
          <p className="small muted" style={{ marginBottom: 0 }}>
            Classifier ({currentScore.modelVersion}): {currentScore.classifierReason}
          </p>
        )}
        {currentScore?.rulesKillReason && (
          <p className="small muted" style={{ marginBottom: 0 }}>
            Rules verdict: killed as <code>{currentScore.rulesKillReason}</code>
          </p>
        )}
      </div>

      <h2>Company</h2>
      <dl className="kv">
        <dt>Name</dt><dd>{domain.company_name ?? '—'}</dd>
        <dt>Description</dt><dd>{domain.description ?? '—'}</dd>
        <dt>Category</dt><dd>{domain.category ?? '—'}</dd>
        <dt>Stage</dt><dd>{domain.stage ?? '—'}</dd>
        <dt>Country</dt><dd>{domain.country ?? '—'}</dd>
        <dt>Confidence</dt><dd>{domain.confidence ?? '—'}</dd>
      </dl>

      <h2>Signals</h2>
      <dl className="kv">
        <dt>Business email</dt>
        <dd>{domain.has_business_email ? `yes — ${domain.mx_provider}` : (domain.mx_provider ?? 'none configured')}</dd>
        <dt>SPF / DMARC</dt><dd>{domain.has_spf ? 'SPF' : '—'} / {domain.has_dmarc ? 'DMARC' : '—'}</dd>
        <dt>Detected tech</dt><dd>{domain.tech_list || '—'}</dd>
        <dt>Page title</dt><dd>{domain.page_title ?? '—'}</dd>
        <dt>HTTP status</dt><dd>{domain.http_status ?? '—'}</dd>
        <dt>Final URL</dt><dd>{domain.final_url ?? '—'}</dd>
        <dt>Parked</dt><dd>{domain.is_parked ? 'yes' : 'no'}</dd>
        <dt>Registrar</dt><dd>{domain.registrar ?? '—'}</dd>
        <dt>Registered</dt>
        <dd>
          {(domain.registration_date ?? '—').slice(0, 10)}{' '}
          <span className="muted small">(source: {domain.registration_date_source ?? 'unknown'})</span>
        </dd>
        <dt>Nameservers</dt><dd>{domain.nameserver_list || '—'}</dd>
      </dl>

      <h2>Enrichment trail</h2>
      <p className="muted small">
        Every observation, newest first, with the timestamp it was taken. Enrichment cost so far:{' '}
        {totalCost} micro-USD ({(totalCost / 10_000).toFixed(4)} cents).
      </p>

      <h3 className="small muted">DNS</h3>
      <div className="scroll-x">
        <table>
          <thead>
            <tr><th>Resolved at</th><th>A</th><th>MX</th><th>NS</th><th>Changed</th></tr>
          </thead>
          <tbody>
            {dns.map((r) => (
              <tr key={r.id}>
                <td className="small">{r.resolvedAt.toISOString()}</td>
                <td className="small">{r.aRecords.join(', ') || '—'}</td>
                <td className="small">{r.mxRecords.map((m) => m.exchange).join(', ') || '—'}</td>
                <td className="small">{r.nsRecords.join(', ') || '—'}</td>
                <td className="small">{r.nsChanged ? 'nameservers changed' : r.changedFromPrevious ? 'yes' : '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="small muted">HTTP</h3>
      <div className="scroll-x">
        <table>
          <thead>
            <tr><th>Probed at</th><th>Status</th><th>Final URL</th><th>Title</th><th>Parked</th><th>robots</th></tr>
          </thead>
          <tbody>
            {http.map((r) => (
              <tr key={r.id}>
                <td className="small">{r.probedAt.toISOString()}</td>
                <td className="small">{r.statusCode ?? r.lastError ?? '—'}</td>
                <td className="small">{r.finalUrl ?? '—'}</td>
                <td className="small">{r.title ?? '—'}</td>
                <td className="small">{r.isParked ? (r.parkingReason ?? 'yes') : '—'}</td>
                <td className="small">{r.robotsAllowed ? 'allowed' : 'disallowed'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="small muted">RDAP</h3>
      <div className="scroll-x">
        <table>
          <thead>
            <tr><th>Fetched at</th><th>Server</th><th>Registrar</th><th>Created</th><th>Statuses</th><th>Redacted</th></tr>
          </thead>
          <tbody>
            {rdap.map((r) => (
              <tr key={r.id}>
                <td className="small">{r.fetchedAt.toISOString()}</td>
                <td className="small">{r.rdapServer ?? '—'}</td>
                <td className="small">{r.registrar ?? '—'}</td>
                <td className="small">{r.createdDate?.toISOString().slice(0, 10) ?? '—'}</td>
                <td className="small">{r.statuses.join(', ') || '—'}</td>
                <td className="small">{r.hadRedactions ? 'yes' : 'no'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3 className="small muted">Scores</h3>
      <div className="scroll-x">
        <table>
          <thead>
            <tr><th>Scored at</th><th>Score</th><th>Verdict</th><th>Version</th><th>Reason</th></tr>
          </thead>
          <tbody>
            {scores.map((r) => (
              <tr key={r.id}>
                <td className="small">{r.scoredAt.toISOString()}</td>
                <td className="small">{r.score} ({r.tier})</td>
                <td className="small">{r.rulesVerdict}{r.rulesKillReason ? `: ${r.rulesKillReason}` : ''}</td>
                <td className="small">{r.scoringVersion}{r.modelVersion ? ` + ${r.modelVersion}` : ''}</td>
                <td className="small" style={{ maxWidth: 420 }}>{r.reason}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <p className="small muted" style={{ marginTop: 24 }}>
        Own this domain?{' '}
        <a href={`/opt-out?domain=${encodeURIComponent(domain.domain)}`}>Remove it from novaX</a>.
      </p>
    </main>
  );
}
