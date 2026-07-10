import type { Mandate } from "@/generated/prisma/client";

// A raw lead as produced by the sourcing layer, before email enrichment.
export interface SourcedLead {
  ownerName: string;
  ownerTitle: string;
  linkedinUrl: string;
  companyName: string;
  domain: string;
  description: string;
  headcount: number;
  estRevenueUsd: number;
  location: string;
}

export interface LeadSourcingService {
  /**
   * Source up to `count` owners matching the mandate. The real Clay-backed
   * implementation is asynchronous (results arrive on /api/webhooks/clay);
   * it returns whatever is immediately available and triggers sourcing for
   * the rest. The mock returns synthetic leads synchronously.
   */
  source(mandate: Mandate, count: number): Promise<SourcedLead[]>;
}

const FIRST = ["Ray","Carol","Miguel","Denise","Hank","Gloria","Walt","Rosa","Earl","Janet","Sam","Teresa","Doug","Alma","Pete","Diane","Russ","Elena","Chuck","Marcy","Lou","Faye","Vic","Brenda","Tom","Yolanda","Bud","Marlene","Gary","Rosa"];
const LAST = ["Hutchins","Delgado","Bowers","Trevino","Mercer","Okafor","Vance","Salas","Whitfield","Pruett","Langley","Serrano","Boyd","Nunez","Holt","Castillo","Marsh","Pham","Redding","Cantu","Ellison","Barr","Keller","Stroud","Draper","Ybarra","Ainsley","Corbin","McAdams","Ferris"];
const PREFIX = ["Summit","Heritage","Cornerstone","Frontier","Legacy","Beacon","Harbor","Crestline","Meridian","Northgate","Silverline","Stonebridge","Clearwater","Highpoint","Redwood","Bluffside","Eastfield","Granite","Willow Creek","Fairview","Oakline","Brightpath","Ridgeway","Lakeshore","Ironwood","Kingsley","Maplewood","Pinnacle","Southbend","Trailhead"];

export class MockLeadSourcingService implements LeadSourcingService {
  async source(mandate: Mandate, count: number): Promise<SourcedLead[]> {
    const industry = mandate.industries[0] ?? "Services";
    const geo = mandate.geographies[0] ?? "United States";
    const noun = industry.split(/[\s/]+/)[0];
    const stamp = Date.now().toString(36).slice(-4);

    return Array.from({ length: count }, (_, i) => {
      const companyName = `${PREFIX[i % PREFIX.length]} ${noun} ${i % 3 === 0 ? "Group" : i % 3 === 1 ? "Co." : "Partners"}`;
      const ownerName = `${FIRST[Math.floor(Math.random() * FIRST.length)]} ${LAST[Math.floor(Math.random() * LAST.length)]}`;
      const domain = `${companyName.toLowerCase().replace(/[^a-z0-9]+/g, "")}${i >= PREFIX.length * 3 ? stamp : ""}.com`.slice(0, 42);
      return {
        ownerName,
        ownerTitle: i % 2 === 0 ? "Owner" : "President",
        linkedinUrl: `https://www.linkedin.com/in/${ownerName.toLowerCase().replace(/\s+/g, "-")}`,
        companyName,
        domain,
        description: `${companyName} is a privately held ${industry.toLowerCase()} company operating in ${geo}.`,
        headcount: 8 + Math.floor(Math.random() * 80),
        estRevenueUsd: (3 + Math.floor(Math.random() * 20)) * 500_000,
        location: geo,
      };
    });
  }
}

/**
 * Clay-backed sourcing. Clay has no public API for creating folders/tables
 * per client, so the self-serve design is: ONE pre-built Clay workbook with a
 * webhook-source table. We POST sourcing requests to that webhook carrying
 * `clientId` + the buy-box; a Clay workflow finds matching companies/owners,
 * enriches, and POSTs results back to /api/webhooks/clay. Per-client
 * separation lives in our DB (`clientId` on every row), not in Clay folders.
 *
 * Requires: CLAY_WEBHOOK_URL (the Clay table's webhook source URL).
 */
export class ClayLeadSourcingService implements LeadSourcingService {
  constructor(private webhookUrl: string) {}

  async source(mandate: Mandate, count: number): Promise<SourcedLead[]> {
    await fetch(this.webhookUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        clientId: mandate.userId,
        count,
        industries: mandate.industries,
        geographies: mandate.geographies,
        revenueMinUsd: mandate.revenueMinUsd,
        revenueMaxUsd: mandate.revenueMaxUsd,
        employeesMin: mandate.employeesMin,
        employeesMax: mandate.employeesMax,
        keywords: mandate.businessModelKeywords,
        exclusions: mandate.hardExclusions,
      }),
    });
    // Results arrive asynchronously via /api/webhooks/clay.
    return [];
  }
}
