import Link from "next/link";
import { getCurrentUser } from "@/lib/session";
import { db } from "@/lib/db";
import { outreach } from "@/services";
import { formatNumber, formatRelative, formatMoney } from "@/lib/format";

const STAGE_LABELS: Record<string, string> = {
  SOURCED: "Sourced",
  ENRICHED: "Enriched",
  CONTACTED: "Contacted",
  REPLIED: "Replied",
};

const DISPOSITION_BADGE: Record<string, { label: string; cls: string }> = {
  INTERESTED: { label: "Interested", cls: "bg-green-soft text-green-dark" },
  NOT_NOW: { label: "Not now", cls: "bg-amber-soft text-amber" },
  NOT_INTERESTED: { label: "Not interested", cls: "bg-cream text-ink-soft" },
};

export default async function PipelinePage() {
  const user = (await getCurrentUser())!;
  const [funnel, recent] = await Promise.all([
    outreach.getFunnelCounts(user.id),
    db.prospect.findMany({
      where: { userId: user.id },
      orderBy: [{ repliedAt: { sort: "desc", nulls: "last" } }, { sourcedAt: "desc" }],
      take: 30,
    }),
  ]);

  const stages = [
    {
      label: "Sourced",
      n: funnel.sourced,
      hint: "owners matching your buy-box",
    },
    {
      label: "Enriched",
      n: funnel.enriched,
      hint: "verified contact found",
    },
    {
      label: "Contacted",
      n: funnel.contacted,
      hint: "outreach sent in your name",
    },
    {
      label: "Replied",
      n: funnel.replied,
      hint: `${funnel.interested} interested · ${funnel.notNow} not now · ${funnel.notInterested} not interested`,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="rounded-3xl border border-line bg-panel px-6 pb-5 pt-6">
        <h1 className="display text-[38px] leading-none text-ink">Pipeline</h1>
        <p className="mt-2 text-[14px] text-ink-soft">
          Your funnel runs 24/7 — from sourcing to interested introductions.
        </p>
      </div>

      {/* Funnel */}
      <div className="grid gap-3 md:grid-cols-4">
        {stages.map((s, i) => {
          const prev = i === 0 ? null : stages[i - 1].n;
          const conv = prev ? Math.round((s.n / prev) * 100) : null;
          return (
            <div key={s.label} className="relative rounded-3xl border border-line bg-white p-5">
              <div className="flex items-center justify-between">
                <span className="text-[13px] font-medium text-ink-soft">
                  {s.label}
                </span>
                {conv !== null && (
                  <span className="rounded-full bg-cream px-2 py-0.5 text-[11px] font-medium text-ink-faint">
                    {conv}% of prior
                  </span>
                )}
              </div>
              <div className="display mt-2 text-[36px] leading-none text-ink">
                {formatNumber(s.n)}
              </div>
              <div className="mt-2 text-[11.5px] leading-relaxed text-ink-faint">
                {s.hint}
              </div>
              <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-cream">
                <div
                  className="h-full rounded-full bg-green"
                  style={{
                    width: `${funnel.sourced ? Math.max(2, (s.n / funnel.sourced) * 100) : 0}%`,
                  }}
                />
              </div>
            </div>
          );
        })}
      </div>

      {/* Recent activity table */}
      <div className="overflow-hidden rounded-3xl border border-line bg-white">
        <div className="flex items-center justify-between border-b border-line-soft px-6 py-4">
          <h2 className="text-[15px] font-semibold text-ink">
            Recent activity
          </h2>
          <Link
            href="/dashboard/interested"
            className="text-[13px] font-medium text-green-dark hover:underline"
          >
            Interested only →
          </Link>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-[13.5px]">
            <thead>
              <tr className="border-b border-line-soft text-[11.5px] uppercase tracking-wide text-ink-faint">
                <th className="px-6 py-3 font-medium">Company</th>
                <th className="px-4 py-3 font-medium">Owner</th>
                <th className="px-4 py-3 font-medium">Est. revenue</th>
                <th className="px-4 py-3 font-medium">Stage</th>
                <th className="px-4 py-3 font-medium">Outcome</th>
                <th className="px-6 py-3 text-right font-medium">Updated</th>
              </tr>
            </thead>
            <tbody>
              {recent.map((p) => (
                <tr
                  key={p.id}
                  className="border-b border-line-soft last:border-0 hover:bg-panel"
                >
                  <td className="px-6 py-3.5">
                    <div className="font-medium text-ink">{p.companyName}</div>
                    <div className="text-[12px] text-ink-faint">
                      {p.location ?? p.domain}
                    </div>
                  </td>
                  <td className="px-4 py-3.5 text-ink-soft">{p.ownerName}</td>
                  <td className="display px-4 py-3.5 text-[15px] text-ink">
                    {p.estRevenueUsd ? formatMoney(p.estRevenueUsd) : "—"}
                  </td>
                  <td className="px-4 py-3.5">
                    <span className="rounded-full bg-cream px-2.5 py-1 text-[12px] font-medium text-ink-soft">
                      {STAGE_LABELS[p.stage]}
                    </span>
                  </td>
                  <td className="px-4 py-3.5">
                    {p.replyDisposition ? (
                      <span
                        className={`rounded-full px-2.5 py-1 text-[12px] font-medium ${DISPOSITION_BADGE[p.replyDisposition].cls}`}
                      >
                        {DISPOSITION_BADGE[p.replyDisposition].label}
                      </span>
                    ) : (
                      <span className="text-ink-faint">—</span>
                    )}
                  </td>
                  <td className="px-6 py-3.5 text-right text-[12.5px] text-ink-faint">
                    {formatRelative(p.repliedAt ?? p.contactedAt ?? p.enrichedAt ?? p.sourcedAt)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
