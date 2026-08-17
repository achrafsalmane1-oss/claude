import { NextResponse } from 'next/server';
import { requestOptOut, verifyOptOut } from '@/compliance/opt-out';
import { createLogger } from '@/lib/logger';

/**
 * Public opt-out API (spec §10).
 *
 * Unauthenticated by design — requiring an account to opt out would defeat the
 * purpose. Two actions:
 *
 *   POST /api/opt-out            { "domain": "example.com" }  -> token + TXT record
 *   POST /api/opt-out?verify=1   { "domain": "example.com" }  -> checks DNS, suppresses
 */

const log = createLogger('api.opt-out');

export const dynamic = 'force-dynamic';

export async function POST(request: Request) {
  let body: { domain?: string; email?: string; note?: string };
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: 'invalid JSON body' }, { status: 400 });
  }

  if (!body.domain) {
    return NextResponse.json({ error: 'domain is required' }, { status: 400 });
  }

  const verify = new URL(request.url).searchParams.get('verify');

  try {
    if (verify) {
      const result = await verifyOptOut(body.domain.trim().toLowerCase());
      return NextResponse.json(result, { status: result.verified ? 200 : 409 });
    }

    const result = await requestOptOut(body.domain, {
      ...(body.email ? { email: body.email } : {}),
      ...(body.note ? { note: body.note } : {}),
    });

    return NextResponse.json({
      domain: result.apex,
      verified: result.alreadyVerified,
      txt_record_name: result.apex,
      txt_record_value: result.txtRecord,
      instructions:
        `Publish a TXT record on ${result.apex} (or _novax.${result.apex}) with the value above, ` +
        `then POST to /api/opt-out?verify=1 with the same domain.`,
    });
  } catch (err) {
    log.warn('opt-out request failed', { error: String(err) });
    return NextResponse.json(
      { error: err instanceof Error ? err.message : 'opt-out failed' },
      { status: 400 },
    );
  }
}

export async function GET() {
  return NextResponse.json({
    description: 'novaX opt-out. POST { "domain": "example.com" } to begin.',
    steps: [
      'POST /api/opt-out with your domain to receive a verification token',
      'Publish the returned TXT record on your domain',
      'POST /api/opt-out?verify=1 with the same domain to complete suppression',
    ],
  });
}
