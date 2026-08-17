import { eq, and } from 'drizzle-orm';
import { db, domainHttp } from '@/db';
import { env, USER_AGENT } from '@/config/env';
import { fetchWithLimits, HttpError } from '@/lib/http';
import { createLogger } from '@/lib/logger';
import { extractApex } from '@/ingest/apex';
import { detectParking, extractVisibleText } from './parking';
import { detectTech } from './tech';

/**
 * HTTP probe (spec §6.3).
 *
 * Fetch the site, capture what a human would see, decide whether it is a
 * parking page. Constraints that matter:
 *
 *  - robots.txt is honoured (spec §10). If it disallows us, we record that we
 *    were disallowed and store no page content at all.
 *  - The User-Agent identifies novaX and carries a contact URL.
 *  - Hard caps on time, redirects and body size, because a probe worker that
 *    reads an unbounded response from a hostile host is a probe worker that dies.
 *  - No headless browser. It would cost ~100x per domain and break the unit
 *    economics the spec sets. A site that renders nothing without JavaScript is
 *    signal we lose, knowingly.
 */

const log = createLogger('enrich.http');

export interface HttpProbeResult {
  apex: string;
  requestedUrl: string | null;
  statusCode: number | null;
  finalUrl: string | null;
  redirectCount: number;
  redirectedOffDomain: boolean;
  title: string | null;
  metaDescription: string | null;
  bodySnippet: string | null;
  lang: string | null;
  tech: string[];
  server: string | null;
  isParked: boolean;
  parkingVendor: string | null;
  parkingReason: string | null;
  isPlaceholder: boolean;
  robotsAllowed: boolean;
  contentLength: number | null;
  responseTimeMs: number | null;
  error?: string;
}

// --- robots.txt ------------------------------------------------------------

interface RobotsRules {
  disallow: string[];
  allow: string[];
}

/**
 * Minimal robots.txt parser.
 *
 * Reads the group for our User-Agent token, falling back to `*`. Deliberately
 * simple: we only ever request `/`, so full path-matching semantics are more
 * machinery than the job needs. Longest-match-wins between allow and disallow is
 * implemented because that is the rule that decides `/` in practice.
 */
export function parseRobots(body: string, agentToken: string): RobotsRules {
  const lines = body.split('\n');
  const groups: { agents: string[]; rules: RobotsRules }[] = [];
  let current: { agents: string[]; rules: RobotsRules } | null = null;
  let lastLineWasAgent = false;

  for (const rawLine of lines) {
    const line = rawLine.split('#')[0]!.trim();
    if (!line) continue;

    const colon = line.indexOf(':');
    if (colon < 0) continue;
    const field = line.slice(0, colon).trim().toLowerCase();
    const value = line.slice(colon + 1).trim();

    if (field === 'user-agent') {
      // Consecutive User-agent lines share one group.
      if (!current || !lastLineWasAgent) {
        current = { agents: [], rules: { disallow: [], allow: [] } };
        groups.push(current);
      }
      current.agents.push(value.toLowerCase());
      lastLineWasAgent = true;
      continue;
    }

    lastLineWasAgent = false;
    if (!current) continue;
    if (field === 'disallow') current.rules.disallow.push(value);
    else if (field === 'allow') current.rules.allow.push(value);
  }

  const token = agentToken.toLowerCase();
  const specific = groups.find((g) => g.agents.some((a) => a === token));
  if (specific) return specific.rules;

  const wildcard = groups.find((g) => g.agents.includes('*'));
  return wildcard?.rules ?? { disallow: [], allow: [] };
}

/** Is `path` allowed by these rules? Longest matching rule wins. */
export function isPathAllowed(rules: RobotsRules, path: string): boolean {
  let longestDisallow = -1;
  let longestAllow = -1;

  for (const rule of rules.disallow) {
    // An empty Disallow means "allow everything" and matches nothing.
    if (rule === '') continue;
    if (path.startsWith(rule)) longestDisallow = Math.max(longestDisallow, rule.length);
  }
  for (const rule of rules.allow) {
    if (rule === '') continue;
    if (path.startsWith(rule)) longestAllow = Math.max(longestAllow, rule.length);
  }

  if (longestDisallow < 0) return true;
  return longestAllow >= longestDisallow;
}

/** Fetch and evaluate robots.txt. Fails open — an unreachable robots.txt is not a ban. */
export async function checkRobots(apex: string): Promise<boolean> {
  if (!env.HTTP_RESPECT_ROBOTS) return true;

  const agentToken = env.USER_AGENT_NAME;
  for (const scheme of ['https', 'http'] as const) {
    try {
      const res = await fetchWithLimits(`${scheme}://${apex}/robots.txt`, {
        timeoutMs: Math.min(env.HTTP_PROBE_TIMEOUT_MS, 5_000),
        maxBytes: 128 * 1024,
        maxRedirects: 2,
      });
      // 404 or any non-2xx means no robots.txt: crawling is permitted.
      if (res.statusCode !== 200) return true;
      return isPathAllowed(parseRobots(res.body, agentToken), '/');
    } catch {
      // Try the other scheme, then fail open.
      continue;
    }
  }
  return true;
}

// --- HTML extraction -------------------------------------------------------

export function extractTitle(html: string): string | null {
  const match = /<title[^>]*>([\s\S]{0,500}?)<\/title>/i.exec(html);
  if (!match?.[1]) return null;
  const title = extractVisibleText(match[1]).trim();
  return title || null;
}

export function extractMetaDescription(html: string): string | null {
  // Attribute order varies, so match either ordering rather than assuming one.
  const patterns = [
    /<meta[^>]+name=["']description["'][^>]+content=["']([\s\S]{0,1000}?)["']/i,
    /<meta[^>]+content=["']([\s\S]{0,1000}?)["'][^>]+name=["']description["']/i,
    /<meta[^>]+property=["']og:description["'][^>]+content=["']([\s\S]{0,1000}?)["']/i,
  ];
  for (const pattern of patterns) {
    const match = pattern.exec(html);
    if (match?.[1]) {
      const description = extractVisibleText(match[1]).trim();
      if (description) return description;
    }
  }
  return null;
}

export function extractLang(html: string): string | null {
  const match = /<html[^>]+lang=["']([a-z]{2}(?:-[a-z0-9]+)?)["']/i.exec(html);
  return match?.[1]?.toLowerCase() ?? null;
}

// --- The probe -------------------------------------------------------------

/** Probe one domain. Never throws: a failure is a recorded result. */
export async function probeDomain(apex: string): Promise<HttpProbeResult> {
  const base: HttpProbeResult = {
    apex,
    requestedUrl: null,
    statusCode: null,
    finalUrl: null,
    redirectCount: 0,
    redirectedOffDomain: false,
    title: null,
    metaDescription: null,
    bodySnippet: null,
    lang: null,
    tech: [],
    server: null,
    isParked: false,
    parkingVendor: null,
    parkingReason: null,
    isPlaceholder: false,
    robotsAllowed: true,
    contentLength: null,
    responseTimeMs: null,
  };

  // Compliance first: if robots.txt says no, we do not fetch the page and we
  // store no content from it.
  const allowed = await checkRobots(apex);
  if (!allowed) {
    log.debug('robots.txt disallows probing', { apex });
    return { ...base, robotsAllowed: false, error: 'disallowed by robots.txt' };
  }

  // https first — a new company's site is https, and http tells us less.
  for (const scheme of ['https', 'http'] as const) {
    const url = `${scheme}://${apex}/`;
    try {
      const res = await fetchWithLimits(url, {
        timeoutMs: env.HTTP_PROBE_TIMEOUT_MS,
        maxBytes: env.HTTP_PROBE_MAX_BYTES,
        maxRedirects: env.HTTP_PROBE_MAX_REDIRECTS,
        headers: {
          accept: 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
          'accept-language': 'en-US,en;q=0.9',
        },
      });

      const visibleText = extractVisibleText(res.body);
      const title = extractTitle(res.body);
      const parking = detectParking({
        html: res.body,
        title,
        finalUrl: res.finalUrl,
        headers: res.headers,
        visibleText,
      });
      const tech = detectTech({ html: res.body, headers: res.headers });

      const finalApex = extractApex(new URL(res.finalUrl).hostname);
      const offDomain = finalApex !== null && finalApex.apex !== apex;

      return {
        ...base,
        requestedUrl: url,
        statusCode: res.statusCode,
        finalUrl: res.finalUrl,
        redirectCount: res.redirectCount,
        redirectedOffDomain: offDomain,
        title,
        metaDescription: extractMetaDescription(res.body),
        // Capped: we keep a snippet for the classifier, never the whole page.
        bodySnippet: visibleText.slice(0, env.BODY_SNIPPET_CHARS) || null,
        lang: extractLang(res.body),
        tech: tech.slugs,
        server: tech.server,
        isParked: parking.isParked,
        parkingVendor: parking.vendor,
        parkingReason: parking.reason,
        isPlaceholder: parking.isPlaceholder,
        contentLength: res.bodyBytes,
        responseTimeMs: res.elapsedMs,
      };
    } catch (err) {
      const message = err instanceof HttpError ? err.message : String(err);
      // https failing is routine (no cert yet); fall through to http.
      if (scheme === 'https') {
        log.debug('https probe failed, trying http', { apex, error: message });
        continue;
      }
      return { ...base, requestedUrl: url, error: message };
    }
  }

  return { ...base, error: 'both https and http failed' };
}

/** Persist a probe result as a new observation, retiring the previous one. */
export async function saveProbeResult(result: HttpProbeResult): Promise<void> {
  await db
    .update(domainHttp)
    .set({ isCurrent: false })
    .where(and(eq(domainHttp.apex, result.apex), eq(domainHttp.isCurrent, true)));

  await db.insert(domainHttp).values({
    apex: result.apex,
    requestedUrl: result.requestedUrl,
    statusCode: result.statusCode,
    finalUrl: result.finalUrl,
    redirectCount: result.redirectCount,
    redirectedOffDomain: result.redirectedOffDomain,
    title: result.title,
    metaDescription: result.metaDescription,
    bodySnippet: result.bodySnippet,
    lang: result.lang,
    tech: result.tech,
    server: result.server,
    isParked: result.isParked,
    parkingVendor: result.parkingVendor,
    parkingReason: result.parkingReason,
    robotsAllowed: result.robotsAllowed,
    contentLength: result.contentLength,
    responseTimeMs: result.responseTimeMs,
    isCurrent: true,
    failureCount: result.error ? 1 : 0,
    lastError: result.error ?? null,
  });
}

export { USER_AGENT };
