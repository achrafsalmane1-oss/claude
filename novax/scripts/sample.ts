/**
 * Dump N random scored domains as CSV, so quality can be eyeballed by hand
 * (spec §11).
 *
 *   npm run sample -- --n=50                     # random scored domains
 *   npm run sample -- --date=2026-08-13 --n=100  # from one feed day
 *   npm run sample -- --n=400 --for-eval         # eval-set template to label
 *
 * `--for-eval` emits the exact column layout `eval/labels.csv` expects, with an
 * empty `label` column for you to fill in with good/garbage.
 */
import { sql as raw } from 'drizzle-orm';
import { sql, db } from '@/db';
import { createLogger } from '@/lib/logger';

const log = createLogger('script.sample');

/** RFC 4180 quoting: wrap in quotes and double any embedded quote. */
function csvEscape(value: unknown): string {
  if (value === null || value === undefined) return '';
  const s = String(value).replace(/\r?\n/g, ' ').trim();
  if (s === '') return '';
  if (/[",]/.test(s)) return `"${s.replace(/"/g, '""')}"`;
  return s;
}

function csvRow(fields: unknown[]): string {
  return fields.map(csvEscape).join(',');
}

async function main() {
  const arg = (name: string) => process.argv.find((a) => a.startsWith(`--${name}=`))?.split('=')[1];
  const n = Number(arg('n') ?? 50);
  const date = arg('date');
  const forEval = process.argv.includes('--for-eval');
  const minScore = arg('min-score');

  const dateFilter = date ? raw`and d.first_seen_at::date <= ${date}::date` : raw``;
  const scoreFilter = minScore ? raw`and s.score >= ${Number(minScore)}` : raw``;
  // For an eval set we want the raw enrichment regardless of score; for a
  // quality spot-check we want things that were actually scored.
  const scoreJoin = forEval ? raw`left join` : raw`inner join`;

  const rows = await db.execute<Record<string, unknown>>(raw`
    select
      d.apex,
      d.tld,
      d.source,
      d.ct_hit_count                                   as ct_hits,
      case when d.registration_date is null then null
           else extract(day from now() - d.registration_date)::int end as age_days,
      coalesce(array_length(array(select jsonb_array_elements(dns.a_records)), 1), 0) > 0 as has_a,
      coalesce(array_length(array(select jsonb_array_elements(dns.mx_records)), 1), 0) > 0 as has_mx,
      dns.mx_provider,
      dns.mx_provider_kind                             as mx_kind,
      dns.has_spf,
      dns.has_dmarc,
      http.status_code                                 as http_status,
      http.is_parked,
      http.parking_vendor,
      http.title,
      http.meta_description,
      left(coalesce(http.body_snippet, ''), 600)       as body_snippet,
      array_to_string(array(select jsonb_array_elements_text(http.tech)), '|') as tech,
      http.redirected_off_domain,
      rdap.registrar,
      rdap.registrant_country,
      s.score,
      s.tier,
      s.reason
    from domains d
    left join domain_dns  dns  on dns.apex  = d.apex and dns.is_current
    left join domain_http http on http.apex = d.apex and http.is_current
    left join domain_rdap rdap on rdap.apex = d.apex and rdap.is_current
    ${scoreJoin} domain_scores s on s.apex = d.apex and s.is_current
    where d.is_suppressed = false
      and d.status in ('enriched', 'scored', 'rejected')
      ${dateFilter}
      ${scoreFilter}
    order by random()
    limit ${n}
  `);

  const header = forEval
    ? [
        'apex', 'tld', 'label', 'notes', 'has_a', 'has_mx', 'mx_provider', 'mx_kind',
        'has_spf', 'has_dmarc', 'http_status', 'is_parked', 'parking_vendor', 'title',
        'meta_description', 'body_snippet', 'tech', 'redirected_off_domain', 'registrar',
        'age_days', 'source', 'ct_hits',
      ]
    : [
        'apex', 'tld', 'score', 'tier', 'reason', 'mx_provider', 'title',
        'meta_description', 'tech', 'registrar', 'registrant_country', 'age_days',
        'is_parked', 'http_status',
      ];

  const out: string[] = [header.join(',')];

  for (const r of rows) {
    out.push(
      csvRow(
        forEval
          ? [
              r['apex'], r['tld'], '', '', r['has_a'], r['has_mx'], r['mx_provider'], r['mx_kind'],
              r['has_spf'], r['has_dmarc'], r['http_status'], r['is_parked'], r['parking_vendor'],
              r['title'], r['meta_description'], r['body_snippet'], r['tech'],
              r['redirected_off_domain'], r['registrar'], r['age_days'], r['source'], r['ct_hits'],
            ]
          : [
              r['apex'], r['tld'], r['score'], r['tier'], r['reason'], r['mx_provider'], r['title'],
              r['meta_description'], r['tech'], r['registrar'], r['registrant_country'],
              r['age_days'], r['is_parked'], r['http_status'],
            ],
      ),
    );
  }

  process.stdout.write(out.join('\n') + '\n');
  // The CSV goes to stdout, so progress reporting must not: a log line here
  // lands in the middle of the file the caller is redirecting.
  process.stderr.write(`# ${rows.length} rows written${forEval ? ' (eval template)' : ''}\n`);
  await sql.end();
}

main().catch(async (err) => {
  log.error('sample failed', err);
  await sql.end().catch(() => {});
  process.exit(1);
});
