const express = require("express");
const { mockCurrentApy } = require("../services/mock");

const router = express.Router();
const MOCK = () => process.env.MOCK_MODE === "true";

// GET /apy/current
router.get("/current", async (_req, res) => {
  if (MOCK()) {
    return res.json(mockCurrentApy());
  }

  try {
    // Fetch from Solana validator performance API
    // In prod: query your staked validator accounts for actual epoch rewards
    const epochRes = await fetch(
      `${process.env.SOLANA_RPC_URL}`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          jsonrpc: "2.0",
          id: 1,
          method: "getInflationRate",
        }),
      }
    );
    const epochData = await epochRes.json();
    const inflationRate = epochData?.result?.validator ?? 0.068;

    return res.json({
      apy: inflationRate,
      apy_pct: (inflationRate * 100).toFixed(2),
      source: "solana_inflation",
      updated_at: new Date().toISOString(),
    });
  } catch (err) {
    console.error(err);
    return res.status(500).json({ error: "Failed to fetch APY" });
  }
});

module.exports = router;
