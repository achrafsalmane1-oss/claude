import Link from "next/link";
import { getCurrentUser } from "@/lib/session";
import { db } from "@/lib/db";
import { outreach } from "@/services";
import StatCard from "@/components/dashboard/StatCard";
import GrowthChart from "@/components/dashboard/GrowthChart";
import InterestedCard from "@/components/dashboard/InterestedCard";
import { serializeProspect } from "./serialize";
import { warmupDay, formatNumber } from "@/lib/format";
import { IconSpark } from "@/components/icons";

export default async function DashboardPage() {
  const user = (await getCurrentUser())!;

  const [funnel, snapshots, recentInterested] = await Promise.all([
    outreach.getFunnelCounts(user.id),
    db.funnelSnapshot.findMany({
      where: { userId: user.id },
      orderBy: { date: "asc" },
    }),
    db.prospect.findMany({
      where: { userId: user.id, replyDisposition: "INTERESTED" },
      orderBy: [{ introStatus: "asc" }, { repliedAt: "desc" }],
      take: 3,
    }),
  ]);

  const sub = user.subscription!;
  const inWarmup = new Date() < sub.outreachStartsAt;
  const day = warmupDay(sub.startedAt);

  // Week-over-week deltas from snapshots
  const latest = snapshots.at(-1);
  const weekAgo = snapshots.at(-8) ?? snapshots.at(0);
  const delta = (now?: number, before?: number) =>
    before && now !== undefined && before > 0
      ? ((now - before) / before) * 100
      : undefined;

  return (
    <div className="space-y-4">
      {inWarmup && (
        <div className="flex items-center gap-4 rounded-2xl border border-green/30 bg-green-mist px-5 py-4">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-green text-white">
            <IconSpark className="h-5 w-5" />
          </span>
          <div>
            <div className="text-[14.5px] font-semibold text-ink">
              Infrastructure warming — Day {day} of 10. Outreach begins Day 11.
            </div>
            <p className="text-[13px] text-ink-soft">
              We&apos;ve already sourced{" "}
              <span className="font-semibold text-green-dark">
                {formatNumber(funnel.sourced)} owners
              </span>{" "}
              in your buy-box while your outreach identity warms up.
            </p>
          </div>
        </div>
      )}

      {/* Heading */}
      <div className="flex items-end justify-between rounded-3xl border border-line bg-panel px-6 pb-5 pt-6">
        <div>
          <h1 className="display text-[38px] leading-none text-ink">
            Dashboard
          </h1>
          <p className="mt-2 text-[14px] text-ink-soft">
            <span className="font-semibold text-ink">Welcome,</span> track
            sourcing, outreach, and interested owners in one place.
          </p>
        </div>
        <Link
          href="/dashboard/interested"
          className="rounded-xl bg-ink px-4.5 py-2.5 text-[13.5px] font-medium text-white transition hover:bg-black"
        >
          View interested
        </Link>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 gap-4 xl:grid-cols-4">
        <StatCard
          label="Owners Sourced"
          value={funnel.sourced}
          delta={delta(latest?.sourced, weekAgo?.sourced)}
          hint="matching your buy-box"
        />
        <StatCard
          label="Contacts Verified"
          value={funnel.enriched}
          delta={delta(latest?.enriched, weekAgo?.enriched)}
          hint="verified owner contact found"
        />
        <StatCard
          label="Owners Contacted"
          value={funnel.contacted}
          delta={delta(latest?.contacted, weekAgo?.contacted)}
          hint="outreach sent in your name"
        />
        <StatCard
          label="Interested Owners"
          value={funnel.interested}
          delta={delta(latest?.interested, weekAgo?.interested)}
          hint="open to a conversation"
        />
      </div>

      {/* Chart + replies breakdown */}
      <div className="grid gap-4 xl:grid-cols-5">
        <div className="rounded-3xl border border-line bg-white p-6 xl:col-span-3">
          <div className="text-[13.5px] font-semibold text-ink">
            Pipeline Growth
          </div>
          <div className="display mt-1 text-[30px] leading-tight text-ink">
            {formatNumber(funnel.sourced)} Owners Sourced
          </div>
          <p className="mb-2 mt-0.5 text-[12.5px] text-ink-faint">
            cumulative, since your mandate went live
          </p>
          <GrowthChart
            points={snapshots.map((s) => ({
              date: s.date.toISOString(),
              value: s.sourced,
            }))}
          />
        </div>

        <div className="rounded-3xl border border-line bg-white p-6 xl:col-span-2">
          <div className="text-[13.5px] font-semibold text-ink">Replies</div>
          <div className="display mt-1 text-[30px] leading-tight text-ink">
            {formatNumber(funnel.replied)} Owners Replied
          </div>
          <p className="mt-0.5 text-[12.5px] text-ink-faint">
            every reply read &amp; classified
          </p>
          <div className="mt-5 space-y-4">
            {[
              {
                label: "Interested",
                n: funnel.interested,
                cls: "bg-green",
                text: "text-green-dark",
              },
              {
                label: "Not now",
                n: funnel.notNow,
                cls: "bg-amber",
                text: "text-amber",
              },
              {
                label: "Not interested",
                n: funnel.notInterested,
                cls: "bg-line",
                text: "text-ink-soft",
              },
            ].map((row) => (
              <div key={row.label}>
                <div className="mb-1.5 flex items-baseline justify-between text-[13px]">
                  <span className="font-medium text-ink">{row.label}</span>
                  <span className={`display text-[18px] ${row.text}`}>
                    {row.n}
                  </span>
                </div>
                <div className="h-2 overflow-hidden rounded-full bg-cream">
                  <div
                    className={`h-full rounded-full ${row.cls}`}
                    style={{
                      width: `${funnel.replied ? Math.max(3, (row.n / funnel.replied) * 100) : 0}%`,
                    }}
                  />
                </div>
              </div>
            ))}
          </div>
          <Link
            href="/dashboard/pipeline"
            className="mt-6 block rounded-xl border border-line px-4 py-2.5 text-center text-[13.5px] font-medium text-ink transition hover:bg-cream"
          >
            View full pipeline
          </Link>
        </div>
      </div>

      {/* Recent interested */}
      <div className="rounded-3xl border border-line bg-panel p-6">
        <div className="mb-4 flex items-end justify-between">
          <div>
            <h2 className="display text-[26px] leading-none text-ink">
              Latest interested owners
            </h2>
            <p className="mt-1.5 text-[13px] text-ink-soft">
              Owners open to a conversation, delivered as introductions.
            </p>
          </div>
          <Link
            href="/dashboard/interested"
            className="text-[13.5px] font-medium text-green-dark hover:underline"
          >
            View all →
          </Link>
        </div>
        <div className="space-y-3">
          {recentInterested.length === 0 ? (
            <p className="rounded-2xl border border-dashed border-line bg-white px-5 py-8 text-center text-[14px] text-ink-faint">
              No interested replies yet — they&apos;ll appear here the moment an
              owner says yes.
            </p>
          ) : (
            recentInterested.map((p) => (
              <InterestedCard key={p.id} prospect={serializeProspect(p)} />
            ))
          )}
        </div>
      </div>
    </div>
  );
}
