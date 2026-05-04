const express = require("express");
const supabase = require("../db/supabase");
const { mockYieldHistory } = require("../services/mock");

const router = express.Router();
const MOCK = () => process.env.MOCK_MODE === "true";

// GET /yield/history
router.get("/history", async (req, res) => {
  const { userId } = req;
  const days = Math.min(parseInt(req.query.days) || 30, 365);

  if (MOCK()) {
    return res.json({ history: mockYieldHistory(userId) });
  }

  try {
    const since = new Date();
    since.setDate(since.getDate() - days);

    const { data, error } = await supabase
      .from("yield_logs")
      .select("date, yield_usd, apy_at_time, sol_price_at_time")
      .eq("user_id", userId)
      .gte("date", since.toISOString().slice(0, 10))
      .order("date", { ascending: false });

    if (error) throw error;
    return res.json({ history: data });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Failed to fetch yield history" });
  }
});

module.exports = router;
