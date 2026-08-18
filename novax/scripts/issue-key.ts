/**
 * Issue an API key by hand (spec §2: no billing in v1, manual issuance is fine).
 *
 *   npm run issue-key -- --name="Acme Corp" --email=buyer@acme.com
 *   npm run issue-key -- --name="Trial" --rpm=30 --rpd=2000 --days=14
 *
 * The key is printed once. It is stored only as a SHA-256 hash, so if it is
 * lost, issue a new one — there is no recovery, by design.
 */
import { randomUUID } from 'node:crypto';
import { eq } from 'drizzle-orm';
import { issueApiKey } from '@/api/auth';
import { db, users, sql } from '@/db';
import { createLogger } from '@/lib/logger';

const log = createLogger('script.issue-key');

async function main() {
  const arg = (n: string) => process.argv.find((a) => a.startsWith(`--${n}=`))?.split('=').slice(1).join('=');

  const name = arg('name');
  if (!name) {
    process.stderr.write(
      'usage: npm run issue-key -- --name="Customer name" [--email=...] [--api-only] [--rpm=60] [--rpd=10000] [--days=N]\n',
    );
    process.exit(1);
  }

  const email = arg('email');
  const apiOnly = process.argv.includes('--api-only');
  const rpm = arg('rpm') ? Number(arg('rpm')) : undefined;
  const rpd = arg('rpd') ? Number(arg('rpd')) : undefined;
  const days = arg('days') ? Number(arg('days')) : undefined;

  // Saved searches, webhooks and digests all hang off a user, so attach the key
  // to one when an email is given.
  //
  // We deliberately do NOT create a user row for an unknown email by default.
  // Better Auth owns account creation, and a bare row inserted here has no
  // credential — which then blocks that person from ever signing up with their
  // own address ("user already exists"). Have them sign up at /login first, or
  // pass --api-only for a key that has no dashboard account behind it.
  let userId: string | null = null;
  if (email) {
    const existing = await db.select({ id: users.id }).from(users).where(eq(users.email, email)).limit(1);
    if (existing[0]) {
      userId = existing[0].id;
    } else if (apiOnly) {
      userId = randomUUID();
      await db.insert(users).values({ id: userId, email, name });
      log.info('created API-only user (no dashboard password)', { email, id: userId });
    } else {
      process.stderr.write(
        `\nNo account exists for ${email}.\n` +
          `  Ask them to sign up at ${process.env.PUBLIC_BASE_URL ?? 'http://localhost:3000'}/login, then re-run this.\n` +
          `  Or pass --api-only to issue a key with no dashboard account (no saved searches or digests).\n\n`,
      );
      process.exit(1);
    }
  }

  const issued = await issueApiKey({
    name,
    userId,
    ...(rpm ? { rateLimitPerMinute: rpm } : {}),
    ...(rpd ? { rateLimitPerDay: rpd } : {}),
    expiresAt: days ? new Date(Date.now() + days * 86_400_000) : null,
  });

  process.stdout.write(
    [
      '',
      `  API key for ${name}`,
      `  ${issued.key}`,
      '',
      '  This is shown once and cannot be recovered.',
      `  Usage:  curl -H "X-API-Key: ${issued.prefix}..." ${process.env.PUBLIC_BASE_URL ?? 'http://localhost:3000'}/api/v1/domains?min_score=70`,
      '',
    ].join('\n'),
  );

  await sql.end();
}

main().catch(async (err) => {
  log.error('failed to issue key', err);
  await sql.end().catch(() => {});
  process.exit(1);
});
