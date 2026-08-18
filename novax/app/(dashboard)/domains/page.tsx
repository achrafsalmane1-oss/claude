import Link from 'next/link';
import { parseFilters } from '@/api/filters';
import { queryDomains } from '@/api/serialize';
import { requireUser } from '@/auth/session';

/**
 * The filterable table of scored domains (spec §9).
 *
 * Reads through the same `queryDomains` the API uses, so the dashboard and the
 * API can never disagree about what a filter means — or about suppression.
 */

export const dynamic = 'force-dynamic';

interface Props {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

const TIERS = ['', 'hot', 'warm', 'cold', 'junk'];

export default async function DomainsPage({ searchParams }: Props) {
  await requireUser();
  const params = await searchParams;

  const flat: Record<string, string> = {};
  for (const [k, v] of Object.entries(params)) {
    if (typeof v === 'string' && v !== '') flat[k] = v;
  }

  let filters;
  let error: string | null = null;
  try {
    filters = parseFilters({ ...flat, limit: flat['limit'] ?? '50' });
  } catch (err) {
    error = err instanceof Error ? 'Invalid filter values.' : 'Invalid filters.';
    filters = parseFilters({ limit: '50' });
  }

  const result = await queryDomains(filters);
  const exportQuery = new URLSearchParams({ ...flat, limit: '5000' }).toString();

  return (
    <main className="wrap">
      <h1>Scored domains</h1>
      <p className="muted small">
        {result.count} shown. Every row is filtered through the opt-out suppression gate.
      </p>

      {error && <div className="notice error">{error}</div>}

      <form className="filters" method="get">
        <label className="field">
          Min score
          <input name="min_score" type="number" min={0} max={100} defaultValue={flat['min_score'] ?? ''} placeholder="0" />
        </label>
        <label className="field">
          Tier
          <select name="tier" defaultValue={flat['tier'] ?? ''}>
            {TIERS.map((t) => (
              <option key={t} value={t}>
                {t || 'any'}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          TLD
          <input name="tld" defaultValue={flat['tld'] ?? ''} placeholder="com,io" />
        </label>
        <label className="field">
          Category
          <input name="category" defaultValue={flat['category'] ?? ''} placeholder="saas" />
        </label>
        <label className="field">
          Tech
          <input name="tech" defaultValue={flat['tech'] ?? ''} placeholder="shopify" />
        </label>
        <label className="field">
          MX
          <input name="mx_provider" defaultValue={flat['mx_provider'] ?? ''} placeholder="business" />
        </label>
        <label className="field">
          Country
          <input name="country" defaultValue={flat['country'] ?? ''} placeholder="US" />
        </label>
        <label className="field">
          Last N days
          <input name="days" type="number" min={1} defaultValue={flat['days'] ?? ''} placeholder="7" />
        </label>
        <label className="field">
          Search
          <input name="q" defaultValue={flat['q'] ?? ''} placeholder="name or title" />
        </label>
        <button type="submit">Filter</button>
        <a className="small" href={`/api/v1/export?${exportQuery}`}>
          Export CSV
        </a>
      </form>

      <div className="scroll-x">
        <table>
          <thead>
            <tr>
              <th>Domain</th>
              <th>Score</th>
              <th>Company</th>
              <th>Category</th>
              <th>Email</th>
              <th>Tech</th>
              <th>Registered</th>
              <th>Why it surfaced</th>
            </tr>
          </thead>
          <tbody>
            {result.domains.map((d) => (
              <tr key={d.domain}>
                <td>
                  <Link href={`/domains/${encodeURIComponent(d.domain)}`}>{d.domain}</Link>
                </td>
                <td>
                  <span className={`tier tier-${d.tier ?? 'junk'}`}>{d.score ?? '—'}</span>
                </td>
                <td>{d.company_name ?? '—'}</td>
                <td>{d.category ?? '—'}</td>
                <td>{d.mx_provider ?? '—'}</td>
                <td className="small muted">{d.tech_list || '—'}</td>
                <td className="small muted">{(d.registration_date ?? '').slice(0, 10) || '—'}</td>
                <td className="small muted" style={{ maxWidth: 420 }}>
                  {d.reason ?? '—'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {result.domains.length === 0 && (
        <p className="muted small">
          Nothing matches. If the pipeline has only just started, domains appear here once they
          have been enriched and scored.
        </p>
      )}

      {result.nextCursor && (
        <p style={{ marginTop: 16 }}>
          <a href={`/domains?${new URLSearchParams({ ...flat, cursor: result.nextCursor })}`}>
            Next page →
          </a>
        </p>
      )}
    </main>
  );
}
