import { drizzle } from 'drizzle-orm/postgres-js';
import postgres from 'postgres';
import { env } from '@/config/env';
import * as schema from './schema';

/**
 * Database connection.
 *
 * The web process gets a small pool (many short requests); the worker gets a
 * larger one (long-running, batched writes). `NOVAX_ROLE` selects which.
 */

const isWorker = process.env.NOVAX_ROLE === 'worker';

declare global {
  // Next.js dev-mode hot reload otherwise opens a new pool on every edit.
  // eslint-disable-next-line no-var
  var __novaxSql: ReturnType<typeof postgres> | undefined;
}

function createClient() {
  return postgres(env.DATABASE_URL, {
    max: isWorker ? 20 : 10,
    idle_timeout: 30,
    connect_timeout: 15,
    // Neon and most managed Postgres require TLS; `prepare: false` keeps us
    // compatible with transaction-mode poolers.
    prepare: false,
    onnotice: () => {},
  });
}

export const sql = globalThis.__novaxSql ?? createClient();
if (env.NODE_ENV !== 'production') globalThis.__novaxSql = sql;

export const db = drizzle(sql, { schema });

export type Database = typeof db;
export { schema };
export * from './schema';
