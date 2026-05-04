/**
 * process_withdrawals.js — runs every 6 hours.
 * 1. Reads the on-chain withdrawal queue
 * 2. Checks vault liquidity (keeps 20% buffer)
 * 3. Processes eligible withdrawals oldest-first
 * 4. Logs results
 */
const anchor = require("@coral-xyz/anchor");
const { PublicKey } = require("@solana/web3.js");
const {
  MOCK_MODE,
  getConnection,
  getOperatorKeypair,
  getProgramStatePDA,
  getVaultPDA,
  getWithdrawalQueuePDA,
  getUserBalancePDA,
  lamportsToSol,
  log,
} = require("./utils");

const LIQUIDITY_BUFFER = 0.20; // always keep 20% of vault liquid

async function main() {
  log("Processing pending withdrawals...");

  if (MOCK_MODE) {
    log("MOCK: 3 pending withdrawals in queue");
    log("MOCK: vault has 25.0 SOL (25% liquid — above 20% buffer)");
    log("MOCK: processing request #1: user 111...  1.0 SOL (SKIPPED — mock)");
    log("MOCK: processing request #2: user 222...  0.3 SOL (SKIPPED — mock)");
    log("MOCK: processing request #3: user 333...  0.2 SOL (SKIPPED — mock)");
    log("MOCK: all withdrawals processed (simulated)");
    return;
  }

  const connection = getConnection();
  const operator = getOperatorKeypair();

  const idl = require("../contract/target/idl/haven.json");
  const provider = new anchor.AnchorProvider(connection, new anchor.Wallet(operator), {});
  const program = new anchor.Program(idl, provider);

  const statePDA = getProgramStatePDA();
  const vaultPDA = getVaultPDA();
  const queuePDA = getWithdrawalQueuePDA();

  const [stateAccount, vaultInfo, queueAccount] = await Promise.all([
    program.account.programState.fetch(statePDA),
    connection.getAccountInfo(vaultPDA),
    program.account.withdrawalQueue.fetch(queuePDA),
  ]);

  const vaultLamports = vaultInfo?.lamports ?? 0;
  const requests = queueAccount.requests;

  log(`Vault balance: ${lamportsToSol(vaultLamports).toFixed(4)} SOL`);
  log(`Pending requests: ${requests.length}`);

  if (requests.length === 0) {
    log("No pending withdrawals. Done.");
    return;
  }

  // Keep LIQUIDITY_BUFFER % of vault as reserve
  const maxDispersable = Math.floor(vaultLamports * (1 - LIQUIDITY_BUFFER));
  let dispensed = 0;
  let successCount = 0;
  let skippedCount = 0;

  // Sort oldest first
  const sorted = [...requests].sort((a, b) => Number(a.requestedAt) - Number(b.requestedAt));

  for (const req of sorted) {
    const amount = Number(req.amountLamports);

    if (dispensed + amount > maxDispersable) {
      log(`  SKIPPED request #${req.id}: insufficient liquid reserve (would breach ${LIQUIDITY_BUFFER * 100}% buffer)`);
      skippedCount++;
      continue;
    }

    try {
      const userBalancePDA = getUserBalancePDA(req.user.toString());

      await program.methods
        .operatorWithdrawForUser(new anchor.BN(amount), req.id)
        .accounts({
          programState: statePDA,
          userBalance: userBalancePDA,
          withdrawalQueue: queuePDA,
          vault: vaultPDA,
          user: req.user,
          operator: operator.publicKey,
          systemProgram: anchor.web3.SystemProgram.programId,
        })
        .signers([operator])
        .rpc();

      dispensed += amount;
      successCount++;
      log(`  ✓ withdrawal #${req.id}: ${req.user.toString().slice(0, 8)}... ${lamportsToSol(amount).toFixed(4)} SOL`);
    } catch (err) {
      log(`  ✗ withdrawal #${req.id} FAILED: ${err.message}`);
    }
  }

  log(`Done: ${successCount} processed, ${skippedCount} deferred (liquidity buffer).`);
  log(`Total dispersed: ${lamportsToSol(dispensed).toFixed(4)} SOL`);
}

main().catch((err) => {
  log(`FATAL: ${err.message}`);
  process.exit(1);
});
