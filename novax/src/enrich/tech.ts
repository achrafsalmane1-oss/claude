import { TECH_FINGERPRINTS, type TechFingerprint } from './data/tech-fingerprints';

/**
 * Technology fingerprinting from response headers and HTML (spec §6.5).
 */

export interface TechInput {
  html: string;
  headers: Record<string, string>;
}

export interface TechResult {
  /** Detected technology slugs, e.g. ['webflow', 'cloudflare', 'stripe']. */
  slugs: string[];
  /** Human-readable names, same order. */
  names: string[];
  /**
   * True when at least one detected technology implies a human deliberately
   * built something — as opposed to a CDN a parking page would also sit behind.
   */
  hasBuildSignal: boolean;
  server: string | null;
}

function matchesHeaders(fp: TechFingerprint, headers: Record<string, string>): boolean {
  for (const rule of fp.headers ?? []) {
    const value = headers[rule.name.toLowerCase()];
    if (value === undefined) continue;
    // An empty `contains` means presence of the header alone is the signal.
    if (rule.contains === '' || value.toLowerCase().includes(rule.contains)) return true;
  }
  return false;
}

function matchesHtml(fp: TechFingerprint, html: string): boolean {
  for (const needle of fp.html ?? []) {
    if (html.includes(needle)) return true;
  }
  return false;
}

export function detectTech(input: TechInput): TechResult {
  const html = (input.html ?? '').toLowerCase();
  const headers: Record<string, string> = {};
  for (const [k, v] of Object.entries(input.headers ?? {})) headers[k.toLowerCase()] = v;

  const slugs: string[] = [];
  const names: string[] = [];
  let hasBuildSignal = false;

  for (const fp of TECH_FINGERPRINTS) {
    if (matchesHeaders(fp, headers) || matchesHtml(fp, html)) {
      slugs.push(fp.slug);
      names.push(fp.name);
      if (fp.buildSignal) hasBuildSignal = true;
    }
  }

  return {
    slugs,
    names,
    hasBuildSignal,
    server: headers['server'] ?? null,
  };
}
