const express = require("express");
const supabase = require("../db/supabase");
const { mockBalance, mockTransactions } = require("../services/mock");

const router = express.Router();
const MOCK = () => process.env.MOCK_MODE === "true";

// GET /wallet/balance
router.get("/balance", async (req, res) => {
  const { userId } = req;

  if (MOCK()) {
    const balance = mockBalance(userId);
    return res.json({
      ...balance,
      apy_pct: (balance.apy * 100).toFixed(2),
    });
  }

  try {
    const { data: wallet, error } = await supabase
      .from("wallets")
      .select("balance_usd, pending_withdrawal_usd, total_earned_usd")
      .eq("user_id", userId)
      .single();

    if (error || !wallet) return res.status(404).json({ error: "Wallet not found" });

    // Fetch current APY
    const apyRes = await fetch(`http://localhost:${process.env.PORT || 3000}/apy/current`);
    const apyData = await apyRes.json();

    return res.json({
      balance_usd: wallet.balance_usd,
      pending_withdrawal_usd: wallet.pending_withdrawal_usd,
      total_earned_usd: wallet.total_earned_usd,
      apy: apyData.apy,
      apy_pct: apyData.apy_pct,
    });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Failed to fetch balance" });
  }
});

// GET /wallet/transactions
router.get("/transactions", async (req, res) => {
  const { userId } = req;
  const limit = Math.min(parseInt(req.query.limit) || 50, 100);
  const offset = parseInt(req.query.offset) || 0;

  if (MOCK()) {
    return res.json({ transactions: mockTransactions(userId) });
  }

  try {
    const { data: transactions, error } = await supabase
      .from("transactions")
      .select("id, type, amount_usd, status, created_at, tx_signature")
      .eq("user_id", userId)
      .order("created_at", { ascending: false })
      .range(offset, offset + limit - 1);

    if (error) throw error;
    return res.json({ transactions });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Failed to fetch transactions" });
  }
});

module.exports = router;
