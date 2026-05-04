const express = require("express");
const Stripe = require("stripe");
const supabase = require("../db/supabase");
const { depositToProgram, LAMPORTS_PER_SOL } = require("../services/solana");
const { mockDepositIntent } = require("../services/mock");
const { authMiddleware } = require("../middleware/auth");

const router = express.Router();
const MOCK = () => process.env.MOCK_MODE === "true";

function getStripe() {
  return new Stripe(process.env.STRIPE_SECRET_KEY);
}

async function getSolPrice() {
  try {
    const res = await fetch("https://price.jup.ag/v6/price?ids=SOL");
    const data = await res.json();
    return data?.data?.SOL?.price ?? 150;
  } catch {
    return 150;
  }
}

// POST /deposit/stripe-intent  (requires auth)
router.post("/stripe-intent", authMiddleware, async (req, res) => {
  const { userId } = req;
  const amountUsd = parseFloat(req.body.amount_usd);

  if (!amountUsd || amountUsd < 10) {
    return res.status(400).json({ error: "Minimum deposit is $10" });
  }

  if (MOCK()) {
    return res.json(mockDepositIntent(amountUsd));
  }

  try {
    const stripe = getStripe();
    // Amount in cents — all Stripe amounts are integers
    const amountCents = Math.round(amountUsd * 100);

    const paymentIntent = await stripe.paymentIntents.create({
      amount: amountCents,
      currency: "usd",
      automatic_payment_methods: { enabled: true },
      metadata: { userId, amountUsd: amountUsd.toString() },
    });

    // Log pending transaction
    await supabase.from("transactions").insert({
      user_id: userId,
      type: "deposit",
      amount_usd: amountUsd,
      status: "pending",
      stripe_payment_id: paymentIntent.id,
    });

    return res.json({
      clientSecret: paymentIntent.client_secret,
      paymentIntentId: paymentIntent.id,
      amount: amountUsd,
    });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Failed to create payment intent" });
  }
});

// POST /deposit/webhook  (Stripe fires this — raw body, no auth)
router.post("/webhook", async (req, res) => {
  if (MOCK()) return res.json({ received: true });

  const stripe = getStripe();
  const sig = req.headers["stripe-signature"];

  let event;
  try {
    event = stripe.webhooks.constructEvent(
      req.body,
      sig,
      process.env.STRIPE_WEBHOOK_SECRET
    );
  } catch (err) {
    return res.status(400).json({ error: `Webhook signature verification failed: ${err.message}` });
  }

  if (event.type !== "payment_intent.succeeded") {
    return res.json({ received: true });
  }

  const intent = event.data.object;
  const userId = intent.metadata.userId;
  const amountUsd = parseFloat(intent.metadata.amountUsd);

  try {
    // 1. Fetch the user's Solana pubkey
    const { data: user } = await supabase
      .from("users")
      .select("solana_pubkey")
      .eq("id", userId)
      .single();

    const solPrice = await getSolPrice();
    const amountSol = amountUsd / solPrice;
    const lamports = Math.floor(amountSol * LAMPORTS_PER_SOL);

    // 2. Update transaction to processing
    await supabase
      .from("transactions")
      .update({ status: "processing", amount_sol: amountSol })
      .eq("stripe_payment_id", intent.id);

    // 3. Deposit to Solana program
    let txSig = null;
    if (user?.solana_pubkey) {
      txSig = await depositToProgram(user.solana_pubkey, lamports);
    }

    // 4. Update wallet balance
    await supabase.rpc("increment_wallet_balance", {
      p_user_id: userId,
      p_amount_usd: amountUsd,
      p_amount_sol: amountSol,
    });

    // 5. Mark transaction complete
    await supabase
      .from("transactions")
      .update({ status: "completed", tx_signature: txSig })
      .eq("stripe_payment_id", intent.id);

    return res.json({ received: true });
  } catch (err) {
    console.error("Deposit webhook error:", err);
    await supabase
      .from("transactions")
      .update({ status: "failed" })
      .eq("stripe_payment_id", intent.id);
    return res.status(500).json({ error: "Deposit processing failed" });
  }
});

module.exports = router;
