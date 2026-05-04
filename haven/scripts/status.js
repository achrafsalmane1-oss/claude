/**
 * status.js — prints full Haven program status.
 * Cron: every hour.
 */
const { Connection, LAMPORTS_PER_SOL } = require("@solana/web3.js");
const {
  MOCK_MODE,
  getConnection,
  getProgramStatePDA,
  getVaultPDA,
  getValidatorListPDA,
  getWithdrawalQueuePDA,
  lamportsToSol,
  log,
} = require("./utils");

const SOL_PRICE_USD = 150; // fallback; replace with Jupiter price feed in prod

async function fetchSolPrice() {
  try {
    const res = await fetch(
      "https://price.jup.ag/v6/price?ids=SOL"
    );
    const data = await res.json();
    return data?.data?.SOL?.price ?? SOL_PRICE_USD;
  } catch {
    return SOL_PRICE_USD;
  }
}

async function main() {
  if (MOCK_MODE) {
    log("=== HAVEN STATUS (MOCK MODE) ===");
    log("Total staked:       100.00 SOL  ($15,000.00 USD)");
    log("Total users:        42");
    log("Pending withdrawals: 3  (total: 1.5 SOL)");
    log("Vault balance:      25.00 SOL  (25% liquid)");
    log("Current APY:        6.80%");
    log("Haven revenue today: $0.62 USD");
    log("Validators:         2 active");
    log("Program paused:     false");
    return;
  }

  const connection = getConnection();

  log("Fetching program state...");

  const [statePDA, vaultPDA, validatorPDA, queuePDA] = await Promise.all([
    getProgramStatePDA(),
    getVaultPDA(),
    getValidatorListPDA(),
    getWithdrawalQueuePDA(),
  ]);

  const [stateInfo, vaultInfo] = await Promise.all([
    connection.getAccountInfo(statePDA),
    connection.getAccountInfo(vaultPDA),
  ]);

  const solPrice = await fetchSolPrice();
  const vaultLamports = vaultInfo?.lamports ?? 0;
  const vaultSol = lamportsToSol(vaultLamports);

  // Decode program state (skip 8-byte discriminator)
  // operator(32) + total_staked(8) + total_users(8) + is_paused(1) + bump(1)
  let totalStaked = 0n;
  let totalUsers = 0n;
  let isPaused = false;

  if (stateInfo) {
    const buf = stateInfo.data;
    totalStaked = buf.readBigUInt64LE(8 + 32);
    totalUsers = buf.readBigUInt64LE(8 + 32 + 8);
    isPaused = buf[8 + 32 + 8 + 8] === 1;
  }

  const totalStakedSol = lamportsToSol(Number(totalStaked));
  const totalStakedUsd = totalStakedSol * solPrice;
  const liquidPct = totalStakedSol > 0 ? (vaultSol / totalStakedSol) * 100 : 0;

  // Rough APY estimate — in prod this comes from validator performance
  const estimatedApy = 6.8;
  const dailyYieldUsd = (totalStakedUsd * estimatedApy) / 100 / 365;
  const havenRevenueUsd = (totalStakedUsd * 0.015) / 100 / 365;

  log("=== HAVEN STATUS ===");
  log(`Total staked:        ${totalStakedSol.toFixed(4)} SOL  ($${totalStakedUsd.toFixed(2)} USD)`);
  log(`Total users:         ${totalUsers.toString()}`);
  log(`Vault (liquid):      ${vaultSol.toFixed(4)} SOL  (${liquidPct.toFixed(1)}% of pool)`);
  log(`SOL price:           $${solPrice.toFixed(2)}`);
  log(`Estimated APY:       ${estimatedApy}%`);
  log(`Daily yield (total): $${dailyYieldUsd.toFixed(2)} USD`);
  log(`Haven revenue/day:   $${havenRevenueUsd.toFixed(2)} USD`);
  log(`Program paused:      ${isPaused}`);
}

main().catch((err) => {
  log(`ERROR: ${err.message}`);
  process.exit(1);
});
