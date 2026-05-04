const express = require("express");
const supabase = require("../db/supabase");
const { mockWithdrawalRequest } = require("../services/mock");

const router = express.Router();
const MOCK = () => process.env.MOCK_MODE === "true";

const LIQUIDITY_BUFFER = 0.20;

// POST /withdraw/request
router.post("/request", async (req, res) => {
  const { userId } = req;
  const amountUsd = parseFloat(req.body.amount_usd);

  if (!amountUsd || amountUsd <= 0) {
    return res.status(400).json({ error: "Invalid amount" });
  }

  if (MOCK()) {
    return res.json(mockWithdrawalRequest(amountUsd));
  }

  try {
    // 1. Check user balance
    const { data: wallet } = await supabase
      .from("wallets")
      .select("balance_usd")
      .eq("user_id", userId)
      .single();

    if (!wallet) return res.status(404).json({ error: "Wallet not found" });
    if (parseFloat(wallet.balance_usd) < amountUsd) {
      return res.status(400).json({ error: "Insufficient balance" });
    }

    // 2. Create withdrawal transaction
    const { data: tx, error } = await supabase
      .from("transactions")
      .insert({
        user_id: userId,
        type: "withdrawal",
        amount_usd: amountUsd,
        status: "pending",
      })
      .select("id")
      .single();

    if (error) throw error;

    // 3. Lock funds as pending
    await supabase
      .from("wallets")
      .update({
        balance_usd: parseFloat(wallet.balance_usd) - amountUsd,
        pending_withdrawal_usd: supabase.rpc("add_pending_withdrawal", {
          p_user_id: userId,
          p_amount: amountUsd,
        }),
      })
      .eq("user_id", userId);

    return res.json({
      id: tx.id,
      status: "pending",
      amount_usd: amountUsd,
      estimated_arrival: "1-2 business days",
    });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Withdrawal request failed" });
  }
});

// GET /withdraw/status/:id
router.get("/status/:id", async (req, res) => {
  const { userId } = req;
  const { id } = req.params;

  if (MOCK()) {
    return res.json({ id, status: "pending", amount_usd: "50.00" });
  }

  try {
    const { data: tx, error } = await supabase
      .from("transactions")
      .select("id, type, amount_usd, status, created_at, tx_signature")
      .eq("id", id)
      .eq("user_id", userId)  // prevents user from querying other users' txs
      .single();

    if (error || !tx) return res.status(404).json({ error: "Withdrawal not found" });

    return res.json(tx);
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Failed to fetch withdrawal status" });
  }
});

module.exports = router;
