import type { Prospect } from "@/generated/prisma/client";
import type { InterestedProspect } from "@/components/dashboard/InterestedCard";

export function serializeProspect(p: Prospect): InterestedProspect {
  return {
    id: p.id,
    ownerName: p.ownerName,
    ownerTitle: p.ownerTitle,
    linkedinUrl: p.linkedinUrl,
    companyName: p.companyName,
    domain: p.domain,
    description: p.description,
    incorporatedOn: p.incorporatedOn?.toISOString() ?? null,
    headcount: p.headcount,
    estRevenueUsd: p.estRevenueUsd,
    location: p.location,
    replyText: p.replyText,
    repliedAt: p.repliedAt?.toISOString() ?? null,
    introStatus: p.introStatus,
    bookingLinkRequested: p.bookingLinkRequested,
    contactEmail: p.introStatus === "CLAIMED" ? p.contactEmail : null,
    contactPhone: p.introStatus === "CLAIMED" ? p.contactPhone : null,
  };
}
