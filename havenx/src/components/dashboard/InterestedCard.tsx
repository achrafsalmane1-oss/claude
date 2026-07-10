"use client";

import { useState, useTransition } from "react";
import {
  IconBuilding,
  IconCalendar,
  IconUsers,
  IconChart,
  IconMap,
  IconLink,
  IconCheck,
  IconHandshake,
} from "@/components/icons";
import { claimProspect, toggleBookingLink } from "@/app/dashboard/actions";
import { formatMoney, formatRelative, formatDate } from "@/lib/format";

export type InterestedProspect = {
  id: string;
  ownerName: string;
  ownerTitle: string | null;
  linkedinUrl: string | null;
  companyName: string;
  domain: string;
  description: string | null;
  incorporatedOn: string | null;
  headcount: number | null;
  estRevenueUsd: number | null;
  location: string | null;
  replyText: string | null;
  repliedAt: string | null;
  introStatus: "NEW" | "CLAIMED";
  bookingLinkRequested: boolean;
  contactEmail: string | null;
  contactPhone: string | null;
};

function Fact({
  icon: Icon,
  label,
  value,
}: {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center gap-2.5 rounded-xl bg-cream px-3 py-2.5">
      <Icon className="h-4 w-4 shrink-0 text-green-dark" />
      <div className="min-w-0">
        <div className="text-[10.5px] uppercase tracking-wide text-ink-faint">
          {label}
        </div>
        <div className="truncate text-[13px] font-medium text-ink">{value}</div>
      </div>
    </div>
  );
}

export default function InterestedCard({
  prospect,
  defaultOpen = false,
}: {
  prospect: InterestedProspect;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  const [pending, startTransition] = useTransition();
  const [bookingPending, startBooking] = useTransition();
  const p = prospect;
  const claimed = p.introStatus === "CLAIMED";

  return (
    <div
      className={`overflow-hidden rounded-3xl border bg-white transition-shadow ${
        claimed ? "border-line" : "border-green/35 shadow-[0_16px_36px_-28px_rgba(30,127,60,0.55)]"
      }`}
    >
      {/* Header row (always visible) */}
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex w-full items-center gap-4 px-5 py-4 text-left"
      >
        <span className="display flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-green-soft text-[18px] italic text-green-dark">
          {p.ownerName
            .split(" ")
            .map((w) => w[0])
            .slice(0, 2)
            .join("")}
        </span>
        <span className="min-w-0 flex-1">
          <span className="flex items-center gap-2.5">
            <span className="truncate text-[16px] font-semibold text-ink">
              {p.ownerName}
            </span>
            {claimed ? (
              <span className="rounded-full bg-cream px-2.5 py-0.5 text-[11px] font-medium text-ink-soft">
                Claimed
              </span>
            ) : (
              <span className="rounded-full bg-green px-2.5 py-0.5 text-[11px] font-semibold text-white">
                New
              </span>
            )}
          </span>
          <span className="mt-0.5 block truncate text-[13.5px] text-ink-soft">
            {p.ownerTitle ? `${p.ownerTitle}, ` : ""}
            {p.companyName}
            {p.location ? ` — ${p.location}` : ""}
          </span>
        </span>
        <span className="hidden shrink-0 text-right sm:block">
          {p.estRevenueUsd && (
            <span className="display block text-[20px] leading-tight text-ink">
              {formatMoney(p.estRevenueUsd)}
            </span>
          )}
          <span className="text-[11.5px] text-ink-faint">
            replied {p.repliedAt ? formatRelative(p.repliedAt) : "recently"}
          </span>
        </span>
        <span
          className={`ml-1 text-ink-faint transition-transform ${open ? "rotate-180" : ""}`}
        >
          ▾
        </span>
      </button>

      {open && (
        <div className="border-t border-line-soft px-5 pb-5">
          {/* Reply */}
          <div className="mt-4 rounded-2xl bg-green-mist p-4">
            <div className="mb-1.5 flex items-center gap-2 text-[11.5px] font-medium uppercase tracking-wide text-green-dark">
              <IconHandshake className="h-3.5 w-3.5" />
              Owner&apos;s reply
            </div>
            <p className="display text-[17px] italic leading-relaxed text-ink">
              &ldquo;{p.replyText}&rdquo;
            </p>
          </div>

          {/* Company profile */}
          {p.description && (
            <p className="mt-4 text-[14px] leading-relaxed text-ink-soft">
              {p.description}
            </p>
          )}
          <div className="mt-4 grid grid-cols-2 gap-2 lg:grid-cols-4">
            <Fact icon={IconBuilding} label="Company" value={p.companyName} />
            {p.incorporatedOn && (
              <Fact
                icon={IconCalendar}
                label="Incorporated"
                value={formatDate(p.incorporatedOn)}
              />
            )}
            {p.headcount !== null && (
              <Fact
                icon={IconUsers}
                label="Headcount"
                value={`~${p.headcount} employees`}
              />
            )}
            {p.estRevenueUsd !== null && (
              <Fact
                icon={IconChart}
                label="Est. revenue"
                value={`${formatMoney(p.estRevenueUsd)} / yr`}
              />
            )}
            {p.location && (
              <Fact icon={IconMap} label="Location" value={p.location} />
            )}
            <Fact icon={IconLink} label="Domain" value={p.domain} />
          </div>

          {/* Links + contact */}
          <div className="mt-4 flex flex-wrap items-center gap-3 text-[13.5px]">
            {p.linkedinUrl && (
              <a
                href={p.linkedinUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="font-medium text-green-dark underline-offset-2 hover:underline"
              >
                LinkedIn profile ↗
              </a>
            )}
            <a
              href={`https://${p.domain}`}
              target="_blank"
              rel="noopener noreferrer"
              className="font-medium text-green-dark underline-offset-2 hover:underline"
            >
              {p.domain} ↗
            </a>
          </div>

          {claimed && (
            <div className="mt-4 rounded-2xl border border-line bg-panel p-4">
              <div className="text-[11.5px] font-medium uppercase tracking-wide text-ink-faint">
                Contact details — the conversation is yours from here
              </div>
              <div className="mt-2 flex flex-wrap gap-x-8 gap-y-1.5 text-[14.5px] text-ink">
                {p.contactEmail && (
                  <span>
                    <span className="text-ink-faint">Email </span>
                    <a
                      href={`mailto:${p.contactEmail}`}
                      className="font-medium text-green-dark"
                    >
                      {p.contactEmail}
                    </a>
                  </span>
                )}
                {p.contactPhone && (
                  <span>
                    <span className="text-ink-faint">Phone </span>
                    <span className="font-medium">{p.contactPhone}</span>
                  </span>
                )}
              </div>
            </div>
          )}

          {/* Actions */}
          <div className="mt-5 flex flex-wrap items-center justify-between gap-4 border-t border-line-soft pt-4">
            <label className="flex cursor-pointer items-center gap-2.5 text-[13.5px] text-ink-soft">
              <button
                type="button"
                role="switch"
                aria-checked={p.bookingLinkRequested}
                disabled={bookingPending}
                onClick={() =>
                  startBooking(() =>
                    toggleBookingLink(p.id, !p.bookingLinkRequested)
                  )
                }
                className={`relative h-6 w-11 rounded-full transition ${
                  p.bookingLinkRequested ? "bg-green" : "bg-line"
                }`}
              >
                <span
                  className={`absolute top-0.5 h-5 w-5 rounded-full bg-white shadow transition-all ${
                    p.bookingLinkRequested ? "left-[22px]" : "left-0.5"
                  }`}
                />
              </button>
              Send a booking link on my behalf
            </label>

            {claimed ? (
              <span className="flex items-center gap-2 text-[13.5px] font-medium text-green-dark">
                <IconCheck className="h-4 w-4" />
                In your hands
              </span>
            ) : (
              <button
                type="button"
                disabled={pending}
                onClick={() => startTransition(() => claimProspect(p.id))}
                className="rounded-2xl bg-green px-5 py-2.5 text-[14.5px] font-semibold text-white transition hover:bg-green-deep disabled:opacity-50"
              >
                {pending ? "Claiming…" : "Take it from here"}
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
