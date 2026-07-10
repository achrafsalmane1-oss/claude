import Link from "next/link";
import { getCurrentUser } from "@/lib/session";
import { formatMoney } from "@/lib/format";

function Chips({ items }: { items: string[] }) {
  if (!items.length) return <span className="text-ink-faint">Any</span>;
  return (
    <div className="flex flex-wrap gap-2">
      {items.map((t) => (
        <span
          key={t}
          className="rounded-lg bg-green-soft px-2.5 py-1 text-[13px] font-medium text-green-dark"
        >
          {t}
        </span>
      ))}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5 border-b border-line-soft py-4 last:border-0 sm:grid-cols-[200px_1fr] sm:gap-6">
      <div className="text-[13px] font-medium uppercase tracking-wide text-ink-faint">
        {label}
      </div>
      <div className="text-[14.5px] leading-relaxed text-ink">{children}</div>
    </div>
  );
}

function range(
  min: number | null,
  max: number | null,
  fmt: (n: number) => string = (n) => n.toLocaleString()
) {
  if (min === null && max === null) return "Any";
  if (min !== null && max !== null) return `${fmt(min)} – ${fmt(max)}`;
  if (min !== null) return `${fmt(min)}+`;
  return `Up to ${fmt(max!)}`;
}

export default async function BuyBoxPage() {
  const user = (await getCurrentUser())!;
  const m = user.mandate!;

  return (
    <div className="space-y-4">
      <div className="flex items-end justify-between rounded-3xl border border-line bg-panel px-6 pb-5 pt-6">
        <div>
          <h1 className="display text-[38px] leading-none text-ink">Buy-box</h1>
          <p className="mt-2 text-[14px] text-ink-soft">
            Your standing acquisition mandate. Everything we source matches
            this.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <span className="flex items-center gap-2 rounded-full border border-green/30 bg-green-mist px-3.5 py-1.5 text-[13px] font-medium text-green-dark">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-green" />
            {m.active ? "Active — sourcing live" : "Paused"}
          </span>
          <Link
            href="/onboarding/buybox"
            className="rounded-xl border border-line bg-white px-4 py-2 text-[13.5px] font-medium text-ink transition hover:bg-cream"
          >
            Edit
          </Link>
        </div>
      </div>

      <div className="rounded-3xl border border-line bg-white px-6 py-2">
        <Row label="Industries">
          <Chips items={m.industries} />
        </Row>
        <Row label="Geography">
          <Chips items={m.geographies} />
        </Row>
        <Row label="Annual revenue">
          {range(m.revenueMinUsd, m.revenueMaxUsd, formatMoney)}
        </Row>
        <Row label="EBITDA">
          {range(m.ebitdaMinUsd, m.ebitdaMaxUsd, formatMoney)}
        </Row>
        <Row label="Employees">{range(m.employeesMin, m.employeesMax)}</Row>
        <Row label="Business model">
          <Chips items={m.businessModelKeywords} />
        </Row>
        <Row label="Owner situation">
          <Chips items={m.ownerSituations} />
        </Row>
        <Row label="Must-haves">
          {m.mustHaves || <span className="text-ink-faint">None specified</span>}
        </Row>
        <Row label="Hard exclusions">
          {m.hardExclusions || (
            <span className="text-ink-faint">None specified</span>
          )}
        </Row>
        {m.thesis && (
          <Row label="Thesis">
            <span className="display text-[17px] italic leading-relaxed">
              &ldquo;{m.thesis}&rdquo;
            </span>
          </Row>
        )}
      </div>

      <div className="rounded-3xl border border-line bg-white px-6 py-2">
        <Row label="Outreach identity">
          <div className="font-medium">{m.senderName}</div>
          <div className="text-ink-soft">{m.senderCompany}</div>
          {m.senderReplyToName && (
            <div className="mt-1 text-[13px] text-ink-faint">
              Replies display as “{m.senderReplyToName}”
            </div>
          )}
        </Row>
        {m.senderSignature && (
          <Row label="Signature">
            <pre className="whitespace-pre-wrap font-sans text-[14px] text-ink-soft">
              {m.senderSignature}
            </pre>
          </Row>
        )}
      </div>
    </div>
  );
}
