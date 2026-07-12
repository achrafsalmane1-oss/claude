export type VerificationResult = "deliverable" | "risky" | "invalid";

export interface EmailVerifierService {
  verify(email: string): Promise<VerificationResult>;
}

/** Mock: ~85% deliverable, 10% risky, 5% invalid. */
export class MockEmailVerifierService implements EmailVerifierService {
  async verify(): Promise<VerificationResult> {
    const r = Math.random();
    if (r < 0.85) return "deliverable";
    if (r < 0.95) return "risky";
    return "invalid";
  }
}

/**
 * Orbisearch adapter. GET /v1/verify?email= with X-API-Key.
 * Response: { status: "valid"|"invalid"|"risky"|"catch-all"|..., ... }.
 * Requires ORBISEARCH_API_KEY.
 */
export class OrbisearchEmailVerifierService implements EmailVerifierService {
  constructor(private apiKey: string) {}

  async verify(email: string): Promise<VerificationResult> {
    const res = await fetch(
      `https://api.orbisearch.com/v1/verify?email=${encodeURIComponent(email)}`,
      { headers: { "X-API-Key": this.apiKey } }
    );
    if (!res.ok) return "risky";
    const data = await res.json();
    const status = String(data?.status ?? "").toLowerCase();
    if (status === "valid" || status === "deliverable" || status === "safe") {
      return "deliverable";
    }
    if (status === "invalid" || status === "undeliverable") return "invalid";
    // catch-all / risky / unknown → risky (we don't cold-email these)
    return "risky";
  }
}
