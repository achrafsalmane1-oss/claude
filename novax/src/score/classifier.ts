import Anthropic from '@anthropic-ai/sdk';
import { env } from '@/config/env';
import { createLogger } from '@/lib/logger';
import { sleep } from '@/lib/backoff';

/**
 * The classifier layer (spec §7).
 *
 * Runs only on rules-layer survivors. Given the domain, page title, meta
 * description, body snippet, MX provider and detected tech, it answers one
 * question: is this a real business?
 *
 * Three things the spec asks for, and how they are done:
 *  - "Force JSON-only output": `output_config.format` with a JSON schema, which
 *    constrains the model rather than merely asking it nicely.
 *  - "Parse defensively": `parseClassification` handles fence-wrapped, prefixed
 *    and truncated output, and falls back to a safe negative rather than
 *    throwing. A malformed response must never take down a batch.
 *  - "Batch these calls": the Message Batches API, at 50% of standard price,
 *    which suits a workload with no latency requirement at all.
 *
 * The system prompt is stable and cached, so the taxonomy is not re-billed on
 * every domain.
 */

const log = createLogger('score.classifier');

export interface ClassifierInput {
  apex: string;
  tld: string;
  title: string | null;
  metaDescription: string | null;
  bodySnippet: string | null;
  mxProvider: string | null;
  tech: string[];
  registrar: string | null;
  country: string | null;
}

export interface Classification {
  isRealBusiness: boolean;
  category: string;
  stageGuess: string;
  confidence: number;
  reason: string;
}

/** What we return when the model gives us something unusable. */
export const FALLBACK_CLASSIFICATION: Classification = {
  isRealBusiness: false,
  category: 'unknown',
  stageGuess: 'unknown',
  confidence: 0,
  reason: 'classifier output could not be parsed',
};

export const CATEGORIES = [
  'saas',
  'ecommerce',
  'agency',
  'consulting',
  'professional_services',
  'local_services',
  'healthcare',
  'finance',
  'real_estate',
  'education',
  'media',
  'nonprofit',
  'hospitality',
  'manufacturing',
  'logistics',
  'construction',
  'crypto',
  'gambling',
  'adult',
  'personal',
  'parked_or_spam',
  'other',
  'unknown',
] as const;

export const STAGES = [
  'pre_launch',
  'just_launched',
  'operating',
  'established_rebrand',
  'side_project',
  'unknown',
] as const;

/**
 * Stable system prompt. Everything volatile (the domain itself) goes in the
 * user turn so this prefix stays byte-identical and cacheable across the batch.
 */
const SYSTEM_PROMPT = `You classify newly registered internet domains for a business-signal product. Buyers are investors and go-to-market teams looking for companies that have just started operating.

Your one job: decide whether this domain represents a REAL BUSINESS — an actual company, practice, agency, shop, or organisation run by real people — as opposed to noise.

Noise includes: parked pages, domains for sale, SEO/affiliate churn, link farms, spam infrastructure, gambling and adult-content farms, scam and phishing sites, drop-catch inventory, and template sites with no actual business behind them.

Judge on the evidence given. Signals that point to a real business:
- Specific, concrete description of what is sold and to whom
- Named people, a real physical location, or a company registration number
- Working commerce or booking functionality
- Business email configured on a real provider
- A deliberately built site (Webflow, Framer, Shopify, a real CMS) rather than a default template
- Coherent, non-generic copy

Signals that point to noise:
- Generic filler copy that could describe any business ("we provide quality solutions")
- Keyword-stuffed text, or content unrelated to the domain name
- Gambling/casino/betting/slot content, adult content, or crypto-giveaway content
- A page that exists only to redirect or to host advertising
- Boilerplate that matches thousands of other sites

Be strict. Most domains you see are not real businesses. A "coming soon" page from a plausible-looking company is worth flagging as pre-launch and real IF the surrounding evidence supports it; a "coming soon" page with nothing else is not.

Categories: ${CATEGORIES.join(', ')}.
Stages: pre_launch (nothing shipped yet), just_launched (site is live, business is new), operating (clearly trading), established_rebrand (an existing company on a new domain), side_project (a personal or hobby project), unknown.

Output JSON only. Set confidence to your genuine certainty: use values below 0.5 when the evidence is thin, and reserve above 0.85 for cases where the evidence is unambiguous.`;

/** JSON schema the API enforces on the response. */
const OUTPUT_SCHEMA = {
  type: 'object',
  properties: {
    is_real_business: { type: 'boolean' },
    category: { type: 'string', enum: [...CATEGORIES] },
    stage_guess: { type: 'string', enum: [...STAGES] },
    confidence: { type: 'number', minimum: 0, maximum: 1 },
    reason: {
      type: 'string',
      description: 'One or two sentences citing the specific evidence that drove the decision.',
    },
  },
  required: ['is_real_business', 'category', 'stage_guess', 'confidence', 'reason'],
  additionalProperties: false,
} as const;

/** Build the per-domain user turn. Kept compact — this is the billed part. */
export function buildUserPrompt(input: ClassifierInput): string {
  const lines = [
    `Domain: ${input.apex}`,
    `TLD: .${input.tld}`,
    `Page title: ${input.title ?? '(none)'}`,
    `Meta description: ${input.metaDescription ?? '(none)'}`,
    `Business email provider: ${input.mxProvider ?? '(none configured)'}`,
    `Detected technology: ${input.tech.length > 0 ? input.tech.join(', ') : '(none detected)'}`,
    `Registrar: ${input.registrar ?? '(unknown)'}`,
    `Registrant country: ${input.country ?? '(not published)'}`,
    '',
    'Page text:',
    input.bodySnippet?.trim() ? input.bodySnippet.trim() : '(page had no readable text)',
  ];
  return lines.join('\n');
}

/**
 * Defensive parser.
 *
 * Handles: a bare JSON object, a fenced code block, leading prose, trailing
 * prose, and a truncated response. Returns the fallback rather than throwing —
 * the spec is explicit that this must parse defensively, and one bad response
 * must not fail an entire batch of 5,000.
 */
export function parseClassification(raw: string): Classification {
  if (!raw || typeof raw !== 'string') return FALLBACK_CLASSIFICATION;

  let text = raw.trim();

  // Strip a markdown fence if the model wrapped the JSON in one.
  const fence = /```(?:json)?\s*([\s\S]*?)```/i.exec(text);
  if (fence?.[1]) text = fence[1].trim();

  // Find the outermost JSON object if there is prose around it.
  if (!text.startsWith('{')) {
    const start = text.indexOf('{');
    const end = text.lastIndexOf('}');
    if (start >= 0 && end > start) text = text.slice(start, end + 1);
  }

  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(text) as Record<string, unknown>;
  } catch {
    log.debug('classifier output was not valid JSON', { sample: raw.slice(0, 200) });
    return FALLBACK_CLASSIFICATION;
  }

  if (typeof parsed !== 'object' || parsed === null) return FALLBACK_CLASSIFICATION;

  // Coerce each field independently: a response missing `stage_guess` is still
  // useful if `is_real_business` came through.
  const isRealBusiness =
    typeof parsed['is_real_business'] === 'boolean'
      ? parsed['is_real_business']
      : String(parsed['is_real_business']).toLowerCase() === 'true';

  const category = typeof parsed['category'] === 'string' ? parsed['category'] : 'unknown';
  const stageGuess = typeof parsed['stage_guess'] === 'string' ? parsed['stage_guess'] : 'unknown';

  let confidence = Number(parsed['confidence']);
  if (!Number.isFinite(confidence)) confidence = 0;
  confidence = Math.max(0, Math.min(1, confidence));

  const reason =
    typeof parsed['reason'] === 'string' && parsed['reason'].trim()
      ? parsed['reason'].trim().slice(0, 1000)
      : 'no reason given';

  return {
    isRealBusiness,
    // Keep unrecognised categories rather than discarding them — better to see
    // the model inventing a category than to silently map it to "unknown".
    category: (CATEGORIES as readonly string[]).includes(category) ? category : `other:${category}`.slice(0, 60),
    stageGuess: (STAGES as readonly string[]).includes(stageGuess) ? stageGuess : 'unknown',
    confidence,
    reason,
  };
}

// --- API plumbing ----------------------------------------------------------

let client: Anthropic | null = null;

function getClient(): Anthropic {
  if (!env.ANTHROPIC_API_KEY) {
    throw new Error('ANTHROPIC_API_KEY is not set; classification is unavailable');
  }
  client ??= new Anthropic({ apiKey: env.ANTHROPIC_API_KEY });
  return client;
}

const MAX_TOKENS = 512;

function requestParams(input: ClassifierInput) {
  return {
    model: env.CLASSIFIER_MODEL,
    max_tokens: MAX_TOKENS,
    // The taxonomy is identical across every request in the run, so cache it.
    system: [
      {
        type: 'text' as const,
        text: SYSTEM_PROMPT,
        cache_control: { type: 'ephemeral' as const },
      },
    ],
    messages: [{ role: 'user' as const, content: buildUserPrompt(input) }],
    output_config: { format: { type: 'json_schema' as const, schema: OUTPUT_SCHEMA } },
  };
}

/** Pull the text out of a response's content blocks. */
function textOf(content: Anthropic.ContentBlock[]): string {
  return content
    .filter((b): b is Anthropic.TextBlock => b.type === 'text')
    .map((b) => b.text)
    .join('');
}

/** Classify a single domain synchronously. Used by the eval harness. */
export async function classifyOne(input: ClassifierInput): Promise<Classification> {
  try {
    const response = await getClient().messages.create(requestParams(input));
    return parseClassification(textOf(response.content));
  } catch (err) {
    log.error('classifier call failed', err, { apex: input.apex });
    return { ...FALLBACK_CLASSIFICATION, reason: 'classifier call failed' };
  }
}

export interface BatchResult {
  results: Map<string, Classification>;
  batchId: string;
  succeeded: number;
  errored: number;
}

/**
 * Classify many domains through the Message Batches API.
 *
 * Half price, and this workload has no latency requirement — a domain surfaced
 * two hours later is still a domain surfaced the same day. Results come back in
 * arbitrary order, so they are keyed by `custom_id` and never by position.
 */
export async function classifyBatch(
  inputs: ClassifierInput[],
  options: { pollIntervalMs?: number; maxWaitMs?: number } = {},
): Promise<BatchResult> {
  const { pollIntervalMs = 60_000, maxWaitMs = 23 * 3600 * 1000 } = options;
  const results = new Map<string, Classification>();

  if (inputs.length === 0) return { results, batchId: '', succeeded: 0, errored: 0 };

  const anthropic = getClient();

  // custom_id must round-trip the apex. Apexes are unique within a batch and
  // contain only characters the API accepts.
  const batch = await anthropic.messages.batches.create({
    requests: inputs.map((input) => ({
      custom_id: input.apex,
      params: requestParams(input),
    })),
  });

  log.info('classifier batch submitted', { batch_id: batch.id, requests: inputs.length });

  const deadline = Date.now() + maxWaitMs;
  let status = batch.processing_status;

  while (status !== 'ended') {
    if (Date.now() > deadline) {
      log.error('classifier batch did not finish before the deadline', undefined, {
        batch_id: batch.id,
      });
      return { results, batchId: batch.id, succeeded: 0, errored: inputs.length };
    }
    await sleep(pollIntervalMs);
    const current = await anthropic.messages.batches.retrieve(batch.id);
    status = current.processing_status;
    log.debug('classifier batch polling', {
      batch_id: batch.id,
      status,
      counts: current.request_counts,
    });
  }

  let succeeded = 0;
  let errored = 0;

  for await (const entry of await anthropic.messages.batches.results(batch.id)) {
    const apex = entry.custom_id;
    switch (entry.result.type) {
      case 'succeeded': {
        results.set(apex, parseClassification(textOf(entry.result.message.content)));
        succeeded += 1;
        break;
      }
      case 'errored': {
        log.warn('classifier request errored', { apex, error_type: entry.result.error.type });
        results.set(apex, { ...FALLBACK_CLASSIFICATION, reason: 'classifier request errored' });
        errored += 1;
        break;
      }
      default: {
        // canceled or expired — both mean no answer.
        results.set(apex, { ...FALLBACK_CLASSIFICATION, reason: `classifier request ${entry.result.type}` });
        errored += 1;
      }
    }
  }

  log.info('classifier batch complete', { batch_id: batch.id, succeeded, errored });
  return { results, batchId: batch.id, succeeded, errored };
}

export { SYSTEM_PROMPT, OUTPUT_SCHEMA };
