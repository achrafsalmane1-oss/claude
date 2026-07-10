import Link from "next/link";
import Nav from "@/components/marketing/Nav";
import Meadow from "@/components/marketing/Meadow";
import HeroPreview from "@/components/marketing/HeroPreview";
import {
  Logo,
  IconTarget,
  IconSpark,
  IconHandshake,
  IconDoc,
  IconTrendUp,
  IconArrowUpRight,
  IconCheck,
  IconPhone,
  IconSearch,
  IconUsers,
  IconChart,
  IconShield,
  IconLightning,
  IconBell,
} from "@/components/icons";

export default function Home() {
  return (
    <main className="bg-cream">
      <Nav />
      <Hero />
      <HowItWorks />
      <WhoItsFor />
      <WhatsIncluded />
      <Pricing />
      <Footer />
    </main>
  );
}

function Hero() {
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-sky-deep via-[#b7dbf3] to-sky-pale">
      <div className="dot-grid absolute inset-0" aria-hidden />
      <Meadow className="absolute inset-x-0 bottom-0 h-[46%] w-full" />

      <div className="relative mx-auto max-w-5xl px-4 pt-40 text-center sm:pt-48">
        <h1 className="mx-auto max-w-4xl text-[44px] font-light leading-[1.14] tracking-tight text-[#3d4654] sm:text-[64px] md:text-[76px]">
          Turn your{" "}
          <span className="inline-flex translate-y-1 items-center gap-3 rounded-2xl bg-violet-soft/90 px-4 py-0.5 align-middle sm:translate-y-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-violet text-white sm:h-11 sm:w-11 sm:rounded-xl">
              <IconTarget className="h-5 w-5 sm:h-6 sm:w-6" />
            </span>
            <span className="display italic text-violet">Buy-box</span>
          </span>{" "}
          into
          <br />
          endless{" "}
          <span className="inline-flex translate-y-1 items-center gap-3 rounded-2xl bg-amber-soft/95 px-4 py-0.5 align-middle sm:translate-y-2">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-amber text-white sm:h-11 sm:w-11 sm:rounded-xl">
              <IconTrendUp className="h-5 w-5 sm:h-6 sm:w-6" />
            </span>
            <span className="display italic text-amber">Deal flow</span>
          </span>
        </h1>

        <p className="mx-auto mt-8 max-w-xl text-lg leading-relaxed text-[#4c5563] sm:text-[21px]">
          HavenX finds off-market companies in your buy-box and delivers owners
          who are open to a conversation — under your brand, on autopilot.
        </p>

        <div className="mt-9 flex items-center justify-center gap-4">
          <Link
            href="/checkout"
            className="inline-flex items-center gap-2 rounded-2xl bg-green px-7 py-4 text-[17px] font-semibold text-white shadow-[0_14px_30px_-10px_rgba(30,127,60,0.55)] transition hover:bg-green-deep"
          >
            Start now
            <IconArrowUpRight className="h-5 w-5" />
          </Link>
          {process.env.DEMO_MODE === "true" && (
            <Link
              href="/api/demo"
              className="inline-flex items-center gap-2 rounded-2xl bg-white/80 px-6 py-4 text-[16px] font-medium text-ink backdrop-blur transition hover:bg-white"
            >
              View live demo
            </Link>
          )}
        </div>
      </div>

      <div className="relative mt-16 px-4 sm:mt-20">
        <HeroPreview />
      </div>
    </section>
  );
}

function SectionHeading({
  kicker,
  title,
  sub,
}: {
  kicker: string;
  title: React.ReactNode;
  sub?: string;
}) {
  return (
    <div className="mx-auto max-w-2xl text-center">
      <div className="mb-4 inline-flex items-center gap-2 rounded-full border border-line bg-white px-3.5 py-1.5 text-[13px] font-medium text-green-dark">
        <span className="h-1.5 w-1.5 rounded-full bg-green" />
        {kicker}
      </div>
      <h2 className="display text-[38px] leading-[1.08] text-ink sm:text-[52px]">
        {title}
      </h2>
      {sub && (
        <p className="mx-auto mt-4 max-w-xl text-[17px] leading-relaxed text-ink-soft">
          {sub}
        </p>
      )}
    </div>
  );
}

function HowItWorks() {
  const steps = [
    {
      n: "01",
      icon: IconTarget,
      title: "Define your buy-box",
      body: "Industries, geography, revenue and EBITDA range, owner situation, hard exclusions — a 5-minute intake that becomes your standing acquisition mandate.",
    },
    {
      n: "02",
      icon: IconSpark,
      title: "Our AI agents run outreach in your name",
      body: "HavenX sources matching companies, verifies the owner, and runs personalized multi-channel outreach — email, calls, LinkedIn — as one blended service, under your brand.",
    },
    {
      n: "03",
      icon: IconHandshake,
      title: "Interested owners land in your dashboard",
      body: "Every reply is read and classified. Owners open to a conversation appear as introductions with the full company picture, ready for you to take from there.",
    },
  ];
  return (
    <section id="how-it-works" className="dot-grid-dark px-4 py-24 sm:py-32">
      <SectionHeading
        kicker="How it works"
        title={
          <>
            Three steps to{" "}
            <span className="italic text-green-deep">off-market</span> flow
          </>
        }
        sub="You set the mandate once. HavenX runs sourcing, verification, and outreach around the clock."
      />
      <div className="mx-auto mt-14 grid max-w-5xl gap-5 md:grid-cols-3">
        {steps.map((s) => (
          <div
            key={s.n}
            className="rounded-3xl border border-line bg-white p-7 shadow-[0_12px_30px_-24px_rgba(30,60,40,0.4)]"
          >
            <div className="flex items-center justify-between">
              <span className="flex h-11 w-11 items-center justify-center rounded-2xl bg-green-soft text-green-dark">
                <s.icon className="h-5 w-5" />
              </span>
              <span className="display text-[28px] italic text-line">
                {s.n}
              </span>
            </div>
            <h3 className="mt-5 text-[19px] font-semibold tracking-tight text-ink">
              {s.title}
            </h3>
            <p className="mt-2.5 text-[15px] leading-relaxed text-ink-soft">
              {s.body}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}

function WhoItsFor() {
  const buyers = [
    {
      icon: IconSearch,
      title: "Search funds",
      body: "Full top-of-funnel while you focus on diligence and the handful of owners who matter.",
    },
    {
      icon: IconUsers,
      title: "Independent sponsors",
      body: "A steady stream of proprietary conversations to bring to your capital partners.",
    },
    {
      icon: IconChart,
      title: "Micro-PE firms",
      body: "Scale origination across multiple theses without scaling an analyst team.",
    },
    {
      icon: IconHandshake,
      title: "Buy-side M&A boutiques",
      body: "Run origination for every client mandate under their brand, from one dashboard.",
    },
  ];
  return (
    <section id="who-its-for" className="bg-panel px-4 py-24 sm:py-32">
      <SectionHeading
        kicker="Who it's for"
        title={
          <>
            Built for <span className="italic text-green-deep">buyers</span>,
            not marketers
          </>
        }
        sub="If your job is acquiring companies, HavenX replaces the analyst, the tooling stack, and the outbound grind."
      />
      <div className="mx-auto mt-14 grid max-w-5xl gap-5 sm:grid-cols-2">
        {buyers.map((b) => (
          <div
            key={b.title}
            className="flex gap-5 rounded-3xl border border-line bg-white p-7"
          >
            <span className="flex h-12 w-12 shrink-0 items-center justify-center rounded-2xl bg-cream text-green-dark">
              <b.icon className="h-6 w-6" />
            </span>
            <div>
              <h3 className="text-[18px] font-semibold tracking-tight text-ink">
                {b.title}
              </h3>
              <p className="mt-1.5 text-[15px] leading-relaxed text-ink-soft">
                {b.body}
              </p>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function WhatsIncluded() {
  const items = [
    {
      icon: IconTarget,
      title: "Buy-box sourcing",
      body: "Continuous sourcing of off-market companies matching your mandate.",
    },
    {
      icon: IconShield,
      title: "Owner verification",
      body: "Every introduction is a verified owner or decision-maker, with contact details.",
    },
    {
      icon: IconLightning,
      title: "Multi-channel outreach, in your name",
      body: "Email, calls, and LinkedIn blended into one service, sent under your brand.",
    },
    {
      icon: IconDoc,
      title: "Company enrichment",
      body: "Incorporation date, headcount, estimated revenue, and location on every card.",
    },
    {
      icon: IconBell,
      title: "Instant interested alerts",
      body: "In-app and email notification the moment an owner replies with interest.",
    },
    {
      icon: IconHandshake,
      title: "Clean handoff",
      body: "One click reveals full contact details. The conversation is yours from there.",
    },
  ];
  return (
    <section id="whats-included" className="px-4 py-24 sm:py-32">
      <SectionHeading
        kicker="What's included"
        title={
          <>
            Everything, in <span className="italic text-green-deep">one</span>{" "}
            subscription
          </>
        }
      />
      <div className="mx-auto mt-14 grid max-w-5xl gap-5 sm:grid-cols-2 lg:grid-cols-3">
        {items.map((f) => (
          <div
            key={f.title}
            className="rounded-3xl border border-line bg-white p-6"
          >
            <span className="flex h-10 w-10 items-center justify-center rounded-xl bg-green-soft text-green-dark">
              <f.icon className="h-5 w-5" />
            </span>
            <h3 className="mt-4 text-[16.5px] font-semibold tracking-tight text-ink">
              {f.title}
            </h3>
            <p className="mt-1.5 text-[14.5px] leading-relaxed text-ink-soft">
              {f.body}
            </p>
          </div>
        ))}
      </div>

      <div className="mx-auto mt-8 flex max-w-5xl items-center gap-4 rounded-3xl border border-dashed border-green/40 bg-green-mist p-6">
        <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-ink text-white">
          <IconPhone className="h-5 w-5" />
        </span>
        <div>
          <div className="text-[15.5px] font-semibold text-ink">
            AI Calling Agent{" "}
            <span className="ml-2 rounded-full bg-green-soft px-2.5 py-0.5 text-[12px] font-medium text-green-dark">
              Expanding soon
            </span>
          </div>
          <p className="mt-0.5 text-[14px] text-ink-soft">
            Live AI voice agents that qualify interested owners by phone before
            the introduction reaches your dashboard.
          </p>
        </div>
      </div>
    </section>
  );
}

function Pricing() {
  const included = [
    "10–30 interested owner introductions per month (target range)",
    "Unlimited buy-box sourcing & owner verification",
    "Multi-channel outreach conducted in your name",
    "Full company enrichment on every introduction",
    "Live pipeline dashboard & instant alerts",
    "Cancel anytime",
  ];
  return (
    <section id="pricing" className="dot-grid-dark px-4 py-24 sm:py-32">
      <SectionHeading
        kicker="Pricing"
        title={
          <>
            One plan.{" "}
            <span className="italic text-green-deep">Everything</span> included.
          </>
        }
      />
      <div className="mx-auto mt-14 max-w-lg overflow-hidden rounded-[28px] border border-line bg-white shadow-[0_30px_60px_-40px_rgba(30,60,40,0.5)]">
        <div className="border-b border-line-soft p-8 text-center">
          <div className="text-[14px] font-medium uppercase tracking-widest text-green-dark">
            HavenX Core
          </div>
          <div className="mt-3 flex items-baseline justify-center gap-2">
            <span className="display text-[64px] leading-none text-ink">
              $499
            </span>
            <span className="text-[17px] text-ink-soft">/month</span>
          </div>
          <p className="mt-2 text-[15px] text-ink-soft">
            Deal flow that costs less than a day of analyst time.
          </p>
        </div>
        <ul className="space-y-3.5 p-8">
          {included.map((line) => (
            <li
              key={line}
              className="flex items-start gap-3 text-[15px] text-ink"
            >
              <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-green-soft text-green-dark">
                <IconCheck className="h-3 w-3" />
              </span>
              {line}
            </li>
          ))}
        </ul>
        <div className="px-8 pb-8">
          <Link
            href="/checkout"
            className="flex w-full items-center justify-center gap-2 rounded-2xl bg-green px-6 py-4 text-[17px] font-semibold text-white transition hover:bg-green-deep"
          >
            Start now
            <IconArrowUpRight className="h-5 w-5" />
          </Link>
          <p className="mt-4 text-center text-[13px] leading-relaxed text-ink-faint">
            Your first 10 days cover setup and infrastructure warmup. Outreach
            begins day 11. Your first billing cycle runs 40 days; monthly
            thereafter.
          </p>
        </div>
      </div>
    </section>
  );
}

function Footer() {
  return (
    <footer className="border-t border-line bg-panel px-4 py-12">
      <div className="mx-auto flex max-w-5xl flex-col items-center justify-between gap-6 sm:flex-row">
        <Logo />
        <p className="text-[14px] text-ink-faint">
          © {new Date().getFullYear()} HavenX. Off-market deal flow on
          autopilot.
        </p>
        <div className="flex gap-5 text-[14px] text-ink-soft">
          <a href="#pricing" className="hover:text-ink">
            Pricing
          </a>
          <Link href="/login" className="hover:text-ink">
            Sign in
          </Link>
        </div>
      </div>
    </footer>
  );
}
