/**
 * Apply Drizzle migrations.
 *
 * `npm run db:migrate`. Safe to run repeatedly — Drizzle tracks what has been
 * applied in its own journal table.
 */
import { drizzle } from 'drizzle-orm/postgres-js';
import { migrate } from 'drizzle-orm/postgres-js/migrator';
import postgres from 'postgres';
import { fileURLToPath } from 'node:url';
import { env } from '@/config/env';
import { createLogger } from '@/lib/logger';

const log = createLogger('migrate');

async function main() {
  // A dedicated single connection: migrations must not share the app pool.
  const client = postgres(env.DATABASE_URL, { max: 1, prepare: false });
  const db = drizzle(client);

  const folder = fileURLToPath(new URL('../src/db/migrations', import.meta.url));
  log.info('applying migrations', { folder });

  await migrate(db, { migrationsFolder: folder });

  log.info('migrations applied');
  await client.end();
}

main().catch((err) => {
  log.error('migration failed', err);
  process.exit(1);
});
