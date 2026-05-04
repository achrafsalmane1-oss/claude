/**
 * stake.js — triggers when new deposits exceed 10 SOL threshold.
 * Reads unstaked SOL in vault, delegates to approved validators.
 * Uses Solana's native Stake program.
 */
const anchor = require("@coral-xyz/anchor");
const {
  PublicKey,
  StakeProgram,
  Authorized,
  Lockup,
  LAMPORTS_PER_SOL,
  SystemProgram,
  Transaction,
} = require("@solana/web3.js");
const {
  MOCK_MODE,
  getConnection,
  getOperatorKeypair,
  getProgramStatePDA,
  getVaultPDA,
  getValidatorListPDA,
  lamportsToSol,
  log,
} = require("./utils");

const STAKE_THRESHOLD_LAMPORTS = 10 * LAMPORTS_PER_SOL; // stake when > 10 SOL available
const RESERVE_RATIO = 0.20;   // keep 20% liquid
const MIN_STAKE_PER_VALIDATOR = 1 * LAMPORTS_PER_SOL; // Solana minimum

async function main() {
  log("Checking stake eligibility...");

  if (MOCK_MODE) {
    log("MOCK: vault balance = 12.5 SOL");
    log("MOCK: liquid reserve = 2.5 SOL (20%)");
    log("MOCK: available to stake = 10.0 SOL");
    log("MOCK: 2 validators available");
    log("MOCK: would stake 5.0 SOL to each validator");
    log("MOCK: staking skipped (mock mode)");
    return;
  }

  const connection = getConnection();
  const operator = getOperatorKeypair();

  const idl = require("../contract/target/idl/haven.json");
  const provider = new anchor.AnchorProvider(connection, new anchor.Wallet(operator), {});
  const program = new anchor.Program(idl, provider);

  const vaultPDA = getVaultPDA();
  const validatorListPDA = getValidatorListPDA();

  const [vaultInfo, validatorListAccount] = await Promise.all([
    connection.getAccountInfo(vaultPDA),
    program.account.validatorList.fetch(validatorListPDA),
  ]);

  const vaultLamports = vaultInfo?.lamports ?? 0;
  const validators = validatorListAccount.validators;

  log(`Vault balance: ${lamportsToSol(vaultLamports).toFixed(4)} SOL`);
  log(`Approved validators: ${validators.length}`);

  if (vaultLamports < STAKE_THRESHOLD_LAMPORTS) {
    log(`Below ${lamportsToSol(STAKE_THRESHOLD_LAMPORTS)} SOL threshold. Nothing to stake.`);
    return;
  }

  if (validators.length === 0) {
    log("No approved validators. Add validators first with add_validator.");
    return;
  }

  const reserveLamports = Math.floor(vaultLamports * RESERVE_RATIO);
  const stakeable = vaultLamports - reserveLamports;

  if (stakeable < MIN_STAKE_PER_VALIDATOR) {
    log("Not enough SOL to stake after keeping reserve.");
    return;
  }

  // Split evenly across validators
  const perValidator = Math.floor(stakeable / validators.length);

  log(`Staking ${lamportsToSol(stakeable).toFixed(4)} SOL across ${validators.length} validators...`);

  for (const validatorVote of validators) {
    try {
      // Create a new stake account keypair
      const stakeAccount = anchor.web3.Keypair.generate();

      const createStakeIx = StakeProgram.createAccount({
        fromPubkey: operator.publicKey,
        stakePubkey: stakeAccount.publicKey,
        authorized: new Authorized(operator.publicKey, operator.publicKey),
        lockup: new Lockup(0, 0, PublicKey.default),
        lamports: perValidator,
      });

      const delegateIx = StakeProgram.delegate({
        stakePubkey: stakeAccount.publicKey,
        authorizedPubkey: operator.publicKey,
        votePubkey: validatorVote,
      });

      const tx = new Transaction().add(createStakeIx, delegateIx);
      const sig = await connection.sendTransaction(tx, [operator, stakeAccount]);
      await connection.confirmTransaction(sig, "confirmed");

      log(`  ✓ staked ${lamportsToSol(perValidator).toFixed(4)} SOL → validator ${validatorVote.toString().slice(0, 8)}... (tx: ${sig})`);
    } catch (err) {
      log(`  ✗ staking to ${validatorVote.toString().slice(0, 8)}... FAILED: ${err.message}`);
    }
  }

  log("Staking complete.");
}

main().catch((err) => {
  log(`FATAL: ${err.message}`);
  process.exit(1);
});
