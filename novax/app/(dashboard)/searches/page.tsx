import { revalidatePath } from 'next/cache';
import { eq, desc } from 'drizzle-orm';
import { db, savedSearches } from '@/db';
import { requireUser } from '@/auth/session';
import { filterSchema } from '@/api/filters';

/**
 * Saved-search builder (spec §9).
 *
 * The filter set is stored as the same query-parameter object the API accepts,
 * so a saved search is replayable by hand and there is no second filter
 * language to keep in sync.
 */

export const dynamic = 'force-dynamic';

async function createSearch(formData: FormData) {
  'use server';
  const user = await requireUser();

  const name = String(formData.get('name') ?? '').trim();
  if (!name) return;

  // Build the filter object from the individual inputs, dropping blanks.
  const filters: Record<string, string> = {};
  for (const field of ['min_score', 'tier', 'tld', 'category', 'tech', 'mx_provider', 'country', 'days', 'q']) {
    const value = String(formData.get(field) ?? '').trim();
    if (value) filters[field] = value;
  }

  // Validate before storing: a saved search containing an invalid filter would
  // fail silently every night when its digest runs.
  const check = filterSchema.safeParse(filters);
  if (!check.success) return;

  await db.insert(savedSearches).values({
    userId: user.id,
    name,
    filters,
    digestEnabled: formData.get('digest') === 'on',
    digestHourUtc: Number(formData.get('digest_hour') ?? 13),
  });

  revalidatePath('/searches');
}

async function deleteSearch(formData: FormData) {
  'use server';
  await requireUser();
  const id = Number(formData.get('id'));
  if (Number.isFinite(id)) {
    await db.delete(savedSearches).where(eq(savedSearches.id, id));
    revalidatePath('/searches');
  }
}

export default async function SearchesPage() {
  const user = await requireUser();

  const rows = await db
    .select()
    .from(savedSearches)
    .where(eq(savedSearches.userId, user.id))
    .orderBy(desc(savedSearches.createdAt));

  return (
    <main className="wrap">
      <h1>Saved searches</h1>
      <p className="muted small">
        A saved search is a filter set. Enable the digest to receive new matches by email once a day.
      </p>

      <div className="panel" style={{ marginBottom: 24 }}>
        <form action={createSearch} className="filters">
          <label className="field">
            Name
            <input name="name" required placeholder="UK SaaS with business email" />
          </label>
          <label className="field">
            Min score
            <input name="min_score" type="number" min={0} max={100} placeholder="60" />
          </label>
          <label className="field">
            Tier
            <select name="tier" defaultValue="">
              <option value="">any</option>
              <option value="hot">hot</option>
              <option value="warm">warm</option>
              <option value="cold">cold</option>
            </select>
          </label>
          <label className="field">
            TLD
            <input name="tld" placeholder="com,io" />
          </label>
          <label className="field">
            Category
            <input name="category" placeholder="saas" />
          </label>
          <label className="field">
            Tech
            <input name="tech" placeholder="shopify" />
          </label>
          <label className="field">
            MX
            <input name="mx_provider" placeholder="business" />
          </label>
          <label className="field">
            Country
            <input name="country" placeholder="GB" />
          </label>
          <label className="field">
            Digest hour (UTC)
            <input name="digest_hour" type="number" min={0} max={23} defaultValue={13} />
          </label>
          <label className="field">
            Daily digest
            <input name="digest" type="checkbox" />
          </label>
          <button type="submit">Save search</button>
        </form>
      </div>

      <div className="scroll-x">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Filters</th>
              <th>Digest</th>
              <th>Last sent</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => {
              const query = new URLSearchParams(r.filters as Record<string, string>).toString();
              return (
                <tr key={r.id}>
                  <td>
                    <a href={`/domains?${query}`}>{r.name}</a>
                  </td>
                  <td className="small muted">{query || 'no filters'}</td>
                  <td className="small">{r.digestEnabled ? `daily at ${r.digestHourUtc}:00 UTC` : 'off'}</td>
                  <td className="small muted">{r.lastDigestAt?.toISOString().slice(0, 16) ?? '—'}</td>
                  <td>
                    <form action={deleteSearch}>
                      <input type="hidden" name="id" value={r.id} />
                      <button className="secondary small" type="submit">
                        Delete
                      </button>
                    </form>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {rows.length === 0 && <p className="muted small">No saved searches yet.</p>}
    </main>
  );
}
