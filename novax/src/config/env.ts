import { z } from 'zod';

/**
 * Environment configuration.
 *
 * Everything the process needs is validated once, at import time, so a missing
 * variable is a loud failure at boot rather than a 3am `undefined` deep inside
 * an enrichment job. Every variable here is documented in `.env.example`.
 */

const bool = (def: boolean) =>
  z
    .string()
    .optional()
    .transform((v) => (v === undefined || v === '' ? def : v === 'true' || v === '1'));

const int = (def: number) =>
  z
    .string()
    .optional()
    .transform((v) => (v === undefined || v === '' ? def : Number(v)))
    .pipe(z.number().int());

const schema = z.object({
  NODE_ENV: z.enum(['development', 'test', 'production']).default('development'),

  // --- Core infrastructure -------------------------------------------------
  DATABASE_URL: z.string().min(1, 'DATABASE_URL is required'),

  // --- Identity of this deployment, used in outbound requests --------------
  // The spec requires an identifying User-Agent with a contact URL on every
  // HTTP probe. This is that contact URL.
  PUBLIC_BASE_URL: z.string().url().default('http://localhost:3000'),
  CONTACT_URL: z.string().url().default('http://localhost:3000/about'),
  USER_AGENT_NAME: z.string().default('novaXBot'),

  // --- Ingestion -----------------------------------------------------------
  NRD_FEED_BASE_URL: z
    .string()
    .url()
    .default('https://www.whoisds.com/whois-database/newly-registered-domains'),
  // The free feed lags; day-2 is the most recent reliably complete file.
  NRD_LAG_DAYS: int(2),
  // Alert if a day's feed is smaller than this. Verified real days land at
  // 250k-450k; the free tier occasionally serves a truncated 70k file.
  NRD_MIN_EXPECTED_DOMAINS: int(100_000),

  CT_LOG_LIST_URL: z.string().url().default('https://www.gstatic.com/ct/log_list/v3/log_list.json'),
  CT_ENABLED: bool(true),
  // Number of CT logs polled concurrently. Each is an independent checkpoint.
  CT_MAX_LOGS: int(6),
  CT_BATCH_SIZE: int(256),
  CT_POLL_INTERVAL_MS: int(3_000),
  // Logs return HTTP 429 to callers that poll too hard. Observed live: 2 req/s
  // per log is accepted, higher gets throttled. This is a politeness limit as
  // much as a throughput one — a banned IP ingests nothing.
  CT_REQUESTS_PER_SECOND_PER_LOG: int(2),
  // Spec: alert if the CT stream is silent for more than 10 minutes.
  CT_SILENCE_ALERT_SECONDS: int(600),
  // In-process dedupe window. ~2M apexes at roughly 60 bytes each.
  CT_DEDUPE_LRU_SIZE: int(2_000_000),

  // --- CZDS (built, not scheduled — see DECISIONS.md) ----------------------
  CZDS_USERNAME: z.string().optional(),
  CZDS_PASSWORD: z.string().optional(),
  CZDS_AUTH_URL: z.string().url().default('https://account-api.icann.org/api/authenticate'),
  CZDS_BASE_URL: z.string().url().default('https://czds-api.icann.org'),

  // --- Enrichment ----------------------------------------------------------
  DNS_SERVERS: z
    .string()
    .default('1.1.1.1,8.8.8.8')
    .transform((v) => v.split(',').map((s) => s.trim()).filter(Boolean)),
  DNS_TIMEOUT_MS: int(4_000),
  DNS_CONCURRENCY: int(50),

  HTTP_PROBE_TIMEOUT_MS: int(8_000),
  HTTP_PROBE_MAX_BYTES: int(512 * 1024),
  HTTP_PROBE_MAX_REDIRECTS: int(5),
  HTTP_PROBE_CONCURRENCY: int(20),
  HTTP_RESPECT_ROBOTS: bool(true),
  BODY_SNIPPET_CHARS: int(2_000),

  RDAP_BOOTSTRAP_URL: z.string().url().default('https://data.iana.org/rdap/dns.json'),
  RDAP_FALLBACK_URL: z.string().url().default('https://rdap.org'),
  // Registries ban hot callers. One request per second per registry, burst 5.
  RDAP_RPS_PER_REGISTRY: int(1),
  RDAP_BURST_PER_REGISTRY: int(5),
  RDAP_TIMEOUT_MS: int(10_000),

  // Spec: set a per-domain enrichment budget and log cost per domain.
  ENRICHMENT_BUDGET_MICRO_USD: int(200), // 0.02 cents per domain
  MAX_ENRICHMENT_FAILURES: int(5),

  // --- Queue ---------------------------------------------------------------
  // DNS is batched so pg-boss sees hundreds of jobs a day, not hundreds of
  // thousands. See the sizing note in DECISIONS.md.
  QUEUE_DNS_BATCH_SIZE: int(500),
  // Smaller than the DNS batch because each item costs a real HTTP round trip.
  QUEUE_HTTP_BATCH_SIZE: int(25),
  QUEUE_RDAP_BATCH_SIZE: int(25),
  QUEUE_CONCURRENCY: int(5),
  QUEUE_SCHEMA: z.string().default('pgboss'),

  // --- Scoring -------------------------------------------------------------
  ANTHROPIC_API_KEY: z.string().optional(),
  CLASSIFIER_MODEL: z.string().default('claude-opus-5'),
  CLASSIFIER_ENABLED: bool(true),
  // The Batch API is 50% cheaper and this workload has no latency requirement.
  CLASSIFIER_USE_BATCH: bool(true),
  CLASSIFIER_MAX_PER_RUN: int(5_000),
  SCORE_TIER_HOT: int(80),
  SCORE_TIER_WARM: int(60),
  SCORE_TIER_COLD: int(40),

  // --- Delivery ------------------------------------------------------------
  RESEND_API_KEY: z.string().optional(),
  DIGEST_FROM_EMAIL: z.string().default('novaX <digest@novax.local>'),
  WEBHOOK_TIMEOUT_MS: int(10_000),
  WEBHOOK_MAX_ATTEMPTS: int(6),

  // --- Auth ----------------------------------------------------------------
  BETTER_AUTH_SECRET: z.string().optional(),

  // --- Ops -----------------------------------------------------------------
  ALERT_WEBHOOK_URL: z.string().optional(),
  LOG_LEVEL: z.enum(['debug', 'info', 'warn', 'error']).default('info'),
});

export type Env = z.infer<typeof schema>;

function load(): Env {
  const parsed = schema.safeParse(process.env);
  if (!parsed.success) {
    const issues = parsed.error.issues
      .map((i) => `  ${i.path.join('.') || '(root)'}: ${i.message}`)
      .join('\n');
    throw new Error(`Invalid environment configuration:\n${issues}`);
  }
  return parsed.data;
}

export const env: Env = load();

/** The identifying User-Agent required by spec §10 for every outbound probe. */
export const USER_AGENT = `${env.USER_AGENT_NAME}/0.1 (+${env.CONTACT_URL})`;

/** Scoring version stamped onto every score row so eval comparisons stay honest. */
export const SCORING_VERSION = 'rules-1.0.0';
