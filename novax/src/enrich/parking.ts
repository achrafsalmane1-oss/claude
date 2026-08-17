import {
  PARKING_VENDORS,
  FOR_SALE_PHRASES,
  PLACEHOLDER_PHRASES,
  PARKING_TITLES,
} from './data/parking-patterns';

/**
 * Parking detection.
 *
 * Confidence tiers matter here, and getting them wrong costs precision in both
 * directions:
 *
 *   - A vendor fingerprint (Sedo, Afternic, Bodis...) is conclusive. Kill it.
 *   - For-sale language is conclusive *on a short page*. A real company's blog
 *     might discuss buying domains; a 200-word page saying "make an offer" is
 *     not a company.
 *   - "Coming soon" is NOT conclusive. A genuinely new company puts up a
 *     coming-soon page all the time — that is arguably the exact moment we want
 *     to catch them. It is recorded as a placeholder and scored down, not killed.
 */

export interface ParkingInput {
  html: string;
  title?: string | null;
  finalUrl?: string | null;
  headers?: Record<string, string>;
  /** Visible text with markup stripped, used for length heuristics. */
  visibleText?: string | null;
}

export interface ParkingResult {
  isParked: boolean;
  vendor: string | null;
  reason: string | null;
  /** True for a "coming soon" style page: not parked, but not a business yet. */
  isPlaceholder: boolean;
  confidence: 'high' | 'medium' | 'low' | 'none';
}

const NOT_PARKED: ParkingResult = {
  isParked: false,
  vendor: null,
  reason: null,
  isPlaceholder: false,
  confidence: 'none',
};

/** Strip tags/scripts/styles down to readable text. */
export function extractVisibleText(html: string): string {
  return html
    .replace(/<script\b[^>]*>[\s\S]*?<\/script>/gi, ' ')
    .replace(/<style\b[^>]*>[\s\S]*?<\/style>/gi, ' ')
    .replace(/<noscript\b[^>]*>[\s\S]*?<\/noscript>/gi, ' ')
    .replace(/<!--[\s\S]*?-->/g, ' ')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/\s+/g, ' ')
    .trim();
}

export function detectParking(input: ParkingInput): ParkingResult {
  const html = (input.html ?? '').toLowerCase();
  const title = (input.title ?? '').toLowerCase().trim();
  const finalUrl = (input.finalUrl ?? '').toLowerCase();
  const text = (input.visibleText ?? extractVisibleText(input.html ?? '')).toLowerCase();

  // --- Tier 1: a known parking vendor is serving this. Conclusive. ---------
  for (const pattern of PARKING_VENDORS) {
    for (const needle of pattern.url ?? []) {
      if (finalUrl.includes(needle)) {
        return {
          isParked: true,
          vendor: pattern.vendor,
          reason: `redirects to ${pattern.vendor} (${needle})`,
          isPlaceholder: false,
          confidence: 'high',
        };
      }
    }
    for (const needle of pattern.html ?? []) {
      if (html.includes(needle)) {
        return {
          isParked: true,
          vendor: pattern.vendor,
          reason: `page contains ${pattern.vendor} parking fingerprint`,
          isPlaceholder: false,
          confidence: 'high',
        };
      }
    }
    for (const header of pattern.header ?? []) {
      const value = input.headers?.[header.name.toLowerCase()];
      if (value && value.toLowerCase().includes(header.value)) {
        return {
          isParked: true,
          vendor: pattern.vendor,
          reason: `${header.name} header identifies ${pattern.vendor}`,
          isPlaceholder: false,
          confidence: 'high',
        };
      }
    }
  }

  // --- Tier 2: a conclusive title -----------------------------------------
  for (const parkedTitle of PARKING_TITLES) {
    if (title === parkedTitle || title.startsWith(`${parkedTitle} `) || title.endsWith(` ${parkedTitle}`)) {
      const placeholder = parkedTitle === 'coming soon' || parkedTitle.includes('under construction');
      return {
        isParked: !placeholder,
        vendor: null,
        reason: `page title is "${input.title}"`,
        isPlaceholder: placeholder,
        confidence: placeholder ? 'medium' : 'high',
      };
    }
  }

  // --- Tier 3: for-sale language on a thin page ---------------------------
  // The length guard is what stops a real company's content tripping this.
  const isThin = text.length < 1_200;
  for (const phrase of FOR_SALE_PHRASES) {
    if (text.includes(phrase)) {
      if (isThin) {
        return {
          isParked: true,
          vendor: null,
          reason: `for-sale language on a ${text.length}-character page: "${phrase}"`,
          isPlaceholder: false,
          confidence: 'high',
        };
      }
      // Present but on a substantial page: note it, do not kill.
      return {
        isParked: false,
        vendor: null,
        reason: `mentions "${phrase}" but the page has ${text.length} characters of content`,
        isPlaceholder: false,
        confidence: 'low',
      };
    }
  }

  // --- Tier 4: placeholder / registrar default ----------------------------
  for (const phrase of PLACEHOLDER_PHRASES) {
    if (text.includes(phrase) || title.includes(phrase)) {
      // A server default page ("welcome to nginx") is nobody's business site.
      const isServerDefault =
        phrase.includes('nginx') ||
        phrase.includes('apache') ||
        phrase.includes('it works') ||
        phrase.includes('index of /') ||
        phrase.includes('default') ||
        phrase.includes('suspended');

      return {
        isParked: isServerDefault,
        vendor: null,
        reason: isServerDefault
          ? `server/registrar default page: "${phrase}"`
          : `placeholder page: "${phrase}"`,
        isPlaceholder: !isServerDefault,
        confidence: 'medium',
      };
    }
  }

  // --- Tier 5: an essentially empty page ----------------------------------
  // Not parked in the vendor sense, but nothing here says "company" either.
  if (text.length < 50 && !title) {
    return {
      isParked: false,
      vendor: null,
      reason: `page has almost no content (${text.length} characters, no title)`,
      isPlaceholder: true,
      confidence: 'medium',
    };
  }

  return NOT_PARKED;
}
