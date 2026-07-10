// Static, styled-to-match preview of the product dashboard, embedded in the
// hero the way the reference design embeds its app. Purely visual.

import {
  LogoMark,
  IconGrid,
  IconFunnel,
  IconHandshake,
  IconTarget,
  IconSettings,
  IconSearch,
  IconBell,
  IconClock,
  IconTrendUp,
  IconTrendDown,
} from "@/components/icons";

const nav = [
  { icon: IconGrid, label: "Dashboard", active: true },
  { icon: IconFunnel, label: "Pipeline" },
  { icon: IconHandshake, label: "Interested" },
  { icon: IconTarget, label: "Buy-box" },
  { icon: IconSettings, label: "Settings" },
];

const stats = [
  { label: "Owners Sourced", value: "2,642", delta: "+11.01%", up: true },
  { label: "Contacts Verified", value: "1,987", delta: "+6.4%", up: true },
  { label: "Owners Contacted", value: "1,412", delta: "-0.03%", up: false },
  { label: "Interested Owners", value: "18", delta: "+4.05%", up: true },
];

export default function HeroPreview() {
  return (
    <div className="mx-auto w-full max-w-5xl rounded-t-3xl border border-b-0 border-black/10 bg-panel p-3 shadow-[0_-20px_60px_-30px_rgba(20,50,30,0.45)]">
      <div className="flex gap-3">
        {/* Sidebar */}
        <aside className="hidden w-52 shrink-0 rounded-2xl border border-line bg-white p-3 sm:block">
          <div className="mb-4 flex items-center gap-2 px-1.5 pt-1">
            <LogoMark className="h-5 w-5" />
            <span className="text-[15px] font-semibold text-ink">HavenX</span>
          </div>
          <nav className="space-y-1">
            {nav.map((item) => (
              <div
                key={item.label}
                className={`flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-[13.5px] ${
                  item.active
                    ? "bg-green-soft font-medium text-green-dark"
                    : "text-ink-soft"
                }`}
              >
                <item.icon className="h-4 w-4" />
                {item.label}
              </div>
            ))}
          </nav>
        </aside>

        {/* Main */}
        <div className="min-w-0 flex-1">
          {/* Top bar */}
          <div className="flex items-center justify-between px-2 py-2.5">
            <div className="flex items-center gap-2 text-[13px] text-ink-faint">
              <span>Dashboards</span>
              <span>/</span>
              <span className="text-ink">Default</span>
            </div>
            <div className="flex items-center gap-3">
              <div className="hidden items-center gap-2 rounded-lg bg-cream px-3 py-1.5 text-[12.5px] text-ink-faint md:flex">
                <IconSearch className="h-3.5 w-3.5" />
                Search
              </div>
              <IconClock className="h-4 w-4 text-ink-soft" />
              <IconBell className="h-4 w-4 text-ink-soft" />
            </div>
          </div>

          {/* Heading */}
          <div className="flex items-end justify-between px-2 pb-4 pt-1">
            <div>
              <h3 className="display text-[28px] leading-none text-ink">
                Dashboard
              </h3>
              <p className="mt-1.5 text-[12.5px] text-ink-soft">
                <span className="font-semibold text-ink">Welcome,</span> track
                sourcing, outreach, and interested owners in one place.
              </p>
            </div>
            <div className="rounded-lg bg-ink px-3.5 py-2 text-[12.5px] font-medium text-white">
              View interested
            </div>
          </div>

          {/* Stat cards */}
          <div className="grid grid-cols-2 gap-2.5 px-2 lg:grid-cols-4">
            {stats.map((s) => (
              <div
                key={s.label}
                className="rounded-2xl border border-line bg-white p-3.5"
              >
                <div className="text-[11.5px] text-ink-soft">{s.label}</div>
                <div className="mt-1.5 flex items-end justify-between gap-1">
                  <span className="display text-[26px] leading-none text-ink">
                    {s.value}
                  </span>
                  <span
                    className={`flex items-center gap-1 text-[11px] font-medium ${
                      s.up ? "text-rise" : "text-fall"
                    }`}
                  >
                    {s.delta}
                    {s.up ? (
                      <IconTrendUp className="h-3 w-3" />
                    ) : (
                      <IconTrendDown className="h-3 w-3" />
                    )}
                  </span>
                </div>
              </div>
            ))}
          </div>

          {/* Lower panels, cropped by the hero edge */}
          <div className="mt-2.5 grid grid-cols-1 gap-2.5 px-2 lg:grid-cols-5">
            <div className="rounded-t-2xl border border-b-0 border-line bg-white p-4 lg:col-span-3">
              <div className="text-[12px] font-semibold text-ink">
                Pipeline Growth
              </div>
              <div className="display mt-1 text-[24px] leading-none text-ink">
                2,642 Owners Sourced
              </div>
              <div className="mt-1 text-[11px] text-ink-faint">
                20 May, 2026{" "}
                <span className="font-medium text-rise">+12%</span> vs last
                month
              </div>
              <svg viewBox="0 0 400 70" className="mt-3 w-full" aria-hidden>
                <path
                  d="M0 60 C 40 55 70 40 110 42 C 150 44 180 28 220 30 C 260 32 300 16 340 14 C 365 13 385 10 400 8 L 400 70 L 0 70 Z"
                  fill="#2FB44F"
                  opacity="0.12"
                />
                <path
                  d="M0 60 C 40 55 70 40 110 42 C 150 44 180 28 220 30 C 260 32 300 16 340 14 C 365 13 385 10 400 8"
                  fill="none"
                  stroke="#1E7F3C"
                  strokeWidth="2"
                />
              </svg>
            </div>
            <div className="rounded-t-2xl border border-b-0 border-line bg-white p-4 lg:col-span-2">
              <div className="text-[12px] font-semibold text-ink">
                New This Week
              </div>
              <div className="display mt-1 text-[24px] leading-none text-ink">
                3 Interested Owners
              </div>
              <div className="mt-3 space-y-2">
                {[
                  ["Meridian Fabrication Co.", "Owner replied 2h ago"],
                  ["Cascade Dental Partners", "Owner replied 9h ago"],
                ].map(([name, meta]) => (
                  <div
                    key={name}
                    className="rounded-xl border border-line bg-panel px-3 py-2"
                  >
                    <div className="text-[12px] font-medium text-ink">
                      {name}
                    </div>
                    <div className="text-[10.5px] text-ink-faint">{meta}</div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
