/**
 * Seeds a realistic demo account (demo@havenx.app) with a live-looking
 * pipeline: 25 days of history, a full funnel, interested introductions with
 * real-feeling replies, notifications, and daily snapshots for the chart.
 */
import "dotenv/config";
import { PrismaPg } from "@prisma/adapter-pg";
import {
  PrismaClient,
  type ProspectStage,
  type ReplyDisposition,
} from "../src/generated/prisma/client";

const db = new PrismaClient({
  adapter: new PrismaPg({ connectionString: process.env.DATABASE_URL }),
});

const DAY = 86_400_000;
const NOW = Date.now();
const STARTED_AT = new Date(NOW - 24 * DAY); // day 25 of membership

// Deterministic PRNG so reseeding produces the same demo
let seedState = 42;
function rand() {
  seedState |= 0;
  seedState = (seedState + 0x6d2b79f5) | 0;
  let t = Math.imul(seedState ^ (seedState >>> 15), 1 | seedState);
  t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}
const pick = <T,>(arr: T[]) => arr[Math.floor(rand() * arr.length)];
const between = (min: number, max: number) =>
  Math.floor(min + rand() * (max - min));

const FIRST = ["Ray","Dale","Carol","Miguel","Hank","Denise","Tom","Gloria","Walt","Brenda","Sam","Rosa","Earl","Janet","Vic","Marlene","Doug","Teresa","Bud","Alma","Chuck","Yolanda","Pete","Diane","Russ","Elena","Gary","Faye","Lou","Marcy"];
const LAST = ["Hutchins","Delgado","Bowers","Trevino","Mercer","Okafor","Ainsley","Vance","Corbin","Salas","Whitfield","Pruett","Langley","Serrano","McAdams","Boyd","Keller","Nunez","Draper","Holt","Ferris","Castillo","Marsh","Ybarra","Stroud","Pham","Redding","Cantu","Ellison","Barr"];

const PREFIX = ["Lone Star","Gulf Coast","Hill Country","Bluebonnet","Rio Grande","Piney Woods","Brazos","Alamo","Cypress","Trinity","Red River","Palmetto","Peach State","Magnolia","Blue Ridge","Coastal Bend","Panhandle","Bayou","Longhorn","Prairie","Summit","Heritage","Cornerstone","Frontier","Legacy"];
const SUFFIX = ["Mechanical","Air Systems","Climate Control","HVAC Services","Comfort Solutions","Heating & Air","Cooling Co.","Air Conditioning","Mechanical Contractors","Refrigeration","Building Services","Airflow Systems"];
const CITY = ["Austin, TX","Houston, TX","San Antonio, TX","Dallas, TX","Fort Worth, TX","El Paso, TX","Waco, TX","Lubbock, TX","Corpus Christi, TX","Tyler, TX","Atlanta, GA","Savannah, GA","Charlotte, NC","Raleigh, NC","Nashville, TN","Knoxville, TN","Birmingham, AL","Jackson, MS","Baton Rouge, LA","Tulsa, OK"];

function slug(s: string) {
  return s.toLowerCase().replace(/[^a-z0-9]+/g, "").slice(0, 22);
}

type SeedProspect = {
  ownerName: string;
  ownerTitle: string;
  linkedinUrl: string;
  companyName: string;
  domain: string;
  description: string;
  incorporatedOn: Date;
  headcount: number;
  estRevenueUsd: number;
  location: string;
  stage: ProspectStage;
  replyDisposition: ReplyDisposition | null;
  replyText: string | null;
  sourcedAt: Date;
  enrichedAt: Date | null;
  contactedAt: Date | null;
  repliedAt: Date | null;
  contactEmail: string | null;
  contactPhone: string | null;
  introStatus: "NEW" | "CLAIMED";
  claimedAt: Date | null;
};

const INTERESTED_REPLIES = [
  {
    reply:
      "Honestly, your timing is pretty good. I turn 64 this fall and my kids have zero interest in the business. I'd want to make sure my guys are taken care of, but yes — I'd take that conversation.",
    title: "Owner & President",
    daysAgo: 0.2,
    claimed: false,
  },
  {
    reply:
      "We've had brokers sniff around before and I ignored all of them, but your note actually read like you knew what we do. What kind of multiple are you seeing for shops our size? Open to a call next week.",
    title: "Founder & CEO",
    daysAgo: 1.1,
    claimed: false,
  },
  {
    reply:
      "Interesting. My partner and I have been talking about an exit for about a year — he wants out sooner than I do. Send me what you'd need from us and let's set something up after the 15th.",
    title: "Co-Owner",
    daysAgo: 2.4,
    claimed: false,
  },
  {
    reply:
      "You caught me at the right time. Just wrapped our best year ever ($6.2M, best margins since covid) and I promised my wife this is my last summer running crews. Happy to talk.",
    title: "Owner",
    daysAgo: 4.0,
    claimed: false,
  },
  {
    reply:
      "Not actively selling, but I'm 58 and there's no succession plan, so I'd be foolish not to listen. Prefer a call over email — afternoons are best, we're slammed in the mornings.",
    title: "President",
    daysAgo: 6.5,
    claimed: true,
  },
  {
    reply:
      "Yes, interested. We did $4.8M last year with about $900K to the bottom line. Before anything else I'd want to understand how you'd handle my long-tenured office manager. When can we talk?",
    title: "Owner & General Manager",
    daysAgo: 9.0,
    claimed: true,
  },
];

const NOT_NOW_REPLIES = [
  "Appreciate the note, but we just signed a 3-year municipal contract I want to see through. Check back with me around this time next year.",
  "Flattered, but I told myself I'd run it until my youngest finishes college. Two more years. Keep my info.",
  "Not right now — mid-season for us. If you're still buying in the fall I'd be open to a conversation then.",
  "Too early for me, but ask again next year.",
];

const NOT_INTERESTED_REPLIES = [
  "Not interested, please take me off your list.",
  "The business isn't for sale. Good luck out there.",
  "No thanks — third generation family company, it stays in the family.",
  "Not interested. We just did our own acquisition, we're buyers not sellers.",
  "No thanks, not for sale.",
  "Stop contacting me.",
  "Not interested at this time.",
  "We're not for sale, but if you're buying my competitor across town I'll help you diligence him for free, ha.",
  "Please remove me from your outreach.",
  "Not interested.",
  "No — and how did you get this contact?",
  "Not for sale. Don't contact me again.",
  "Not interested, thanks anyway.",
  "We're good, thanks.",
];

function makeProspects(): SeedProspect[] {
  const prospects: SeedProspect[] = [];
  const usedNames = new Set<string>();

  const TOTAL = 187;
  const ENRICHED = 134;
  const CONTACTED = 96;
  const REPLIED = 24; // 6 interested, 4 not-now, 14 not-interested

  for (let i = 0; i < TOTAL; i++) {
    let companyName = "";
    do {
      companyName = `${pick(PREFIX)} ${pick(SUFFIX)}`;
    } while (usedNames.has(companyName));
    usedNames.add(companyName);

    const ownerName = `${pick(FIRST)} ${pick(LAST)}`;
    const domain = `${slug(companyName)}.com`;
    const location = pick(CITY);
    const headcount = between(8, 95);
    const estRevenueUsd = between(4, 28) * 500_000;
    const incorporatedOn = new Date(between(1988, 2016), between(0, 11), between(1, 27));

    // Newer prospects are sourced more recently; replied ones earliest.
    const isReplied = i < REPLIED;
    const isContacted = i < CONTACTED;
    const isEnriched = i < ENRICHED;

    const sourcedDaysAgo = isReplied
      ? between(12, 23)
      : isContacted
        ? between(6, 20)
        : isEnriched
          ? between(2, 16)
          : between(0, 10);
    const sourcedAt = new Date(NOW - sourcedDaysAgo * DAY - between(0, 20) * 3_600_000);
    const enrichedAt = isEnriched
      ? new Date(sourcedAt.getTime() + between(4, 40) * 3_600_000)
      : null;
    const contactedAt =
      isContacted && enrichedAt
        ? new Date(
            Math.max(
              enrichedAt.getTime() + between(6, 30) * 3_600_000,
              STARTED_AT.getTime() + 10 * DAY // outreach never predates day 11
            )
          )
        : null;

    let replyDisposition: ReplyDisposition | null = null;
    let replyText: string | null = null;
    let repliedAt: Date | null = null;
    let ownerTitle = pick(["Owner", "President", "Founder", "Owner & President", "CEO"]);
    let contactEmail: string | null = null;
    let contactPhone: string | null = null;
    let introStatus: "NEW" | "CLAIMED" = "NEW";
    let claimedAt: Date | null = null;

    if (isReplied && contactedAt) {
      if (i < 6) {
        const r = INTERESTED_REPLIES[i];
        replyDisposition = "INTERESTED";
        replyText = r.reply;
        ownerTitle = r.title;
        repliedAt = new Date(NOW - r.daysAgo * DAY);
        contactEmail = `${ownerName.split(" ")[0].toLowerCase()}@${domain}`;
        contactPhone = `(${between(210, 979)}) 555-0${between(100, 199)}`;
        if (r.claimed) {
          introStatus = "CLAIMED";
          claimedAt = new Date(repliedAt.getTime() + between(2, 20) * 3_600_000);
        }
      } else if (i < 10) {
        replyDisposition = "NOT_NOW";
        replyText = NOT_NOW_REPLIES[i - 6];
        repliedAt = new Date(contactedAt.getTime() + between(8, 90) * 3_600_000);
      } else {
        replyDisposition = "NOT_INTERESTED";
        replyText = NOT_INTERESTED_REPLIES[i - 10];
        repliedAt = new Date(contactedAt.getTime() + between(4, 70) * 3_600_000);
      }
    }

    prospects.push({
      ownerName,
      ownerTitle,
      linkedinUrl: `https://www.linkedin.com/in/${ownerName.toLowerCase().replace(/\s+/g, "-")}-${slug(companyName).slice(0, 8)}`,
      companyName,
      domain,
      description: `${companyName} is a ${location.split(",")[1].trim()}-based commercial and residential services company (${pick(["HVAC installation and maintenance", "mechanical contracting", "climate control and refrigeration", "heating and air services"])}) serving the ${location.split(",")[0]} metro. ${pick(["Long-standing commercial maintenance contracts.", "Strong recurring service-agreement base.", "Route-based residential service model.", "Mix of new construction and service work."])}`,
      incorporatedOn,
      headcount,
      estRevenueUsd,
      location,
      stage: isReplied
        ? "REPLIED"
        : isContacted
          ? "CONTACTED"
          : isEnriched
            ? "ENRICHED"
            : "SOURCED",
      replyDisposition,
      replyText,
      sourcedAt,
      enrichedAt,
      contactedAt,
      repliedAt,
      contactEmail,
      contactPhone,
      introStatus,
      claimedAt,
    });
  }
  return prospects;
}

async function main() {
  console.log("Seeding demo account…");

  // Idempotent: wipe and recreate the demo user
  await db.user.deleteMany({ where: { email: "demo@havenx.app" } });

  const user = await db.user.create({
    data: {
      email: "demo@havenx.app",
      name: "Alex Morgan",
      subscription: {
        create: {
          status: "ACTIVE",
          startedAt: STARTED_AT,
          outreachStartsAt: new Date(STARTED_AT.getTime() + 10 * DAY),
          firstCycleEndsAt: new Date(STARTED_AT.getTime() + 40 * DAY),
          currentPeriodEnd: new Date(STARTED_AT.getTime() + 40 * DAY),
        },
      },
      mandate: {
        create: {
          active: true,
          industries: ["HVAC services", "Mechanical contracting", "Plumbing services"],
          geographies: ["Texas", "Southeast US"],
          revenueMinUsd: 2_000_000,
          revenueMaxUsd: 15_000_000,
          ebitdaMinUsd: 400_000,
          ebitdaMaxUsd: 2_500_000,
          employeesMin: 10,
          employeesMax: 100,
          businessModelKeywords: ["recurring revenue", "B2B", "service agreements", "route-based"],
          mustHaves:
            "Second layer of management in place. At least 40% of revenue from recurring service agreements.",
          hardExclusions:
            "No franchises. No single-customer concentration above 40%. No new-construction-only shops.",
          ownerSituations: ["Retirement", "Succession", "Owner burnout"],
          senderName: "Alex Morgan",
          senderCompany: "Morgan Capital Partners",
          senderSignature:
            "Alex Morgan\nManaging Partner, Morgan Capital Partners",
          senderReplyToName: "Alex Morgan — Morgan Capital",
          thesis:
            "Buying founder-led HVAC and mechanical services companies in Texas and the Southeast with $400K–$2.5M EBITDA, where the owner wants a respectful exit and the team stays.",
        },
      },
    },
  });

  const prospects = makeProspects();
  await db.prospect.createMany({
    data: prospects.map((p) => ({ ...p, userId: user.id })),
  });

  // Daily cumulative snapshots for the chart (day the mandate went live → today)
  const days = 25;
  const totals = {
    sourced: prospects.length,
    enriched: prospects.filter((p) => p.enrichedAt).length,
    contacted: prospects.filter((p) => p.contactedAt).length,
    replied: prospects.filter((p) => p.repliedAt).length,
    interested: prospects.filter((p) => p.replyDisposition === "INTERESTED").length,
  };
  const curve = (f: number, total: number, startDay = 0) => {
    if (f * days <= startDay) return 0;
    const progress = (f * days - startDay) / (days - startDay);
    return Math.round(total * Math.pow(Math.min(1, progress), 1.35));
  };
  await db.funnelSnapshot.createMany({
    data: Array.from({ length: days }, (_, i) => {
      const f = (i + 1) / days;
      return {
        userId: user.id,
        date: new Date(STARTED_AT.getTime() + (i + 1) * DAY),
        sourced: curve(f, totals.sourced),
        enriched: curve(f, totals.enriched, 1),
        contacted: curve(f, totals.contacted, 10),
        replied: curve(f, totals.replied, 12),
        interested: curve(f, totals.interested, 13),
      };
    }),
  });

  // Notifications: welcome + mandate + the freshest interested replies
  const interested = prospects
    .filter((p) => p.replyDisposition === "INTERESTED")
    .sort((a, b) => b.repliedAt!.getTime() - a.repliedAt!.getTime());

  await db.notification.createMany({
    data: [
      ...interested.slice(0, 3).map((p, idx) => ({
        userId: user.id,
        type: "interested_reply",
        title: "An owner just replied with interest",
        body: `${p.ownerName} at ${p.companyName} is open to a conversation. View the introduction in your dashboard.`,
        href: "/dashboard/interested",
        createdAt: p.repliedAt!,
        readAt: idx < 2 ? null : p.repliedAt,
      })),
      {
        userId: user.id,
        type: "mandate_active",
        title: "Your buy-box is live",
        body: "Sourcing has started for your mandate. Outreach in your name begins on day 11, after infrastructure warmup completes.",
        href: "/dashboard",
        createdAt: STARTED_AT,
        readAt: STARTED_AT,
      },
      {
        userId: user.id,
        type: "welcome",
        title: "Welcome to HavenX",
        body: "Your outreach infrastructure is being provisioned. Days 1-10 cover setup and warmup — outreach begins day 11.",
        href: "/dashboard",
        createdAt: STARTED_AT,
        readAt: STARTED_AT,
      },
    ],
  });

  console.log(
    `Seeded: ${prospects.length} prospects (${totals.enriched} enriched, ${totals.contacted} contacted, ${totals.replied} replied, ${totals.interested} interested), ${days} snapshots.`
  );
  console.log("Demo login: demo@havenx.app (or use “View live demo” on the homepage)");
}

main()
  .catch((e) => {
    console.error(e);
    process.exit(1);
  })
  .finally(() => db.$disconnect());
