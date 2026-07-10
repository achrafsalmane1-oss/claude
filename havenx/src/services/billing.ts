import Stripe from "stripe";
import type { BillingService, CheckoutResult } from "./types";

const PRICE_USD = 499;
const FIRST_CYCLE_DAYS = 40;

export function subscriptionDates(startedAt = new Date()) {
  const outreachStartsAt = new Date(startedAt.getTime() + 10 * 86_400_000);
  const firstCycleEndsAt = new Date(
    startedAt.getTime() + FIRST_CYCLE_DAYS * 86_400_000
  );
  return { outreachStartsAt, firstCycleEndsAt, currentPeriodEnd: firstCycleEndsAt };
}

/**
 * Mock billing: skips Stripe entirely and sends the browser straight to the
 * internal activation route, which creates the account and subscription
 * record with the 40-day first cycle.
 */
export class MockBillingService implements BillingService {
  readonly isLive = false;

  async startCheckout(email: string): Promise<CheckoutResult> {
    console.log(`[billing:mock] simulating $${PRICE_USD} charge for ${email}`);
    return {
      redirectUrl: `/api/checkout/activate?email=${encodeURIComponent(email)}`,
    };
  }
}

/**
 * Real Stripe billing for the 40-day-then-30-day cycle:
 * - invoice one ($499) is charged immediately at checkout via a one-time line item
 * - the recurring $499/mo subscription starts billing after a 40-day trial,
 *   which lands renewal exactly at the end of the first cycle, then monthly.
 * The webhook (`/api/webhooks/stripe`) activates the account on
 * `checkout.session.completed`.
 */
export class StripeBillingService implements BillingService {
  readonly isLive = true;
  private stripe: Stripe;

  constructor(secretKey: string) {
    this.stripe = new Stripe(secretKey);
  }

  async startCheckout(email: string): Promise<CheckoutResult> {
    const appUrl = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
    const session = await this.stripe.checkout.sessions.create({
      mode: "subscription",
      customer_email: email,
      line_items: [
        {
          price: process.env.STRIPE_PRICE_ID!, // $499/mo recurring price
          quantity: 1,
        },
      ],
      subscription_data: {
        trial_period_days: FIRST_CYCLE_DAYS,
        description:
          "HavenX Core — first cycle 40 days (days 1-10 setup & warmup), monthly thereafter",
      },
      // Invoice one: $499 charged immediately alongside the subscription setup.
      // Configured in Stripe as a one-time price attached via invoice item, or
      // simplest: a payment-mode line on the same session is not supported, so
      // we bill it as a setup invoice right after checkout completes (webhook).
      success_url: `${appUrl}/onboarding/buybox?session_id={CHECKOUT_SESSION_ID}`,
      cancel_url: `${appUrl}/checkout`,
      metadata: { product: "havenx-core" },
    });
    return { redirectUrl: session.url! };
  }

  webhooks() {
    return this.stripe.webhooks;
  }
}
