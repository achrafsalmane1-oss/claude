import { db } from "@/lib/db";
import type { FunnelCounts, OutreachService, SenderIdentity } from "./types";

/**
 * Mock outreach engine. The real implementation provisions sending
 * infrastructure and runs multi-channel sequences via external providers;
 * this one just records state and lets the seeded pipeline stand in for a
 * live one. Per-stage counts are computed from the Prospect table, which is
 * exactly what the real implementation would sync into.
 */
export class MockOutreachService implements OutreachService {
  async provisionIdentity(userId: string, identity: SenderIdentity) {
    console.log(
      `[outreach:mock] provisioning identity for user ${userId}: ${identity.name} <${identity.company}> — warmup started`
    );
  }

  async startOutreach(userId: string) {
    console.log(`[outreach:mock] outreach started for user ${userId}`);
    // Sourcing and enrichment are active from day one (outreach itself waits
    // for day 11), so a fresh account's dashboard is never empty. The real
    // implementation streams these in from the sourcing engine.
    const existing = await db.prospect.count({ where: { userId } });
    if (existing > 0) return;

    const mandate = await db.mandate.findUnique({ where: { userId } });
    const industry = mandate?.industries[0] ?? "Services";
    const geo = mandate?.geographies[0] ?? "United States";

    const first = ["Ray", "Carol", "Miguel", "Denise", "Hank", "Gloria", "Walt", "Rosa", "Earl", "Janet", "Sam", "Teresa", "Doug", "Alma", "Pete", "Diane", "Russ", "Elena", "Chuck", "Marcy", "Lou", "Faye", "Vic", "Brenda"];
    const last = ["Hutchins", "Delgado", "Bowers", "Trevino", "Mercer", "Okafor", "Vance", "Salas", "Whitfield", "Pruett", "Langley", "Serrano", "Boyd", "Nunez", "Holt", "Castillo", "Marsh", "Pham", "Redding", "Cantu", "Ellison", "Barr", "Keller", "Stroud"];
    const prefix = ["Summit", "Heritage", "Cornerstone", "Frontier", "Legacy", "Beacon", "Harbor", "Crestline", "Meridian", "Northgate", "Silverline", "Stonebridge", "Clearwater", "Highpoint", "Redwood", "Bluffside", "Eastfield", "Granite", "Willow Creek", "Fairview", "Oakline", "Brightpath", "Ridgeway", "Lakeshore"];
    const noun = industry.split(/[\s/]+/)[0];

    const count = 24 + Math.floor(Math.random() * 12);
    const now = Date.now();
    const rows = Array.from({ length: count }, (_, i) => {
      const companyName = `${prefix[i % prefix.length]} ${noun} ${i % 3 === 0 ? "Group" : i % 3 === 1 ? "Co." : "Partners"}`;
      const ownerName = `${first[i % first.length]} ${last[(i * 7) % last.length]}`;
      const domain = `${companyName.toLowerCase().replace(/[^a-z0-9]+/g, "")}.com`.slice(0, 40);
      const enriched = i % 5 !== 4; // enrichment lags sourcing slightly
      const sourcedAt = new Date(now - Math.floor(Math.random() * 20) * 3_600_000);
      return {
        userId,
        stage: (enriched ? "ENRICHED" : "SOURCED") as "ENRICHED" | "SOURCED",
        ownerName,
        ownerTitle: i % 2 === 0 ? "Owner" : "President",
        linkedinUrl: `https://www.linkedin.com/in/${ownerName.toLowerCase().replace(/\s+/g, "-")}`,
        companyName,
        domain,
        description: `${companyName} is a privately held ${industry.toLowerCase()} company operating in ${geo}.`,
        headcount: 8 + Math.floor(Math.random() * 80),
        estRevenueUsd: (3 + Math.floor(Math.random() * 20)) * 500_000,
        location: geo,
        sourcedAt,
        enrichedAt: enriched
          ? new Date(sourcedAt.getTime() + 2 * 3_600_000)
          : null,
      };
    });
    await db.prospect.createMany({ data: rows });
  }

  async getFunnelCounts(userId: string): Promise<FunnelCounts> {
    const [sourced, enriched, contacted, replied, byDisposition] =
      await Promise.all([
        db.prospect.count({ where: { userId } }),
        db.prospect.count({
          where: { userId, stage: { in: ["ENRICHED", "CONTACTED", "REPLIED"] } },
        }),
        db.prospect.count({
          where: { userId, stage: { in: ["CONTACTED", "REPLIED"] } },
        }),
        db.prospect.count({ where: { userId, stage: "REPLIED" } }),
        db.prospect.groupBy({
          by: ["replyDisposition"],
          where: { userId, stage: "REPLIED" },
          _count: true,
        }),
      ]);

    const count = (d: string) =>
      byDisposition.find((g) => g.replyDisposition === d)?._count ?? 0;

    return {
      sourced,
      enriched,
      contacted,
      replied,
      notInterested: count("NOT_INTERESTED"),
      notNow: count("NOT_NOW"),
      interested: count("INTERESTED"),
    };
  }
}
