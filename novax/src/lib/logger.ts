import { env } from '@/config/env';

/**
 * Structured JSON logging.
 *
 * One line per event, always JSON, always with `ts`, `level` and `msg`. Deliberately
 * dependency-free: at 3am you want to be able to read this file top to bottom.
 */

const LEVELS = { debug: 10, info: 20, warn: 30, error: 40 } as const;
export type Level = keyof typeof LEVELS;

const threshold = LEVELS[env.LOG_LEVEL];

export type LogContext = Record<string, unknown>;

function serialiseError(err: unknown): LogContext {
  if (err instanceof Error) {
    return {
      error: err.message,
      error_type: err.name,
      // `cause` carries the underlying failure for wrapped errors.
      ...(err.cause ? { error_cause: String(err.cause) } : {}),
      stack: err.stack?.split('\n').slice(0, 6).join('\n'),
    };
  }
  if (err === undefined) return {};
  return { error: String(err) };
}

function emit(level: Level, scope: string, msg: string, ctx?: LogContext) {
  if (LEVELS[level] < threshold) return;
  const line = {
    ts: new Date().toISOString(),
    level,
    scope,
    msg,
    ...ctx,
  };
  // stderr for warn/error so log shipping can split streams; stdout otherwise.
  const out = LEVELS[level] >= LEVELS.warn ? process.stderr : process.stdout;
  try {
    out.write(`${JSON.stringify(line)}\n`);
  } catch {
    // A log line must never crash the process (e.g. circular context object).
    out.write(`${JSON.stringify({ ts: line.ts, level, scope, msg, log_error: 'unserialisable context' })}\n`);
  }
}

export interface Logger {
  debug(msg: string, ctx?: LogContext): void;
  info(msg: string, ctx?: LogContext): void;
  warn(msg: string, ctx?: LogContext): void;
  error(msg: string, err?: unknown, ctx?: LogContext): void;
  child(scope: string): Logger;
}

export function createLogger(scope: string): Logger {
  return {
    debug: (msg, ctx) => emit('debug', scope, msg, ctx),
    info: (msg, ctx) => emit('info', scope, msg, ctx),
    warn: (msg, ctx) => emit('warn', scope, msg, ctx),
    error: (msg, err, ctx) => emit('error', scope, msg, { ...ctx, ...serialiseError(err) }),
    child: (sub) => createLogger(`${scope}.${sub}`),
  };
}

export const logger = createLogger('novax');
