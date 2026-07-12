export interface FoundEmail {
  email: string;
  confidence: "high" | "medium" | "low";
}

export interface FindInput {
  fullName: string;
  domain: string;
  linkedinUrl?: string;
}

export interface EmailFinderService {
  /** Find a work email for a person. Null if none found. */
  find(input: FindInput): Promise<FoundEmail | null>;
}

/** Mock: derives first@domain, succeeds ~90% of the time. */
export class MockEmailFinderService implements EmailFinderService {
  async find({ fullName, domain }: FindInput): Promise<FoundEmail | null> {
    if (Math.random() < 0.1) return null;
    const first = fullName.split(" ")[0]?.toLowerCase() ?? "owner";
    return { email: `${first}@${domain}`, confidence: "high" };
  }
}

/**
 * Moltsets adapter. Tries the LinkedIn→best-email endpoint first (highest hit
 * rate when we have a profile URL from sourcing), then falls back to
 * name+company_domain. Both return { results: { email }, status }.
 * Requires MOLTSETS_API_KEY.
 */
export class MoltsetsEmailFinderService implements EmailFinderService {
  private base = "https://api.moltsets.com/api/v1/tools";
  constructor(private apiKey: string) {}

  private async post(tool: string, body: unknown) {
    const res = await fetch(`${this.base}/${tool}`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(body),
    });
    if (!res.ok && res.status !== 404) {
      // 404 = "not_found" (still JSON); other non-2xx are real errors
      const text = await res.text();
      if (!text.trim().startsWith("{")) {
        throw new Error(`Moltsets ${tool} → ${res.status}: ${text}`);
      }
      return JSON.parse(text);
    }
    return res.json();
  }

  async find({ fullName, domain, linkedinUrl }: FindInput): Promise<FoundEmail | null> {
    if (linkedinUrl) {
      const r = await this.post("linkedin_to_best_email", {
        linkedin_url: linkedinUrl,
      }).catch(() => null);
      const email = r?.results?.email;
      if (email) {
        return { email, confidence: r.results.type === "business" ? "high" : "medium" };
      }
    }
    const r = await this.post("search_business_email_by_name", {
      name: fullName,
      company_domain: domain,
    }).catch(() => null);
    const email = r?.results?.email;
    if (email) return { email, confidence: "medium" };
    return null;
  }
}
