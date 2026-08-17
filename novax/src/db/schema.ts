import {
  pgTable,
  text,
  timestamp,
  integer,
  boolean,
  jsonb,
  serial,
  bigint,
  doublePrecision,
  uniqueIndex,
  index,
  primaryKey,
  smallint,
} from 'drizzle-orm/pg-core';
import { sql } from 'drizzle-orm';

/**
 * novaX schema.
 *
 * Conventions that hold everywhere:
 *  - `domains.apex` is the natural key. Everything joins on it. It is stored
 *    lowercased and punycode-normalised at write time.
 *  - Enrichment tables are append-only observation history. Nameserver changes
 *    are themselves a signal (spec §4), so we never overwrite an observation.
 *    `is_current` + a partial unique index gives cheap "latest" lookups.
 *  - Every enrichment table carries `last_attempted_at` and `failure_count` so
 *    retries cannot loop forever (spec §4).
 *  - Every stored field group carries a `source` and an observed-at timestamp so
 *    any record's provenance can be shown on request (spec §10).
 */

// ---------------------------------------------------------------------------
// Ingestion
// ---------------------------------------------------------------------------

/** Where we first learned about a domain. */
export const DOMAIN_SOURCES = ['ct_log', 'nrd_feed', 'czds', 'manual'] as const;
export type DomainSource = (typeof DOMAIN_SOURCES)[number];

/**
 * Lifecycle of a domain through the pipeline. This is the field the worker
 * queries to decide what to do next.
 */
export const DOMAIN_STATUSES = [
  'discovered', // seen, nothing done yet
  'dns_pending', // queued for DNS
  'unconfigured', // no A and no MX — parked in a 72h requeue (spec §6.1)
  'enriching', // passed the DNS gate, later stages running
  'enriched', // enrichment complete, ready to score
  'scored', // has a current score
  'rejected', // hard-killed by the rules layer
  'failed', // exceeded MAX_ENRICHMENT_FAILURES
] as const;
export type DomainStatus = (typeof DOMAIN_STATUSES)[number];

export const domains = pgTable(
  'domains',
  {
    id: serial('id').primaryKey(),
    /** Registrable apex, lowercase, e.g. `example.co.uk`. Never a subdomain. */
    apex: text('apex').notNull(),
    /** Public-suffix TLD, e.g. `co.uk`. Not simply the last label. */
    tld: text('tld').notNull(),

    firstSeenAt: timestamp('first_seen_at', { withTimezone: true }).notNull().defaultNow(),
    lastSeenAt: timestamp('last_seen_at', { withTimezone: true }).notNull().defaultNow(),
    source: text('source').$type<DomainSource>().notNull(),

    /**
     * Actual registration date. From the NRD feed (the feed date) or the RDAP
     * `registration` event, whichever we learn first. Null until known — a CT
     * hit alone proves nothing about registration age (spec §5b gotcha).
     */
    registrationDate: timestamp('registration_date', { withTimezone: true }),
    registrationDateSource: text('registration_date_source'),

    status: text('status').$type<DomainStatus>().notNull().default('discovered'),

    /** Denormalised from `opt_outs` so the suppression gate is a single-table read. */
    isSuppressed: boolean('is_suppressed').notNull().default(false),

    /** How many distinct times CT has produced a cert for this apex. */
    ctHitCount: integer('ct_hit_count').notNull().default(0),

    /** Do-not-enrich-before, used for the 72h unconfigured requeue. */
    requeueAfter: timestamp('requeue_after', { withTimezone: true }),

    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [
    uniqueIndex('domains_apex_key').on(t.apex),
    index('domains_status_idx').on(t.status),
    index('domains_first_seen_idx').on(t.firstSeenAt),
    index('domains_tld_idx').on(t.tld),
    // The worker's hot query: "what is ready for this stage, oldest first".
    index('domains_status_requeue_idx').on(t.status, t.requeueAfter),
  ],
);

/** One row per NRD/CZDS feed download attempt. Backs the `/health` metric. */
export const feedRuns = pgTable(
  'feed_runs',
  {
    id: serial('id').primaryKey(),
    feed: text('feed').notNull(), // 'nrd' | 'czds:<tld>'
    feedDate: text('feed_date').notNull(), // YYYY-MM-DD
    status: text('status').$type<'running' | 'success' | 'failed'>().notNull(),
    domainsInFile: integer('domains_in_file'),
    domainsInserted: integer('domains_inserted'),
    bytesDownloaded: bigint('bytes_downloaded', { mode: 'number' }),
    /** Set when the file parsed but looked truncated — see the free-tier caveat. */
    warning: text('warning'),
    error: text('error'),
    startedAt: timestamp('started_at', { withTimezone: true }).notNull().defaultNow(),
    finishedAt: timestamp('finished_at', { withTimezone: true }),
  },
  (t) => [
    uniqueIndex('feed_runs_feed_date_key').on(t.feed, t.feedDate),
    index('feed_runs_status_idx').on(t.status, t.startedAt),
  ],
);

/**
 * CT poller checkpoint, one row per log. Polling from a stored index is what
 * makes a crash resume with zero gaps — the reason we poll rather than consume
 * a websocket (see DECISIONS.md).
 */
export const ctLogState = pgTable('ct_log_state', {
  logUrl: text('log_url').primaryKey(),
  description: text('description'),
  /** Next entry index to fetch. */
  nextIndex: bigint('next_index', { mode: 'number' }).notNull().default(0),
  treeSize: bigint('tree_size', { mode: 'number' }).notNull().default(0),
  lastEventAt: timestamp('last_event_at', { withTimezone: true }),
  lastErrorAt: timestamp('last_error_at', { withTimezone: true }),
  lastError: text('last_error'),
  consecutiveFailures: integer('consecutive_failures').notNull().default(0),
  entriesProcessed: bigint('entries_processed', { mode: 'number' }).notNull().default(0),
  enabled: boolean('enabled').notNull().default(true),
  updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
});

// ---------------------------------------------------------------------------
// Enrichment — append-only observation history
// ---------------------------------------------------------------------------

export const domainDns = pgTable(
  'domain_dns',
  {
    id: serial('id').primaryKey(),
    apex: text('apex').notNull(),

    aRecords: jsonb('a_records').$type<string[]>().notNull().default(sql`'[]'::jsonb`),
    aaaaRecords: jsonb('aaaa_records').$type<string[]>().notNull().default(sql`'[]'::jsonb`),
    /** `[{ exchange, priority }]`, priority-sorted. */
    mxRecords: jsonb('mx_records')
      .$type<{ exchange: string; priority: number }[]>()
      .notNull()
      .default(sql`'[]'::jsonb`),
    nsRecords: jsonb('ns_records').$type<string[]>().notNull().default(sql`'[]'::jsonb`),
    txtRecords: jsonb('txt_records').$type<string[]>().notNull().default(sql`'[]'::jsonb`),

    /** Presence only — we do not store or output the record contents as PII. */
    hasSpf: boolean('has_spf').notNull().default(false),
    hasDmarc: boolean('has_dmarc').notNull().default(false),

    /** Classified from `mxRecords`. The single highest-signal cheap filter. */
    mxProvider: text('mx_provider'),
    mxProviderKind: text('mx_provider_kind').$type<
      'business' | 'consumer' | 'hosting' | 'parking' | 'security' | 'unknown' | 'none'
    >(),

    /** Set when this observation differs from the previous one for this apex. */
    changedFromPrevious: boolean('changed_from_previous').notNull().default(false),
    nsChanged: boolean('ns_changed').notNull().default(false),

    isCurrent: boolean('is_current').notNull().default(true),
    resolvedAt: timestamp('resolved_at', { withTimezone: true }).notNull().defaultNow(),
    lastAttemptedAt: timestamp('last_attempted_at', { withTimezone: true }).notNull().defaultNow(),
    failureCount: integer('failure_count').notNull().default(0),
    lastError: text('last_error'),
  },
  (t) => [
    index('domain_dns_apex_idx').on(t.apex, t.resolvedAt),
    // One current observation per apex. History rows have is_current = false.
    uniqueIndex('domain_dns_current_key')
      .on(t.apex)
      .where(sql`${t.isCurrent}`),
    index('domain_dns_mx_provider_idx').on(t.mxProvider),
  ],
);

export const domainHttp = pgTable(
  'domain_http',
  {
    id: serial('id').primaryKey(),
    apex: text('apex').notNull(),

    /** Which URL we actually probed first (https://apex, then http://). */
    requestedUrl: text('requested_url'),
    statusCode: integer('status_code'),
    finalUrl: text('final_url'),
    redirectCount: integer('redirect_count').notNull().default(0),
    /** True when the final URL's apex differs — a redirect off-domain. */
    redirectedOffDomain: boolean('redirected_off_domain').notNull().default(false),

    title: text('title'),
    metaDescription: text('meta_description'),
    /** Capped at BODY_SNIPPET_CHARS. Never the full page. */
    bodySnippet: text('body_snippet'),
    lang: text('lang'),

    /** Fingerprint slugs, e.g. ['webflow','cloudflare']. */
    tech: jsonb('tech').$type<string[]>().notNull().default(sql`'[]'::jsonb`),
    server: text('server'),

    isParked: boolean('is_parked').notNull().default(false),
    parkingVendor: text('parking_vendor'),
    parkingReason: text('parking_reason'),

    /** False when robots.txt disallowed the probe; we then store no page content. */
    robotsAllowed: boolean('robots_allowed').notNull().default(true),

    contentLength: integer('content_length'),
    responseTimeMs: integer('response_time_ms'),

    isCurrent: boolean('is_current').notNull().default(true),
    probedAt: timestamp('probed_at', { withTimezone: true }).notNull().defaultNow(),
    lastAttemptedAt: timestamp('last_attempted_at', { withTimezone: true }).notNull().defaultNow(),
    failureCount: integer('failure_count').notNull().default(0),
    lastError: text('last_error'),
  },
  (t) => [
    index('domain_http_apex_idx').on(t.apex, t.probedAt),
    uniqueIndex('domain_http_current_key')
      .on(t.apex)
      .where(sql`${t.isCurrent}`),
    index('domain_http_parked_idx').on(t.isParked),
  ],
);

/**
 * RDAP observations.
 *
 * Registrant name/email are redacted for essentially every gTLD registration.
 * Nothing downstream may depend on them, and the parser drops anything flagged
 * redacted before it reaches this table (spec §10).
 */
export const domainRdap = pgTable(
  'domain_rdap',
  {
    id: serial('id').primaryKey(),
    apex: text('apex').notNull(),

    registrar: text('registrar'),
    registrarIanaId: text('registrar_iana_id'),
    createdDate: timestamp('created_date', { withTimezone: true }),
    expiresDate: timestamp('expires_date', { withTimezone: true }),
    lastChangedDate: timestamp('last_changed_date', { withTimezone: true }),

    /** EPP status codes, e.g. ['client transfer prohibited']. */
    statuses: jsonb('statuses').$type<string[]>().notNull().default(sql`'[]'::jsonb`),
    nameservers: jsonb('nameservers').$type<string[]>().notNull().default(sql`'[]'::jsonb`),

    /**
     * Registrant country/state only, and only where the registry publishes them
     * unredacted. Never a name, email, phone or street address.
     */
    registrantCountry: text('registrant_country'),
    registrantState: text('registrant_state'),

    /** True when the response carried redaction markers — recorded, not worked around. */
    hadRedactions: boolean('had_redactions').notNull().default(false),
    /** Which RDAP server answered, for provenance. */
    rdapServer: text('rdap_server'),

    isCurrent: boolean('is_current').notNull().default(true),
    fetchedAt: timestamp('fetched_at', { withTimezone: true }).notNull().defaultNow(),
    lastAttemptedAt: timestamp('last_attempted_at', { withTimezone: true }).notNull().defaultNow(),
    failureCount: integer('failure_count').notNull().default(0),
    lastError: text('last_error'),
  },
  (t) => [
    index('domain_rdap_apex_idx').on(t.apex, t.fetchedAt),
    uniqueIndex('domain_rdap_current_key')
      .on(t.apex)
      .where(sql`${t.isCurrent}`),
    index('domain_rdap_registrar_idx').on(t.registrar),
    index('domain_rdap_country_idx').on(t.registrantCountry),
  ],
);

// ---------------------------------------------------------------------------
// Scoring
// ---------------------------------------------------------------------------

export const SCORE_TIERS = ['hot', 'warm', 'cold', 'junk'] as const;
export type ScoreTier = (typeof SCORE_TIERS)[number];

export const domainScores = pgTable(
  'domain_scores',
  {
    id: serial('id').primaryKey(),
    apex: text('apex').notNull(),

    score: integer('score').notNull(), // 0-100 composite
    tier: text('tier').$type<ScoreTier>().notNull(),

    /** Human-readable explanation. The differentiator over black-box incumbents. */
    reason: text('reason').notNull(),

    /** Deterministic layer output. */
    rulesVerdict: text('rules_verdict').$type<'pass' | 'kill'>().notNull(),
    rulesKillReason: text('rules_kill_reason'),
    rulesSignals: jsonb('rules_signals').$type<Record<string, unknown>>(),

    /** Classifier layer output, null when rules killed it before any LLM cost. */
    classifierRan: boolean('classifier_ran').notNull().default(false),
    isRealBusiness: boolean('is_real_business'),
    category: text('category'),
    stageGuess: text('stage_guess'),
    confidence: doublePrecision('confidence'),
    classifierReason: text('classifier_reason'),

    modelVersion: text('model_version'), // e.g. 'claude-opus-5'
    scoringVersion: text('scoring_version').notNull(), // e.g. 'rules-1.0.0'

    isCurrent: boolean('is_current').notNull().default(true),
    scoredAt: timestamp('scored_at', { withTimezone: true }).notNull().defaultNow(),
    lastAttemptedAt: timestamp('last_attempted_at', { withTimezone: true }).notNull().defaultNow(),
    failureCount: integer('failure_count').notNull().default(0),
    lastError: text('last_error'),
  },
  (t) => [
    index('domain_scores_apex_idx').on(t.apex, t.scoredAt),
    uniqueIndex('domain_scores_current_key')
      .on(t.apex)
      .where(sql`${t.isCurrent}`),
    // The API's hot path: high scores, newest first.
    index('domain_scores_score_idx').on(t.score, t.scoredAt),
    index('domain_scores_tier_idx').on(t.tier),
    index('domain_scores_category_idx').on(t.category),
  ],
);

/** The resolved entity a buyer actually wants. One row per apex. */
export const companies = pgTable(
  'companies',
  {
    id: serial('id').primaryKey(),
    apex: text('apex').notNull(),

    name: text('name'),
    description: text('description'),
    category: text('category'),
    country: text('country'),
    website: text('website'),
    confidence: doublePrecision('confidence'),

    /** Per-field provenance, e.g. {name: 'http_title', country: 'rdap'}. */
    fieldSources: jsonb('field_sources').$type<Record<string, string>>(),

    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [
    uniqueIndex('companies_apex_key').on(t.apex),
    index('companies_category_idx').on(t.category),
    index('companies_country_idx').on(t.country),
  ],
);

/** Per-domain, per-stage cost in micro-dollars. Backs the unit-economics tripwire. */
export const enrichmentCosts = pgTable(
  'enrichment_costs',
  {
    id: serial('id').primaryKey(),
    apex: text('apex').notNull(),
    stage: text('stage').notNull(), // dns | http | rdap | classifier
    microUsd: integer('micro_usd').notNull(),
    detail: jsonb('detail').$type<Record<string, unknown>>(),
    incurredAt: timestamp('incurred_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [
    index('enrichment_costs_apex_idx').on(t.apex),
    index('enrichment_costs_incurred_idx').on(t.incurredAt),
  ],
);

// ---------------------------------------------------------------------------
// Compliance
// ---------------------------------------------------------------------------

/**
 * Permanent suppression, proven by a DNS TXT record.
 *
 * A verified row means the apex is excluded from every output path, forever.
 * Enforcement lives in one place: `src/compliance/suppression.ts`.
 */
export const optOuts = pgTable(
  'opt_outs',
  {
    id: serial('id').primaryKey(),
    apex: text('apex').notNull(),
    /** Value the requester must publish as `novax-verify=<token>` in a TXT record. */
    verificationToken: text('verification_token').notNull(),
    verifiedAt: timestamp('verified_at', { withTimezone: true }),
    verificationAttempts: integer('verification_attempts').notNull().default(0),
    lastAttemptedAt: timestamp('last_attempted_at', { withTimezone: true }),
    lastError: text('last_error'),
    /** Optional contact for the confirmation only. Never used as a data field. */
    requesterEmail: text('requester_email'),
    requestedAt: timestamp('requested_at', { withTimezone: true }).notNull().defaultNow(),
    /** Free-text note from the requester, retained for the audit trail. */
    note: text('note'),
  },
  (t) => [
    uniqueIndex('opt_outs_apex_key').on(t.apex),
    index('opt_outs_verified_idx').on(t.verifiedAt),
  ],
);

// ---------------------------------------------------------------------------
// Auth (Better Auth core tables) and API access
// ---------------------------------------------------------------------------

export const users = pgTable(
  'users',
  {
    id: text('id').primaryKey(),
    name: text('name').notNull().default(''),
    email: text('email').notNull(),
    emailVerified: boolean('email_verified').notNull().default(false),
    image: text('image'),
    role: text('role').$type<'admin' | 'user'>().notNull().default('user'),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [uniqueIndex('users_email_key').on(t.email)],
);

export const sessions = pgTable(
  'sessions',
  {
    id: text('id').primaryKey(),
    userId: text('user_id')
      .notNull()
      .references(() => users.id, { onDelete: 'cascade' }),
    token: text('token').notNull(),
    expiresAt: timestamp('expires_at', { withTimezone: true }).notNull(),
    ipAddress: text('ip_address'),
    userAgent: text('user_agent'),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [uniqueIndex('sessions_token_key').on(t.token), index('sessions_user_idx').on(t.userId)],
);

export const accounts = pgTable(
  'accounts',
  {
    id: text('id').primaryKey(),
    userId: text('user_id')
      .notNull()
      .references(() => users.id, { onDelete: 'cascade' }),
    accountId: text('account_id').notNull(),
    providerId: text('provider_id').notNull(),
    accessToken: text('access_token'),
    refreshToken: text('refresh_token'),
    accessTokenExpiresAt: timestamp('access_token_expires_at', { withTimezone: true }),
    refreshTokenExpiresAt: timestamp('refresh_token_expires_at', { withTimezone: true }),
    scope: text('scope'),
    idToken: text('id_token'),
    password: text('password'),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [index('accounts_user_idx').on(t.userId)],
);

export const verifications = pgTable(
  'verifications',
  {
    id: text('id').primaryKey(),
    identifier: text('identifier').notNull(),
    value: text('value').notNull(),
    expiresAt: timestamp('expires_at', { withTimezone: true }).notNull(),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [index('verifications_identifier_idx').on(t.identifier)],
);

/**
 * API keys.
 *
 * Only a SHA-256 hash is stored. `keyPrefix` is the displayable first 12 chars
 * so a user can tell their keys apart without us holding the secret.
 */
export const apiKeys = pgTable(
  'api_keys',
  {
    id: serial('id').primaryKey(),
    userId: text('user_id').references(() => users.id, { onDelete: 'cascade' }),
    name: text('name').notNull(),
    keyHash: text('key_hash').notNull(),
    keyPrefix: text('key_prefix').notNull(),

    rateLimitPerMinute: integer('rate_limit_per_minute').notNull().default(60),
    rateLimitPerDay: integer('rate_limit_per_day').notNull().default(10_000),

    totalRequests: bigint('total_requests', { mode: 'number' }).notNull().default(0),
    totalRowsReturned: bigint('total_rows_returned', { mode: 'number' }).notNull().default(0),
    lastUsedAt: timestamp('last_used_at', { withTimezone: true }),

    revokedAt: timestamp('revoked_at', { withTimezone: true }),
    expiresAt: timestamp('expires_at', { withTimezone: true }),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [
    uniqueIndex('api_keys_hash_key').on(t.keyHash),
    index('api_keys_user_idx').on(t.userId),
  ],
);

/**
 * Fixed-window rate limiting and usage counting.
 *
 * `windowStart` is truncated to the window size, so the primary key is the
 * bucket and an upsert is the whole limiter. Correct across web instances,
 * which an in-memory limiter is not.
 */
export const apiUsage = pgTable(
  'api_usage',
  {
    apiKeyId: integer('api_key_id')
      .notNull()
      .references(() => apiKeys.id, { onDelete: 'cascade' }),
    window: text('window').notNull(), // 'minute' | 'day'
    windowStart: timestamp('window_start', { withTimezone: true }).notNull(),
    requestCount: integer('request_count').notNull().default(0),
    rowsReturned: bigint('rows_returned', { mode: 'number' }).notNull().default(0),
  },
  (t) => [
    primaryKey({ columns: [t.apiKeyId, t.window, t.windowStart] }),
    index('api_usage_window_idx').on(t.windowStart),
  ],
);

// ---------------------------------------------------------------------------
// Delivery
// ---------------------------------------------------------------------------

export const savedSearches = pgTable(
  'saved_searches',
  {
    id: serial('id').primaryKey(),
    userId: text('user_id')
      .notNull()
      .references(() => users.id, { onDelete: 'cascade' }),
    name: text('name').notNull(),
    /** The same filter object the API accepts as query params. */
    filters: jsonb('filters').$type<Record<string, unknown>>().notNull(),
    digestEnabled: boolean('digest_enabled').notNull().default(false),
    digestHourUtc: smallint('digest_hour_utc').notNull().default(13),
    lastDigestAt: timestamp('last_digest_at', { withTimezone: true }),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    updatedAt: timestamp('updated_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [index('saved_searches_user_idx').on(t.userId), index('saved_searches_digest_idx').on(t.digestEnabled)],
);

export const webhooks = pgTable(
  'webhooks',
  {
    id: serial('id').primaryKey(),
    userId: text('user_id')
      .notNull()
      .references(() => users.id, { onDelete: 'cascade' }),
    url: text('url').notNull(),
    /** HMAC-SHA256 signing secret; the receiver verifies with this. */
    secret: text('secret').notNull(),
    savedSearchId: integer('saved_search_id').references(() => savedSearches.id, {
      onDelete: 'cascade',
    }),
    filters: jsonb('filters').$type<Record<string, unknown>>(),
    active: boolean('active').notNull().default(true),
    /** Watermark: only domains scored after this are delivered. */
    lastDeliveredScoreId: integer('last_delivered_score_id').notNull().default(0),
    consecutiveFailures: integer('consecutive_failures').notNull().default(0),
    disabledAt: timestamp('disabled_at', { withTimezone: true }),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
  },
  (t) => [index('webhooks_user_idx').on(t.userId), index('webhooks_active_idx').on(t.active)],
);

export const deliveries = pgTable(
  'deliveries',
  {
    id: serial('id').primaryKey(),
    kind: text('kind').$type<'webhook' | 'digest'>().notNull(),
    webhookId: integer('webhook_id').references(() => webhooks.id, { onDelete: 'cascade' }),
    savedSearchId: integer('saved_search_id').references(() => savedSearches.id, {
      onDelete: 'cascade',
    }),
    target: text('target').notNull(), // URL or email address
    payloadSummary: jsonb('payload_summary').$type<Record<string, unknown>>(),
    domainCount: integer('domain_count').notNull().default(0),
    status: text('status').$type<'pending' | 'delivered' | 'failed'>().notNull().default('pending'),
    statusCode: integer('status_code'),
    attempt: integer('attempt').notNull().default(0),
    error: text('error'),
    createdAt: timestamp('created_at', { withTimezone: true }).notNull().defaultNow(),
    deliveredAt: timestamp('delivered_at', { withTimezone: true }),
  },
  (t) => [
    index('deliveries_webhook_idx').on(t.webhookId, t.createdAt),
    index('deliveries_status_idx').on(t.status),
  ],
);
