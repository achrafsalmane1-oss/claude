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
 * Reoon Email Verifier adapter (power mode). Untested until a key is
 * provided — verify the response mapping against the account's docs.
 * Requires REOON_API_KEY.
 */
export class ReoonEmailVerifierService implements EmailVerifierService {
  constructor(private apiKey: string) {}

  async verify(email: string): Promise<VerificationResult> {
    const url = `https://emailverifier.reoon.com/api/v1/verify?email=${encodeURIComponent(email)}&key=${this.apiKey}&mode=power`;
    const res = await fetch(url);
    if (!res.ok) return "risky";
    const data = await res.json();
    const status = String(data?.status ?? "").toLowerCase();
    if (status === "safe" || status === "valid" || status === "deliverable") {
      return "deliverable";
    }
    if (status === "invalid" || status === "disabled") return "invalid";
    return "risky";
  }
}
