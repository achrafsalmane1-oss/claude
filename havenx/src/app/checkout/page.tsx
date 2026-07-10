import Link from "next/link";
import { redirect } from "next/navigation";
import { billing } from "@/services";
import { db } from "@/lib/db";
import { activateAccount } from "@/lib/account";
import { createSession } from "@/lib/session";
import { Logo, IconCheck, IconArrowRight } from "@/components/icons";

async function startCheckout(formData: FormData) {
  "use server";
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  if (!email || !email.includes("@")) redirect("/checkout?error=email");

  if (billing.isLive) {
    // Real Stripe: hand the browser to Stripe Checkout; the webhook activates.
    const { redirectUrl } = await billing.startCheckout(email);
    redirect(redirectUrl);
  }

  // Mock billing: simulate the charge and activate inline.
  await billing.startCheckout(email);
  const user = await activateAccount(email);
  await createSession(user.id);
  const mandate = await db.mandate.findUnique({ where: { userId: user.id } });
  redirect(mandate ? "/dashboard" : "/onboarding/buybox");
}

export default async function CheckoutPage({
  searchParams,
}: {
  searchParams: Promise<{ error?: string }>;
}) {
  const { error } = await searchParams;
  return (
    <main className="dot-grid-dark flex min-h-screen flex-col bg-cream px-4 py-8">
      <div className="mx-auto w-full max-w-5xl">
        <Link href="/">
          <Logo />
        </Link>
      </div>

      <div className="mx-auto mt-10 grid w-full max-w-4xl gap-8 lg:grid-cols-[1fr_380px]">
        {/* Order summary */}
        <div className="order-2 lg:order-1">
          <h1 className="display text-[40px] leading-tight text-ink">
            Start your <span className="italic text-green-deep">deal flow</span>
          </h1>
          <p className="mt-3 max-w-md text-[16px] leading-relaxed text-ink-soft">
            One subscription. Sourcing, verification, and multi-channel
            outreach in your name — with interested owners delivered to your
            dashboard.
          </p>

          <div className="mt-8 space-y-4">
            {[
              ["Days 1–10", "Setup & infrastructure warmup. Sourcing for your buy-box begins immediately."],
              ["Day 11", "Outreach begins, in your name, across channels."],
              ["Day 40", "First billing cycle ends. Renews monthly ($499) thereafter."],
            ].map(([when, what]) => (
              <div key={when} className="flex gap-4">
                <span className="display mt-0.5 w-24 shrink-0 text-[17px] italic text-green-deep">
                  {when}
                </span>
                <p className="text-[15px] leading-relaxed text-ink-soft">
                  {what}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* Payment card */}
        <div className="order-1 lg:order-2">
          <div className="rounded-[24px] border border-line bg-white p-7 shadow-[0_24px_50px_-36px_rgba(30,60,40,0.5)]">
            <div className="flex items-baseline justify-between">
              <span className="text-[15px] font-semibold text-ink">
                HavenX Core
              </span>
              <span>
                <span className="display text-[34px] text-ink">$499</span>
                <span className="text-[14px] text-ink-soft">/mo</span>
              </span>
            </div>
            <ul className="mt-4 space-y-2.5 border-b border-line-soft pb-5">
              {[
                "10–30 interested introductions / month",
                "Outreach in your name, fully managed",
                "Live pipeline dashboard",
              ].map((l) => (
                <li
                  key={l}
                  className="flex items-center gap-2.5 text-[13.5px] text-ink-soft"
                >
                  <span className="flex h-4.5 w-4.5 items-center justify-center rounded-full bg-green-soft text-green-dark">
                    <IconCheck className="h-2.5 w-2.5" />
                  </span>
                  {l}
                </li>
              ))}
            </ul>

            <form action={startCheckout} className="mt-5 space-y-3.5">
              <div>
                <label
                  htmlFor="email"
                  className="mb-1.5 block text-[13px] font-medium text-ink"
                >
                  Work email
                </label>
                <input
                  id="email"
                  name="email"
                  type="email"
                  required
                  placeholder="you@yourfund.com"
                  className="w-full rounded-xl border border-line bg-panel px-3.5 py-2.5 text-[15px] text-ink outline-none transition placeholder:text-ink-faint focus:border-green focus:bg-white"
                />
                {error === "email" && (
                  <p className="mt-1 text-[12.5px] text-fall">
                    Enter a valid email address.
                  </p>
                )}
              </div>

              {!billing.isLive && (
                <div className="rounded-xl border border-dashed border-line bg-panel px-3.5 py-3 text-[12.5px] leading-relaxed text-ink-faint">
                  Demo environment — no card required. Payment is simulated and
                  you&apos;ll be dropped straight into onboarding.
                </div>
              )}

              <button
                type="submit"
                className="flex w-full items-center justify-center gap-2 rounded-2xl bg-green px-6 py-3.5 text-[16px] font-semibold text-white transition hover:bg-green-deep"
              >
                {billing.isLive ? "Continue to payment" : "Start subscription"}
                <IconArrowRight className="h-4.5 w-4.5" />
              </button>
            </form>

            <p className="mt-4 text-center text-[12px] leading-relaxed text-ink-faint">
              $499 charged today. Your first billing cycle runs 40 days — days
              1–10 are setup &amp; warmup before outreach begins. Renews
              monthly. Cancel anytime.
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}
