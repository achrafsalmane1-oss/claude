import { betterAuth } from 'better-auth';
import { drizzleAdapter } from 'better-auth/adapters/drizzle';
import { randomBytes } from 'node:crypto';
import { db, users, sessions, accounts, verifications } from '@/db';
import { env } from '@/config/env';
import { createLogger } from '@/lib/logger';

/**
 * Authentication for the dashboard (spec §3: Better Auth or Clerk, email +
 * password is enough).
 *
 * Better Auth over Clerk because it is self-hosted: no third party in the login
 * path, no per-seat bill before there is revenue, and its tables live in the
 * same Postgres and the same migration flow as everything else.
 *
 * This is dashboard login only. Machine access uses API keys (`src/api/auth.ts`),
 * which are a separate mechanism on purpose — different lifetime, different
 * blast radius, and a cookie is unusable from Clay.
 */

const log = createLogger('auth');

/**
 * Session signing secret.
 *
 * Falling back to a random secret is fine locally but catastrophic in
 * production: the secret is regenerated on every boot, so every deploy and
 * every restart silently signs out every user. This was caught during the
 * phase 5 verification run, where sibling dashboard pages started 307ing to
 * /login after the dev server reloaded.
 *
 * So: generate one in development with a loud warning, and refuse to start in
 * production without it.
 */
function resolveSecret(): string {
  if (env.BETTER_AUTH_SECRET) return env.BETTER_AUTH_SECRET;

  if (env.NODE_ENV === 'production') {
    throw new Error(
      'BETTER_AUTH_SECRET must be set in production. Without it, sessions are signed with a ' +
        'secret that changes on every restart and all users are signed out on each deploy. ' +
        'Generate one with: openssl rand -hex 32',
    );
  }

  log.warn('BETTER_AUTH_SECRET is not set; generating an ephemeral one', {
    consequence: 'every restart of this process will sign you out',
  });
  return randomBytes(32).toString('hex');
}

export const auth = betterAuth({
  database: drizzleAdapter(db, {
    provider: 'pg',
    schema: { user: users, session: sessions, account: accounts, verification: verifications },
  }),
  secret: resolveSecret(),
  baseURL: env.PUBLIC_BASE_URL,
  emailAndPassword: {
    enabled: true,
    // No email provider is required for v1: an operator issues accounts by hand
    // alongside API keys, so there is nothing to verify by email yet.
    requireEmailVerification: false,
    minPasswordLength: 12,
  },
  session: {
    expiresIn: 60 * 60 * 24 * 30,
    updateAge: 60 * 60 * 24,
  },
  advanced: {
    // Our own `users` table uses text ids we generate elsewhere (issue-key.ts
    // creates users), so let Better Auth generate compatible ones.
    database: { generateId: () => randomBytes(16).toString('hex') },
  },
});

export type Session = typeof auth.$Infer.Session;
