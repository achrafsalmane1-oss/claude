import { describe, it, expect } from 'vitest';
import { classifyMx, isSelfHostedMx } from '@/enrich/mx';
import { detectParking, extractVisibleText } from '@/enrich/parking';
import { detectTech } from '@/enrich/tech';
import { parseRobots, isPathAllowed, extractTitle, extractMetaDescription, extractLang } from '@/enrich/http';
import { parseRdapResponse, isRedactedValue } from '@/enrich/rdap';

describe('MX classification — the highest-signal cheap filter', () => {
  it('identifies Google Workspace as business email', () => {
    const result = classifyMx([
      { exchange: 'aspmx.l.google.com', priority: 1 },
      { exchange: 'alt1.aspmx.l.google.com', priority: 5 },
    ]);
    expect(result.provider).toBe('Google Workspace');
    expect(result.kind).toBe('business');
    expect(result.isBusinessEmail).toBe(true);
  });

  it('identifies Microsoft 365, matching the longest suffix', () => {
    const result = classifyMx([
      { exchange: 'example-com.mail.protection.outlook.com', priority: 0 },
    ]);
    expect(result.provider).toBe('Microsoft 365');
    expect(result.isBusinessEmail).toBe(true);
  });

  it('treats parking MX as a negative signal', () => {
    const result = classifyMx([{ exchange: 'mail.sedoparking.com', priority: 10 }]);
    expect(result.kind).toBe('parking');
    expect(result.isParkingMx).toBe(true);
    expect(result.isBusinessEmail).toBe(false);
  });

  it('classifies by the highest-priority record, not the first in the array', () => {
    // A domain with Google primary and a hosting fallback is a Google domain.
    const result = classifyMx([
      { exchange: 'mail.hostinger.com', priority: 50 },
      { exchange: 'aspmx.l.google.com', priority: 1 },
    ]);
    expect(result.provider).toBe('Google Workspace');
    expect(result.allProviders).toContain('Hostinger');
  });

  it('reports no MX as none, not unknown', () => {
    expect(classifyMx([]).kind).toBe('none');
    expect(classifyMx([]).isBusinessEmail).toBe(false);
  });

  it('handles RFC 7505 null MX', () => {
    const result = classifyMx([{ exchange: '.', priority: 0 }]);
    expect(result.kind).toBe('none');
    expect(result.isBusinessEmail).toBe(false);
  });

  it('marks an unrecognised exchange as unknown rather than guessing', () => {
    const result = classifyMx([{ exchange: 'mail.some-random-host.example', priority: 10 }]);
    expect(result.kind).toBe('unknown');
    expect(result.isBusinessEmail).toBe(false);
  });

  it('treats mail security gateways as business signal', () => {
    const result = classifyMx([{ exchange: 'mx1-us1.ppe-hosted.com', priority: 10 }]);
    expect(result.kind).toBe('security');
    expect(result.isBusinessEmail).toBe(true);
  });

  it('detects self-hosted mail', () => {
    expect(isSelfHostedMx('example.com', [{ exchange: 'mail.example.com', priority: 10 }])).toBe(true);
    expect(isSelfHostedMx('example.com', [{ exchange: 'aspmx.l.google.com', priority: 1 }])).toBe(false);
  });
});

describe('parking detection', () => {
  it('kills a Sedo parking page on the vendor fingerprint', () => {
    const result = detectParking({
      html: '<html><body><script src="https://sedoparking.com/park.js"></script></body></html>',
      title: 'example.com',
    });
    expect(result.isParked).toBe(true);
    expect(result.vendor).toBe('Sedo');
    expect(result.confidence).toBe('high');
  });

  it('kills a domain that redirects to Afternic', () => {
    const result = detectParking({
      html: '<html></html>',
      finalUrl: 'https://www.afternic.com/domain/example.com',
    });
    expect(result.isParked).toBe(true);
    expect(result.vendor).toBe('Afternic');
  });

  it('kills for-sale language on a thin page', () => {
    const result = detectParking({
      html: '<html><body><h1>example.com</h1><p>This domain is for sale. Make an offer.</p></body></html>',
    });
    expect(result.isParked).toBe(true);
    expect(result.confidence).toBe('high');
  });

  /**
   * The precision case that matters: a real company writing about domains must
   * not be killed by a phrase match.
   */
  it('does NOT kill a substantial page that merely mentions buying domains', () => {
    const filler = 'We help startups pick and register their first domain name. '.repeat(40);
    const result = detectParking({
      html: `<html><body><h1>Acme Naming Co</h1><p>${filler} Wondering how to buy this domain? Read our guide.</p></body></html>`,
      title: 'Acme Naming Co — naming and branding for startups',
    });
    expect(result.isParked).toBe(false);
    expect(result.confidence).toBe('low');
  });

  /**
   * "Coming soon" is a placeholder, not parking. A genuinely new company puts
   * one up constantly — arguably the exact moment we want to catch them.
   */
  it('treats "coming soon" as a placeholder, not a kill', () => {
    const result = detectParking({
      html: '<html><body><h1>Coming soon</h1><p>We are launching in March.</p></body></html>',
      title: 'Coming Soon',
    });
    expect(result.isParked).toBe(false);
    expect(result.isPlaceholder).toBe(true);
  });

  it('kills a server default page', () => {
    const result = detectParking({
      html: '<html><head><title>Welcome to nginx!</title></head><body><h1>Welcome to nginx!</h1></body></html>',
      title: 'Welcome to nginx!',
    });
    expect(result.isParked).toBe(true);
  });

  it('kills a suspended-account page', () => {
    const result = detectParking({
      html: '<html><body><h1>Account Suspended</h1></body></html>',
      title: 'Account Suspended',
    });
    expect(result.isParked).toBe(true);
  });

  it('flags an essentially empty page as a placeholder', () => {
    const result = detectParking({ html: '<html><body></body></html>', title: null });
    expect(result.isPlaceholder).toBe(true);
    expect(result.isParked).toBe(false);
  });

  it('passes a genuine company site through untouched', () => {
    const result = detectParking({
      html: `<html><head><title>Northwind Analytics</title></head><body>
        <h1>Analytics for logistics teams</h1>
        <p>${'Northwind gives freight operators live visibility into their fleet. '.repeat(30)}</p>
        <a href="/pricing">Pricing</a><a href="/careers">Careers</a></body></html>`,
      title: 'Northwind Analytics',
    });
    expect(result.isParked).toBe(false);
    expect(result.isPlaceholder).toBe(false);
    expect(result.confidence).toBe('none');
  });

  it('strips scripts and styles when extracting visible text', () => {
    const text = extractVisibleText(
      '<html><head><style>body{color:red}</style><script>var x = "hidden";</script></head><body><p>Real&nbsp;content</p></body></html>',
    );
    expect(text).toBe('Real content');
    expect(text).not.toContain('hidden');
    expect(text).not.toContain('color');
  });
});

describe('tech fingerprinting', () => {
  it('detects Webflow from its markup', () => {
    const result = detectTech({
      html: '<html data-wf-page="abc" data-wf-site="def"><script src="webflow.js"></script></html>',
      headers: {},
    });
    expect(result.slugs).toContain('webflow');
    expect(result.hasBuildSignal).toBe(true);
  });

  it('detects Shopify and Stripe together', () => {
    const result = detectTech({
      html: '<script src="https://cdn.shopify.com/s/x.js"></script><script src="https://js.stripe.com/v3"></script>',
      headers: {},
    });
    expect(result.slugs).toEqual(expect.arrayContaining(['shopify', 'stripe']));
  });

  it('detects Next.js from either the markup or the header', () => {
    expect(detectTech({ html: '<div id="__next"></div>', headers: {} }).slugs).toContain('nextjs');
    expect(detectTech({ html: '', headers: { 'x-powered-by': 'Next.js' } }).slugs).toContain('nextjs');
  });

  it('detects a CDN but does not count it as a build signal', () => {
    const result = detectTech({ html: '<html></html>', headers: { 'cf-ray': '123abc', server: 'cloudflare' } });
    expect(result.slugs).toContain('cloudflare');
    // A parking page sits behind Cloudflare too, so this must not imply a build.
    expect(result.hasBuildSignal).toBe(false);
  });

  it('returns nothing for a bare page', () => {
    const result = detectTech({ html: '<html><body>hi</body></html>', headers: {} });
    expect(result.slugs).toEqual([]);
    expect(result.hasBuildSignal).toBe(false);
  });
});

describe('robots.txt handling', () => {
  it('applies the wildcard group when there is no specific one', () => {
    const rules = parseRobots('User-agent: *\nDisallow: /private\n', 'novaXBot');
    expect(isPathAllowed(rules, '/')).toBe(true);
    expect(isPathAllowed(rules, '/private/x')).toBe(false);
  });

  it('prefers a group naming our agent over the wildcard', () => {
    const rules = parseRobots(
      'User-agent: *\nDisallow: /\n\nUser-agent: novaXBot\nDisallow:\n',
      'novaXBot',
    );
    expect(isPathAllowed(rules, '/')).toBe(true);
  });

  it('honours a blanket disallow', () => {
    const rules = parseRobots('User-agent: *\nDisallow: /\n', 'novaXBot');
    expect(isPathAllowed(rules, '/')).toBe(false);
  });

  it('lets the longest matching rule win', () => {
    const rules = parseRobots('User-agent: *\nDisallow: /\nAllow: /public\n', 'novaXBot');
    expect(isPathAllowed(rules, '/public/page')).toBe(true);
    expect(isPathAllowed(rules, '/other')).toBe(false);
  });

  it('ignores comments and blank lines', () => {
    const rules = parseRobots('# comment\n\nUser-agent: *  # inline\nDisallow: /x\n', 'novaXBot');
    expect(isPathAllowed(rules, '/x')).toBe(false);
    expect(isPathAllowed(rules, '/y')).toBe(true);
  });

  it('treats an empty robots.txt as fully allowed', () => {
    expect(isPathAllowed(parseRobots('', 'novaXBot'), '/')).toBe(true);
  });

  it('groups consecutive user-agent lines together', () => {
    const rules = parseRobots('User-agent: googlebot\nUser-agent: novaXBot\nDisallow: /nope\n', 'novaXBot');
    expect(isPathAllowed(rules, '/nope')).toBe(false);
  });
});

describe('HTML extraction', () => {
  it('extracts and cleans the title', () => {
    expect(extractTitle('<html><head><title>  Acme &amp; Co  </title></head></html>')).toBe('Acme & Co');
  });

  it('returns null when there is no title', () => {
    expect(extractTitle('<html><body>hi</body></html>')).toBeNull();
  });

  it('extracts a meta description in either attribute order', () => {
    expect(
      extractMetaDescription('<meta name="description" content="We build things.">'),
    ).toBe('We build things.');
    expect(
      extractMetaDescription('<meta content="We build things." name="description">'),
    ).toBe('We build things.');
  });

  it('falls back to og:description', () => {
    expect(extractMetaDescription('<meta property="og:description" content="Social blurb">')).toBe(
      'Social blurb',
    );
  });

  /**
   * Regression from real output: the capture used to cross tag boundaries and
   * return the viewport meta plus everything up to the next quote.
   */
  it('does not run across tag boundaries into the next meta tag', () => {
    const html =
      '<meta name="viewport" content="width=device-width, initial-scale=1.0">' +
      '<meta name="description" content="Actual description here">';
    expect(extractMetaDescription(html)).toBe('Actual description here');
  });

  it('returns null when there is no description meta at all', () => {
    expect(
      extractMetaDescription('<meta name="viewport" content="width=device-width"><title>x</title>'),
    ).toBeNull();
  });

  it('extracts the document language', () => {
    expect(extractLang('<html lang="en-GB">')).toBe('en-gb');
    expect(extractLang('<html>')).toBeNull();
  });
});

describe('RDAP parsing — redaction is the normal case', () => {
  /**
   * This is the real shape returned by rdap.verisign.com for stripe.com on
   * 2026-08-17, trimmed. Note the registrar vCard carries only version and fn,
   * and there is no registrant entity at all — the redaction the spec warns
   * about, in the wild.
   */
  const liveShape = {
    objectClassName: 'domain',
    ldhName: 'STRIPE.COM',
    status: ['client delete prohibited', 'client transfer prohibited'],
    events: [
      { eventAction: 'registration', eventDate: '1995-09-12T04:00:00Z' },
      { eventAction: 'expiration', eventDate: '2027-09-11T04:00:00Z' },
      { eventAction: 'last changed', eventDate: '2025-10-01T01:39:51Z' },
    ],
    entities: [
      {
        roles: ['registrar'],
        handle: '447',
        publicIds: [{ type: 'IANA Registrar ID', identifier: '447' }],
        vcardArray: ['vcard', [['version', {}, 'text', '4.0'], ['fn', {}, 'text', 'MarkMonitor Inc.']]],
      },
    ],
    nameservers: [{ ldhName: 'NS-1087.AWSDNS-07.ORG' }, { ldhName: 'NS-423.AWSDNS-52.COM' }],
  };

  it('parses the registrar, dates and statuses from a live-shaped response', () => {
    const result = parseRdapResponse(liveShape);
    expect(result.registrar).toBe('MarkMonitor Inc.');
    expect(result.registrarIanaId).toBe('447');
    expect(result.createdDate?.toISOString()).toBe('1995-09-12T04:00:00.000Z');
    expect(result.expiresDate?.toISOString()).toBe('2027-09-11T04:00:00.000Z');
    expect(result.statuses).toContain('client transfer prohibited');
    expect(result.nameservers).toContain('ns-1087.awsdns-07.org');
  });

  it('yields no registrant data when the registry publishes none', () => {
    const result = parseRdapResponse(liveShape);
    expect(result.registrantCountry).toBeNull();
    expect(result.registrantState).toBeNull();
  });

  it('keeps country and state when a registry does publish them', () => {
    const result = parseRdapResponse({
      entities: [
        {
          roles: ['registrant'],
          vcardArray: [
            'vcard',
            [
              ['version', {}, 'text', '4.0'],
              ['adr', {}, 'text', ['', '', '', 'Berlin', 'BE', '10115', 'DE']],
            ],
          ],
        },
      ],
    });
    expect(result.registrantCountry).toBe('DE');
    expect(result.registrantState).toBe('BE');
  });

  it('drops redaction placeholders instead of storing them as data', () => {
    const result = parseRdapResponse({
      entities: [
        {
          roles: ['registrant'],
          vcardArray: [
            'vcard',
            [['adr', {}, 'text', ['', '', 'REDACTED FOR PRIVACY', 'REDACTED', 'REDACTED FOR PRIVACY', '', 'REDACTED FOR PRIVACY']]],
          ],
        },
      ],
    });
    expect(result.registrantCountry).toBeNull();
    expect(result.registrantState).toBeNull();
    expect(result.hadRedactions).toBe(true);
  });

  it('records that redaction happened when the registry declares it', () => {
    const result = parseRdapResponse({
      ...liveShape,
      redacted: [{ name: { type: 'Registrant Name' } }],
    });
    expect(result.hadRedactions).toBe(true);
  });

  it('recognises redaction placeholders in their many spellings', () => {
    for (const value of [
      'REDACTED FOR PRIVACY',
      'Not Disclosed',
      'Data Protected',
      'GDPR Masked',
      'Privacy service provided',
      'n/a',
      '',
    ]) {
      expect(isRedactedValue(value)).toBe(true);
    }
    expect(isRedactedValue('MarkMonitor Inc.')).toBe(false);
  });

  it('survives a response with nothing in it', () => {
    const result = parseRdapResponse({});
    expect(result.registrar).toBeNull();
    expect(result.createdDate).toBeNull();
    expect(result.statuses).toEqual([]);
    expect(result.hadRedactions).toBe(false);
  });
});
