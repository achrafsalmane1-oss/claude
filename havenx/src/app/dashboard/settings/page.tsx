import { getCurrentUser } from "@/lib/session";
import { formatDate } from "@/lib/format";

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5 border-b border-line-soft py-4 last:border-0 sm:grid-cols-[200px_1fr] sm:gap-6">
      <div className="text-[13px] font-medium uppercase tracking-wide text-ink-faint">
        {label}
      </div>
      <div className="text-[14.5px] text-ink">{children}</div>
    </div>
  );
}

export default async function SettingsPage() {
  const user = (await getCurrentUser())!;
  const sub = user.subscription!;
  const inFirstCycle = new Date() < sub.firstCycleEndsAt;

  return (
    <div className="space-y-4">
      <div className="rounded-3xl border border-line bg-panel px-6 pb-5 pt-6">
        <h1 className="display text-[38px] leading-none text-ink">Settings</h1>
        <p className="mt-2 text-[14px] text-ink-soft">
          Account and subscription.
        </p>
      </div>

      <div className="rounded-3xl border border-line bg-white px-6 py-2">
        <Row label="Signed in as">{user.email}</Row>
        <Row label="Plan">
          <span className="font-medium">HavenX Core</span> —{" "}
          <span className="display text-[16px]">${sub.priceUsd}</span>/month,
          everything included
        </Row>
        <Row label="Status">
          <span className="rounded-full bg-green-soft px-2.5 py-1 text-[12.5px] font-medium text-green-dark">
            {sub.status === "ACTIVE" ? "Active" : sub.status}
          </span>
        </Row>
        <Row label="Member since">{formatDate(sub.startedAt)}</Row>
        <Row label="Outreach began">
          {new Date() < sub.outreachStartsAt
            ? `Begins ${formatDate(sub.outreachStartsAt)} (after day-10 warmup)`
            : formatDate(sub.outreachStartsAt)}
        </Row>
        <Row label={inFirstCycle ? "First cycle ends" : "Renews"}>
          {formatDate(inFirstCycle ? sub.firstCycleEndsAt : sub.currentPeriodEnd)}
          {inFirstCycle && (
            <span className="ml-2 text-[13px] text-ink-faint">
              first cycle runs 40 days, then monthly
            </span>
          )}
        </Row>
      </div>

      <div className="flex items-center justify-between rounded-3xl border border-line bg-white px-6 py-5">
        <div>
          <div className="text-[14.5px] font-medium text-ink">Sign out</div>
          <p className="text-[13px] text-ink-faint">
            You can sign back in anytime with a magic link.
          </p>
        </div>
        <a
          href="/api/auth/logout"
          className="rounded-xl border border-line px-4 py-2 text-[13.5px] font-medium text-ink transition hover:bg-cream"
        >
          Sign out
        </a>
      </div>
    </div>
  );
}
