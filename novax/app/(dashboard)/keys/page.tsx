import { revalidatePath } from 'next/cache';
import { eq, desc } from 'drizzle-orm';
import { db, apiKeys } from '@/db';
import { requireUser } from '@/auth/session';
import { issueApiKey, revokeApiKey } from '@/api/auth';
import { env } from '@/config/env';

/**
 * API key management (spec §9).
 *
 * The plaintext key is shown exactly once, immediately after creation, and is
 * never recoverable — only its SHA-256 hash is stored.
 */

export const dynamic = 'force-dynamic';

async function createKey(formData: FormData) {
  'use server';
  const { redirect } = await import('next/navigation');
  const user = await requireUser();

  const name = String(formData.get('name') ?? '').trim() || 'Unnamed key';
  const issued = await issueApiKey({ name, userId: user.id });

  // Round-trip through the URL so the key survives exactly one render and is
  // not held in any server-side state.
  redirect(`/keys?new=${encodeURIComponent(issued.key)}`);
}

async function revoke(formData: FormData) {
  'use server';
  await requireUser();
  const id = Number(formData.get('id'));
  if (Number.isFinite(id)) {
    await revokeApiKey(id);
    revalidatePath('/keys');
  }
}

export default async function KeysPage({
  searchParams,
}: {
  searchParams: Promise<{ new?: string }>;
}) {
  const user = await requireUser();
  const params = await searchParams;

  const rows = await db
    .select()
    .from(apiKeys)
    .where(eq(apiKeys.userId, user.id))
    .orderBy(desc(apiKeys.createdAt));

  return (
    <main className="wrap">
      <h1>API keys</h1>
      <p className="muted small">
        Use a key with <code>X-API-Key</code> or <code>Authorization: Bearer</code>. Keys are stored
        hashed and cannot be recovered — if one is lost, revoke it and issue another.
      </p>

      {params.new && (
        <div className="notice ok">
          <strong>New key — copy it now, it will not be shown again:</strong>
          <pre style={{ marginBottom: 0 }}>{params.new}</pre>
        </div>
      )}

      <div className="panel" style={{ marginBottom: 24 }}>
        <form action={createKey} className="filters">
          <label className="field">
            Name
            <input name="name" placeholder="Clay table" required />
          </label>
          <button type="submit">Create key</button>
        </form>
      </div>

      <div className="scroll-x">
        <table>
          <thead>
            <tr>
              <th>Name</th>
              <th>Prefix</th>
              <th>Rate limit</th>
              <th>Requests</th>
              <th>Rows</th>
              <th>Last used</th>
              <th>Status</th>
              <th />
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id}>
                <td>{r.name}</td>
                <td className="small muted">
                  <code>{r.keyPrefix}…</code>
                </td>
                <td className="small">
                  {r.rateLimitPerMinute}/min · {r.rateLimitPerDay}/day
                </td>
                <td className="small">{r.totalRequests}</td>
                <td className="small">{r.totalRowsReturned}</td>
                <td className="small muted">{r.lastUsedAt?.toISOString().slice(0, 16) ?? 'never'}</td>
                <td className="small">{r.revokedAt ? 'revoked' : 'active'}</td>
                <td>
                  {!r.revokedAt && (
                    <form action={revoke}>
                      <input type="hidden" name="id" value={r.id} />
                      <button className="secondary small" type="submit">
                        Revoke
                      </button>
                    </form>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h2>Using it in Clay</h2>
      <p className="muted small">
        Add an HTTP API column, method GET, and paste this URL. The response is flat, so each key
        maps to a column directly.
      </p>
      <pre>{`${env.PUBLIC_BASE_URL}/api/v1/domains?min_score=70&days=1&limit=100

Header:  X-API-Key: nvx_live_...`}</pre>
    </main>
  );
}
