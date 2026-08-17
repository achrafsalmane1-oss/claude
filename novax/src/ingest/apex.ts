import { parse } from 'tldts';

/**
 * Apex (registrable domain) extraction using the Public Suffix List.
 *
 * Naive last-two-labels splitting breaks on `.co.uk` and `.com.au` (spec §5b),
 * so everything goes through `tldts`.
 *
 * A deliberate subtlety: we run with `allowPrivateDomains: false` (the tldts
 * default). We want the domain someone *paid a registrar for*. `github.io` is a
 * registration; `myapp.github.io` is not. With the private section enabled,
 * every Vercel/GitHub Pages/Netlify subdomain would look like a separate new
 * registration and flood the pipeline. Instead they collapse to the platform
 * apex, which the blocklist below then drops.
 */

/**
 * Hosting/platform apexes that appear constantly in CT and are never a new
 * company registration. These are the apexes that `allowPrivateDomains: false`
 * collapses subdomains onto.
 */
export const PLATFORM_APEXES = new Set([
  'github.io',
  'gitlab.io',
  'vercel.app',
  'netlify.app',
  'netlify.com',
  'pages.dev',
  'workers.dev',
  'herokuapp.com',
  'azurewebsites.net',
  'cloudapp.azure.com',
  'amazonaws.com',
  'elasticbeanstalk.com',
  'cloudfront.net',
  'appspot.com',
  'run.app',
  'firebaseapp.com',
  'web.app',
  'googleusercontent.com',
  'wixsite.com',
  'squarespace.com',
  'webflow.io',
  'framer.app',
  'framer.website',
  'myshopify.com',
  'bigcartel.com',
  'wordpress.com',
  'blogspot.com',
  'weebly.com',
  'strikingly.com',
  'notion.site',
  'super.site',
  'zendesk.com',
  'freshdesk.com',
  'intercom-attachments.com',
  'salesforce.com',
  'force.com',
  'hubspotpagebuilder.com',
  'sharepoint.com',
  'onmicrosoft.com',
  'atlassian.net',
  'ngrok.io',
  'ngrok-free.app',
  'trycloudflare.com',
  'replit.dev',
  'repl.co',
  'glitch.me',
  'render.com',
  'onrender.com',
  'railway.app',
  'fly.dev',
  'up.railway.app',
  'surge.sh',
  'gitpod.io',
  'codesandbox.io',
  'stackblitz.io',
  'discordapp.com',
  'akamaized.net',
  'akamai.net',
  'fastly.net',
  'edgekey.net',
  'cdn77.org',
  'b-cdn.net',
  'sendgrid.net',
  'mailgun.org',
  'awsglobalaccelerator.com',
  'duckdns.org',
  'no-ip.org',
  'dynv6.net',
  'freeddns.org',
  // Observed live in CT during the phase 1 verification run: these generate a
  // steady stream of per-tenant certificates that are never new registrations.
  'ts.net',
  'sslip.io',
  'nip.io',
  'localtest.me',
]);

export interface ApexResult {
  apex: string;
  tld: string;
}

/**
 * Normalise a hostname from any source into a comparable form.
 * Strips wildcards, trailing dots, ports, whitespace, and lowercases.
 */
export function normaliseHostname(input: string): string | null {
  if (!input) return null;
  let h = input.trim().toLowerCase();
  if (!h) return null;

  // CT emits wildcards as `*.example.com`. The wildcard tells us nothing beyond
  // the apex, so strip it rather than discard the observation.
  while (h.startsWith('*.')) h = h.slice(2);

  // Some sources emit a trailing dot (fully-qualified form) or a port.
  h = h.replace(/\.+$/, '');
  const colon = h.indexOf(':');
  if (colon > -1) h = h.slice(0, colon);

  // Reject anything that is plainly not a hostname before handing it to the PSL.
  if (!h || h.length > 253) return null;
  if (h.includes(' ') || h.includes('/') || h.includes('@')) return null;
  if (!h.includes('.')) return null;

  return h;
}

/**
 * Extract the registrable apex from a hostname.
 * Returns null for IPs, invalid names, unknown suffixes and platform apexes.
 */
export function extractApex(hostname: string): ApexResult | null {
  const h = normaliseHostname(hostname);
  if (!h) return null;

  const parsed = parse(h);

  // `parse` sets isIp for literal addresses, which CT certs do carry.
  if (parsed.isIp) return null;
  if (!parsed.domain || !parsed.publicSuffix) return null;
  // An unlisted suffix means the PSL does not recognise the TLD — usually an
  // internal or made-up name (`.local`, `.internal`). Not a registration.
  if (parsed.isIcann === false && parsed.isPrivate === false) return null;

  const apex = parsed.domain.toLowerCase();
  if (PLATFORM_APEXES.has(apex)) return null;

  return { apex, tld: parsed.publicSuffix.toLowerCase() };
}

/**
 * Extract unique apexes from a list of certificate SANs.
 * One cert usually carries `example.com` and `www.example.com`, or a wildcard
 * plus the apex; all of them collapse to one result.
 */
export function apexesFromSans(sans: readonly string[]): ApexResult[] {
  const seen = new Map<string, ApexResult>();
  for (const san of sans) {
    const result = extractApex(san);
    if (result && !seen.has(result.apex)) seen.set(result.apex, result);
  }
  return [...seen.values()];
}

/**
 * True when the hostname is a bare apex or `www.` of it — i.e. the cert covers
 * the site itself rather than some deep subdomain. A cert issued for
 * `mail.corp.example.com` is much weaker evidence of a new site than one for
 * `example.com`, and the scoring layer uses this.
 */
export function isApexLevelName(hostname: string): boolean {
  const h = normaliseHostname(hostname);
  if (!h) return false;
  const result = extractApex(h);
  if (!result) return false;
  return h === result.apex || h === `www.${result.apex}`;
}
