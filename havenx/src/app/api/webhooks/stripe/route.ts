import { NextRequest, NextResponse } from "next/server";
import Stripe from "stripe";
import { activateAccount } from "@/lib/account";

// Stripe webhook: activates the account on checkout completion. Only
// relevant when STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET are configured.
export async function POST(req: NextRequest) {
  const secretKey = process.env.STRIPE_SECRET_KEY;
  const webhookSecret = process.env.STRIPE_WEBHOOK_SECRET;
  if (!secretKey || !webhookSecret) {
    return NextResponse.json({ error: "stripe not configured" }, { status: 400 });
  }

  const stripe = new Stripe(secretKey);
  const signature = req.headers.get("stripe-signature");
  if (!signature) {
    return NextResponse.json({ error: "missing signature" }, { status: 400 });
  }

  let event: Stripe.Event;
  try {
    event = stripe.webhooks.constructEvent(
      await req.text(),
      signature,
      webhookSecret
    );
  } catch {
    return NextResponse.json({ error: "invalid signature" }, { status: 400 });
  }

  if (event.type === "checkout.session.completed") {
    const session = event.data.object;
    const email = session.customer_details?.email ?? session.customer_email;
    if (email) {
      await activateAccount(email.toLowerCase(), {
        customerId:
          typeof session.customer === "string" ? session.customer : undefined,
        subscriptionId:
          typeof session.subscription === "string"
            ? session.subscription
            : undefined,
      });
      // Invoice one: $499 charged immediately for the 40-day first cycle
      // (the recurring price itself starts billing at day 40).
      if (typeof session.customer === "string") {
        await stripe.invoiceItems.create({
          customer: session.customer,
          amount: 49900,
          currency: "usd",
          description: "HavenX Core — first cycle (40 days)",
        });
        const invoice = await stripe.invoices.create({
          customer: session.customer,
          auto_advance: true,
        });
        if (invoice.id) await stripe.invoices.pay(invoice.id);
      }
    }
  }

  return NextResponse.json({ received: true });
}
