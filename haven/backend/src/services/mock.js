/**
 * Mock service — returns realistic fake data when MOCK_MODE=true.
 * Allows full UI/API testing without real Stripe, Solana, or Persona calls.
 */
const MOCK_APY = 0.068;
const MOCK_SOL_PRICE = 150;

function mockBalance(userId) {
  // Deterministic fake balance seeded from userId
  const seed = userId.charCodeAt(0) + userId.charCodeAt(userId.length - 1);
  const base = 500 + (seed % 2000);
  const dailyYield = (base * MOCK_APY) / 365;
  return {
    balance_usd: base.toFixed(6),
    pending_withdrawal_usd: "0.000000",
    total_earned_usd: ((base * 0.3) * MOCK_APY / 365 * 30).toFixed(6),
    apy: MOCK_APY,
  };
}

function mockTransactions(userId) {
  return [
    {
      id: "mock-tx-1",
      type: "deposit",
      amount_usd: "500.00",
      status: "completed",
      created_at: new Date(Date.now() - 30 * 86400000).toISOString(),
    },
    {
      id: "mock-tx-2",
      type: "yield",
      amount_usd: "0.19",
      status: "completed",
      created_at: new Date(Date.now() - 86400000).toISOString(),
    },
    {
      id: "mock-tx-3",
      type: "yield",
      amount_usd: "0.19",
      status: "completed",
      created_at: new Date().toISOString(),
    },
  ];
}

function mockDepositIntent(amountUsd) {
  return {
    clientSecret: "pi_mock_secret_" + Math.random().toString(36).slice(2),
    paymentIntentId: "pi_mock_" + Math.random().toString(36).slice(2),
    amount: amountUsd,
  };
}

function mockWithdrawalRequest(amountUsd) {
  return {
    id: "wd_mock_" + Math.random().toString(36).slice(2),
    status: "pending",
    amount_usd: amountUsd,
    estimated_arrival: "1-2 business days",
  };
}

function mockYieldHistory(userId) {
  const history = [];
  for (let i = 0; i < 30; i++) {
    history.push({
      date: new Date(Date.now() - i * 86400000).toISOString().slice(0, 10),
      yield_usd: "0.190000",
      apy_at_time: MOCK_APY,
      sol_price_at_time: MOCK_SOL_PRICE,
    });
  }
  return history;
}

function mockCurrentApy() {
  return {
    apy: MOCK_APY,
    apy_pct: (MOCK_APY * 100).toFixed(2),
    source: "mock",
    updated_at: new Date().toISOString(),
  };
}

module.exports = {
  mockBalance,
  mockTransactions,
  mockDepositIntent,
  mockWithdrawalRequest,
  mockYieldHistory,
  mockCurrentApy,
  MOCK_APY,
  MOCK_SOL_PRICE,
};
