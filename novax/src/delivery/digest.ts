import { eq, and } from 'drizzle-orm';
import { Resend } from 'resend';
import { db, savedSearches, users, deliveries } from '@/db';
import { env } from '@/config/env';
import { createLogger } from '@/lib/logger';
import { parseFilters } from '@/api/filters';
import { queryDomains, type FlatDomain } from '@/api/serialize';

/**
 * Daily digest email, one per saved search (spec §8).
 *
 * The digest leads with the classifier's reason for each domain, because the
 * reason is what makes the email worth opening — a list of domain names is a
 * list anybody can generate.
 */

const log = createLogger('delivery.digest');

let resend: Resend | null = null;
function getResend(): Resend {
  if (!env.RESEND_API_KEY) throw new Error('RESEND_API_KEY is not set; digests are unavailable');
  resend ??= new Resend(env.RESEND_API_KEY);
  return resend;
}

function escapeHtml(value: string): string {
  return value
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

export function renderDigestHtml(options: {
  searchName: string;
  domains: FlatDomain[];
  baseUrl: string;
}): string {
  const { searchName, domains, baseUrl } = options;

  const rows = domains
    .map((d) => {
      const tierColour =
        d.tier === 'hot' ? '#ff7a45' : d.tier === 'warm' ? '#d19a00' : '#4c8dff';
      return `
      <tr>
        <td style="padding:14px 0;border-bottom:1px solid #e2e6eb;vertical-align:top">
          <div style="font-size:15px;font-weight:600">
            <a href="https://${escapeHtml(d.domain)}" style="color:#11151a;text-decoration:none">${escapeHtml(d.domain)}</a>
            <span style="background:${tierColour};color:#fff;font-size:10px;font-weight:700;padding:2px 7px;border-radius:99px;margin-left:8px;text-transform:uppercase">${escapeHtml(d.tier ?? '')} ${d.score ?? ''}</span>
          </div>
          ${d.company_name ? `<div style="font-size:13px;color:#11151a;margin-top:3px">${escapeHtml(d.company_name)}</div>` : ''}
          <div style="font-size:12px;color:#626d7a;margin-top:5px;line-height:1.5">${escapeHtml((d.reason ?? '').slice(0, 320))}</div>
          <div style="font-size:11px;color:#8b95a3;margin-top:6px">
            ${d.category ? `${escapeHtml(d.category)} &middot; ` : ''}${d.mx_provider ? `${escapeHtml(d.mx_provider)} &middot; ` : ''}${d.tech_list ? `${escapeHtml(d.tech_list)} &middot; ` : ''}${d.country ? `${escapeHtml(d.country)} &middot; ` : ''}registered ${escapeHtml((d.registration_date ?? '').slice(0, 10) || 'unknown')}
          </div>
        </td>
      </tr>`;
    })
    .join('');

  return `<!doctype html>
<html><body style="margin:0;padding:0;background:#f7f8fa;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif">
  <div style="max-width:640px;margin:0 auto;padding:28px 20px">
    <div style="font-size:12px;color:#8b95a3;letter-spacing:0.08em;text-transform:uppercase">novaX daily digest</div>
    <h1 style="font-size:20px;margin:6px 0 2px;color:#11151a">${escapeHtml(searchName)}</h1>
    <p style="font-size:13px;color:#626d7a;margin:0 0 18px">
      ${domains.length} new ${domains.length === 1 ? 'domain' : 'domains'} matched in the last 24 hours.
    </p>
    <table style="width:100%;border-collapse:collapse;background:#fff;border:1px solid #e2e6eb;border-radius:8px;padding:0 16px">
      ${rows}
    </table>
    <p style="font-size:11px;color:#8b95a3;margin-top:20px;line-height:1.6">
      <a href="${escapeHtml(baseUrl)}/domains" style="color:#4c8dff">Open in novaX</a>
      &middot; <a href="${escapeHtml(baseUrl)}/searches" style="color:#4c8dff">Edit this search</a>
      &middot; <a href="${escapeHtml(baseUrl)}/opt-out" style="color:#8b95a3">Domain owner opt-out</a>
    </p>
    <p style="font-size:11px;color:#8b95a3;line-height:1.6">
      novaX reports company-level signals only. We do not include registrant personal data.
    </p>
  </div>
</body></html>`;
}

export function renderDigestText(searchName: string, domains: FlatDomain[]): string {
  const lines = [`novaX daily digest — ${searchName}`, `${domains.length} new domains`, ''];
  for (const d of domains) {
    lines.push(`${d.domain}  [${d.tier ?? '-'} ${d.score ?? '-'}]`);
    if (d.company_name) lines.push(`  ${d.company_name}`);
    if (d.reason) lines.push(`  ${d.reason.slice(0, 300)}`);
    lines.push('');
  }
  return lines.join('\n');
}

export interface DigestResult {
  savedSearchId: number;
  sent: boolean;
  domainCount: number;
  reason?: string;
}

/** Build and send one saved search's digest. */
export async function sendDigest(savedSearchId: number): Promise<DigestResult> {
  const rows = await db
    .select({
      search: savedSearches,
      email: users.email,
    })
    .from(savedSearches)
    .innerJoin(users, eq(users.id, savedSearches.userId))
    .where(and(eq(savedSearches.id, savedSearchId), eq(savedSearches.digestEnabled, true)))
    .limit(1);

  const row = rows[0];
  if (!row) return { savedSearchId, sent: false, domainCount: 0, reason: 'not found or digest disabled' };

  // Only what is new since the last digest — a digest that repeats yesterday's
  // domains stops being read within a week.
  const since = row.search.lastDigestAt ?? new Date(Date.now() - 86_400_000);
  const filters = parseFilters({
    ...(row.search.filters as Record<string, unknown>),
    from: since.toISOString(),
    limit: 50,
  });

  const result = await queryDomains(filters);

  if (result.domains.length === 0) {
    // Silence beats an empty email.
    await db
      .update(savedSearches)
      .set({ lastDigestAt: new Date() })
      .where(eq(savedSearches.id, savedSearchId));
    return { savedSearchId, sent: false, domainCount: 0, reason: 'no new matches' };
  }

  const [delivery] = await db
    .insert(deliveries)
    .values({
      kind: 'digest',
      savedSearchId,
      target: row.email,
      domainCount: result.domains.length,
      status: 'pending',
      payloadSummary: { domains: result.domains.map((d) => d.domain).slice(0, 50) },
    })
    .returning({ id: deliveries.id });

  try {
    await getResend().emails.send({
      from: env.DIGEST_FROM_EMAIL,
      to: row.email,
      subject: `novaX: ${result.domains.length} new ${result.domains.length === 1 ? 'domain' : 'domains'} — ${row.search.name}`,
      html: renderDigestHtml({
        searchName: row.search.name,
        domains: result.domains,
        baseUrl: env.PUBLIC_BASE_URL,
      }),
      text: renderDigestText(row.search.name, result.domains),
    });

    await db
      .update(deliveries)
      .set({ status: 'delivered', deliveredAt: new Date() })
      .where(eq(deliveries.id, delivery!.id));
    await db
      .update(savedSearches)
      .set({ lastDigestAt: new Date() })
      .where(eq(savedSearches.id, savedSearchId));

    log.info('digest sent', { saved_search_id: savedSearchId, domains: result.domains.length });
    return { savedSearchId, sent: true, domainCount: result.domains.length };
  } catch (err) {
    const message = err instanceof Error ? err.message : String(err);
    await db
      .update(deliveries)
      .set({ status: 'failed', error: message })
      .where(eq(deliveries.id, delivery!.id));
    log.error('digest send failed', err, { saved_search_id: savedSearchId });
    return { savedSearchId, sent: false, domainCount: result.domains.length, reason: message };
  }
}

/** Saved searches whose digest hour has arrived and which have not run today. */
export async function digestsDueNow(now = new Date()): Promise<number[]> {
  const hour = now.getUTCHours();
  const rows = await db
    .select({ id: savedSearches.id, lastDigestAt: savedSearches.lastDigestAt })
    .from(savedSearches)
    .where(and(eq(savedSearches.digestEnabled, true), eq(savedSearches.digestHourUtc, hour)));

  const cutoff = new Date(now.getTime() - 20 * 3600 * 1000);
  return rows.filter((r) => !r.lastDigestAt || r.lastDigestAt < cutoff).map((r) => r.id);
}
