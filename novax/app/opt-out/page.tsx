import { requestOptOut, verifyOptOut, TXT_PREFIX } from '@/compliance/opt-out';
import { env } from '@/config/env';

/**
 * Public opt-out page (spec §10).
 *
 * Two steps, both on this page: request a token, then verify the TXT record.
 * No account required — requiring a login to opt out would defeat the point.
 */

export const dynamic = 'force-dynamic';

interface Props {
  searchParams: Promise<{ domain?: string; step?: string; error?: string }>;
}

async function submitRequest(formData: FormData) {
  'use server';
  const { redirect } = await import('next/navigation');
  const domain = String(formData.get('domain') ?? '').trim();
  const email = String(formData.get('email') ?? '').trim();

  try {
    const result = await requestOptOut(domain, email ? { email } : {});
    redirect(`/opt-out?domain=${encodeURIComponent(result.apex)}&step=verify`);
  } catch (err) {
    // `redirect` throws by design; only re-wrap genuine failures.
    if (err instanceof Error && err.message.includes('NEXT_REDIRECT')) throw err;
    redirect(`/opt-out?error=${encodeURIComponent(err instanceof Error ? err.message : 'failed')}`);
  }
}

async function submitVerify(formData: FormData) {
  'use server';
  const { redirect } = await import('next/navigation');
  const domain = String(formData.get('domain') ?? '').trim();
  const result = await verifyOptOut(domain);
  redirect(
    `/opt-out?domain=${encodeURIComponent(domain)}&step=${result.verified ? 'done' : 'verify'}` +
      (result.verified ? '' : `&error=${encodeURIComponent(result.reason)}`),
  );
}

export default async function OptOutPage({ searchParams }: Props) {
  const params = await searchParams;
  const domain = params.domain ?? '';
  const step = params.step ?? 'request';

  let token: string | null = null;
  let alreadyVerified = false;
  if (domain && step !== 'request') {
    try {
      const existing = await requestOptOut(domain);
      token = existing.token;
      alreadyVerified = existing.alreadyVerified;
    } catch {
      token = null;
    }
  }

  return (
    <main className="wrap narrow">
      <h1>Remove your domain from novaX</h1>
      <p className="muted">
        If you own a domain that appears in novaX, you can have it permanently suppressed from every
        output — API, exports, webhooks and digests. Verification is by DNS TXT record, which proves
        you control the domain.
      </p>

      {params.error && (
        <div className="notice error">
          <strong>Not verified.</strong> {params.error}
        </div>
      )}

      {step === 'done' || alreadyVerified ? (
        <div className="notice ok">
          <strong>{domain} is suppressed.</strong> It has been removed from all novaX outputs
          permanently. You can delete the TXT record now.
        </div>
      ) : step === 'verify' && token ? (
        <>
          <h2>Step 2 — publish this TXT record</h2>
          <p className="muted small">
            Add the following TXT record to <code>{domain}</code> (or to{' '}
            <code>_novax.{domain}</code> if your DNS panel will not accept a second TXT record on
            the apex), then press Verify. DNS changes can take a few minutes to propagate.
          </p>
          <pre>
            {domain}. IN TXT &quot;{TXT_PREFIX}
            {token}&quot;
          </pre>
          <form action={submitVerify}>
            <input type="hidden" name="domain" value={domain} />
            <button type="submit">Verify and suppress</button>
          </form>
        </>
      ) : (
        <>
          <h2>Step 1 — tell us the domain</h2>
          <form action={submitRequest}>
            <label className="field">
              Domain
              <input name="domain" placeholder="example.com" required defaultValue={domain} />
            </label>
            <label className="field" style={{ marginTop: 8 }}>
              Email (optional, used only to confirm this request)
              <input name="email" type="email" placeholder="you@example.com" />
            </label>
            <div style={{ marginTop: 12 }}>
              <button type="submit">Continue</button>
            </div>
          </form>
        </>
      )}

      <h2>What we hold</h2>
      <p className="muted small">
        novaX records company-level signals about domains: DNS configuration, public web page
        content, and registry (RDAP) data. We never store registrant names, email addresses, phone
        numbers or street addresses that the registry redacts, and we do not attempt to circumvent
        redaction. Questions: <a href={env.CONTACT_URL}>{env.CONTACT_URL}</a>.
      </p>
    </main>
  );
}
