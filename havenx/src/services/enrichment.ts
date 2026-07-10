import type { CompanyProfile, EnrichmentService } from "./types";

/**
 * Mock enrichment. The real implementation calls an enrichment provider
 * (e.g. Clay) with the domain and returns a verified company profile.
 * This one derives a deterministic, plausible profile from the domain so
 * the same input always yields the same output.
 */
export class MockEnrichmentService implements EnrichmentService {
  async enrichDomain(domain: string): Promise<CompanyProfile | null> {
    const seed = [...domain].reduce((a, c) => a + c.charCodeAt(0), 0);
    const name = domain
      .replace(/\.(com|io|co|net|org)$/i, "")
      .split(/[-.]/)
      .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
      .join(" ");

    return {
      companyName: name,
      domain,
      description: `${name} is a privately held company operating in its regional market.`,
      incorporatedOn: new Date(1995 + (seed % 25), seed % 12, (seed % 27) + 1),
      headcount: 10 + (seed % 140),
      estRevenueUsd: (1 + (seed % 18)) * 500_000,
      location: null,
    };
  }
}
