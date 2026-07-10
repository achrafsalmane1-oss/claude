export interface FoundEmail {
  email: string;
  confidence: "high" | "medium" | "low";
}

export interface EmailFinderService {
  /** Find a work email for a person at a domain. Null if none found. */
  find(fullName: string, domain: string): Promise<FoundEmail | null>;
}

/** Mock: derives first@domain, succeeds ~90% of the time. */
export class MockEmailFinderService implements EmailFinderService {
  async find(fullName: string, domain: string): Promise<FoundEmail | null> {
    if (Math.random() < 0.1) return null;
    const first = fullName.split(" ")[0]?.toLowerCase() ?? "owner";
    return { email: `${first}@${domain}`, confidence: "high" };
  }
}

/**
 * Real email-finder adapter. Point EMAIL_FINDER_API_URL at the provider's
 * find-by-name endpoint and set EMAIL_FINDER_API_KEY; adjust the request/
 * response mapping to the provider's schema (each of these APIs is a single
 * POST with name+domain and a JSON response — a ~10-line change once the
 * provider is confirmed).
 */
export class HttpEmailFinderService implements EmailFinderService {
  constructor(
    private apiUrl: string,
    private apiKey: string
  ) {}

  async find(fullName: string, domain: string): Promise<FoundEmail | null> {
    const res = await fetch(this.apiUrl, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${this.apiKey}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ full_name: fullName, domain }),
    });
    if (!res.ok) return null;
    const data = await res.json();
    if (!data?.email) return null;
    return {
      email: String(data.email),
      confidence: data.confidence ?? "medium",
    };
  }
}
