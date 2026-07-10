import { getCurrentUser } from "@/lib/session";
import { db } from "@/lib/db";
import InterestedCard from "@/components/dashboard/InterestedCard";
import { serializeProspect } from "../serialize";

export default async function InterestedPage() {
  const user = (await getCurrentUser())!;
  const prospects = await db.prospect.findMany({
    where: { userId: user.id, replyDisposition: "INTERESTED" },
    orderBy: [{ introStatus: "asc" }, { repliedAt: "desc" }],
  });

  const fresh = prospects.filter((p) => p.introStatus === "NEW").length;

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between rounded-3xl border border-line bg-panel px-6 pb-5 pt-6">
        <div>
          <h1 className="display text-[38px] leading-none text-ink">
            Interested
          </h1>
          <p className="mt-2 text-[14px] text-ink-soft">
            Owners in your buy-box who are open to a conversation.{" "}
            {fresh > 0 && (
              <span className="font-semibold text-green-dark">
                {fresh} waiting for you.
              </span>
            )}
          </p>
        </div>
        <div className="text-right">
          <div className="display text-[38px] leading-none text-green-dark">
            {prospects.length}
          </div>
          <div className="text-[12px] text-ink-faint">introductions</div>
        </div>
      </div>

      <div className="space-y-3">
        {prospects.length === 0 ? (
          <p className="rounded-3xl border border-dashed border-line bg-white px-5 py-16 text-center text-[14.5px] text-ink-faint">
            No interested replies yet. Outreach is running — the first
            introductions typically land within the first two weeks after
            warmup.
          </p>
        ) : (
          prospects.map((p, i) => (
            <InterestedCard
              key={p.id}
              prospect={serializeProspect(p)}
              defaultOpen={i === 0 && p.introStatus === "NEW"}
            />
          ))
        )}
      </div>
    </div>
  );
}
