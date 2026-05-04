/**
 * initialize.js — run ONCE after deploying the Haven program to devnet.
 * Sets up program state, validator list, and withdrawal queue PDAs.
 */
const anchor = require("@coral-xyz/anchor");
const { PublicKey } = require("@solana/web3.js");
const {
  MOCK_MODE,
  getConnection,
  getOperatorKeypair,
  getProgramStatePDA,
  getValidatorListPDA,
  getWithdrawalQueuePDA,
  log,
  PROGRAM_ID,
} = require("./utils");
require("dotenv").config();

async function main() {
  if (MOCK_MODE) {
    log("MOCK: program would be initialized here. Set MOCK_MODE=false to run for real.");
    return;
  }

  log("Initializing Haven program on devnet...");

  const connection = getConnection();
  const operator = getOperatorKeypair();
  const idl = require("../contract/target/idl/haven.json");
  const provider = new anchor.AnchorProvider(connection, new anchor.Wallet(operator), {
    commitment: "confirmed",
  });
  const program = new anchor.Program(idl, provider);

  const statePDA   = getProgramStatePDA();
  const validatorPDA = getValidatorListPDA();
  const queuePDA   = getWithdrawalQueuePDA();

  // Check if already initialized
  const existing = await connection.getAccountInfo(statePDA);
  if (existing) {
    log(`Already initialized. State PDA: ${statePDA.toString()}`);
    return;
  }

  const tx = await program.methods
    .initialize()
    .accounts({
      programState:    statePDA,
      validatorList:   validatorPDA,
      withdrawalQueue: queuePDA,
      operator:        operator.publicKey,
      systemProgram:   anchor.web3.SystemProgram.programId,
    })
    .signers([operator])
    .rpc();

  log(`✓ Initialized! Transaction: ${tx}`);
  log(`  programState:    ${statePDA.toString()}`);
  log(`  validatorList:   ${validatorPDA.toString()}`);
  log(`  withdrawalQueue: ${queuePDA.toString()}`);
  log(`Explorer: https://explorer.solana.com/tx/${tx}?cluster=devnet`);
}

main().catch(err => {
  log(`FATAL: ${err.message}`);
  process.exit(1);
});
