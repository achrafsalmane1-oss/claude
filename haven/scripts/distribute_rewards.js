/**
 * distribute_rewards.js — daily cron job (midnight UTC).
 * 1. Reads all user balances from on-chain
 * 2. Fetches current validator APY
 * 3. Calculates each user's share
 * 4. Deducts Haven's 1.5% margin
 * 5. Credits each user on-chain via credit_user_reward
 * 6. Logs full distribution report
 */
const anchor = require("@coral-xyz/anchor");
const { PublicKey, LAMPORTS_PER_SOL } = require("@solana/web3.js");
const {
  MOCK_MODE,
  getConnection,
  getOperatorKeypair,
  getProgramStatePDA,
  getUserBalancePDA,
  lamportsToSol,
  solToLamports,
  log,
} = require("./utils");

const HAVEN_MARGIN = 0.015;        // 1.5% annual margin kept by Haven
const VALIDATOR_APY = 0.068;       // 6.8% gross APY from validators
const USER_APY = VALIDATOR_APY - HAVEN_MARGIN; // 5.3% net to users

// In production, fetch real user list from Supabase or on-chain logs.
// Here we read from environment / a local JSON file for the operator script.
async function loadUserList() {
  if (MOCK_MODE) {
    return [
      { pubkey: "11111111111111111111111111111111", balanceLamports: 10_000_000_000 },
      { pubkey: "22222222222222222222222222222222", balanceLamports: 5_000_000_000 },
      { pubkey: "33333333333333333333333333333333", balanceLamports: 2_000_000_000 },
    ];
  }

  // In prod: query Supabase for all users with solana_pubkey, then fetch
  // their on-chain UserBalance account to get current lamport balance.
  throw new Error("Non-mock user list loading not yet implemented — integrate with Supabase");
}

function calculateDailyReward(balanceLamports) {
  // daily_reward = balance * user_apy / 365
  return Math.floor((balanceLamports * USER_APY) / 365);
}

function calculateHavenRevenue(balanceLamports) {
  return Math.floor((balanceLamports * HAVEN_MARGIN) / 365);
}

async function main() {
  log("Starting daily reward distribution...");

  const users = await loadUserList();
  const totalBalanceLamports = users.reduce((sum, u) => sum + u.balanceLamports, 0);

  const report = users.map((u) => ({
    pubkey: u.pubkey,
    balanceLamports: u.balanceLamports,
    rewardLamports: calculateDailyReward(u.balanceLamports),
    havenRevenueLamports: calculateHavenRevenue(u.balanceLamports),
  }));

  const totalRewardLamports = report.reduce((s, r) => s + r.rewardLamports, 0);
  const totalHavenRevenueLamports = report.reduce((s, r) => s + r.havenRevenueLamports, 0);

  log("=== DISTRIBUTION REPORT ===");
  log(`Users:              ${users.length}`);
  log(`Total pool:         ${lamportsToSol(totalBalanceLamports).toFixed(4)} SOL`);
  log(`Total rewards:      ${lamportsToSol(totalRewardLamports).toFixed(6)} SOL`);
  log(`Haven revenue:      ${lamportsToSol(totalHavenRevenueLamports).toFixed(6)} SOL`);
  log(`Effective user APY: ${(USER_APY * 100).toFixed(2)}%`);

  if (MOCK_MODE) {
    for (const r of report) {
      log(
        `  ${r.pubkey.slice(0, 8)}...  ` +
        `balance: ${lamportsToSol(r.balanceLamports).toFixed(4)} SOL  ` +
        `reward: ${lamportsToSol(r.rewardLamports).toFixed(6)} SOL (MOCK - not sent)`
      );
    }
    log("MOCK MODE: on-chain distribution skipped.");
    return;
  }

  // Real path: submit credit_user_reward for each user
  const connection = getConnection();
  const operator = getOperatorKeypair();

  // Load the IDL — in prod, store as generated file after anchor build
  const idl = require("../contract/target/idl/haven.json");
  const provider = new anchor.AnchorProvider(connection, new anchor.Wallet(operator), {});
  const program = new anchor.Program(idl, provider);

  let successCount = 0;
  let failCount = 0;

  for (const r of report) {
    if (r.rewardLamports === 0) continue;

    try {
      const userBalancePDA = getUserBalancePDA(r.pubkey);
      const statePDA = getProgramStatePDA();

      await program.methods
        .creditUserReward(new anchor.BN(r.rewardLamports))
        .accounts({
          programState: statePDA,
          userBalance: userBalancePDA,
          operator: operator.publicKey,
        })
        .signers([operator])
        .rpc();

      log(`  ✓ credited ${r.pubkey.slice(0, 8)}... +${lamportsToSol(r.rewardLamports).toFixed(6)} SOL`);
      successCount++;
    } catch (err) {
      log(`  ✗ FAILED ${r.pubkey.slice(0, 8)}...: ${err.message}`);
      failCount++;
    }
  }

  log(`Distribution complete: ${successCount} succeeded, ${failCount} failed.`);
}

main().catch((err) => {
  log(`FATAL: ${err.message}`);
  process.exit(1);
});
