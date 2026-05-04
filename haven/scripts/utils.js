const anchor = require("@coral-xyz/anchor");
const { Connection, Keypair, PublicKey, LAMPORTS_PER_SOL } = require("@solana/web3.js");
require("dotenv").config();

const PROGRAM_ID = new PublicKey(process.env.PROGRAM_ID || "44pCUeEtEaKTLFHtrvvEu78N9Xv9A54yb3TTbTdoqif9");
const MOCK_MODE = process.env.MOCK_MODE === "true";

function getConnection() {
  return new Connection(
    process.env.SOLANA_RPC_URL || "https://api.devnet.solana.com",
    "confirmed"
  );
}

function getOperatorKeypair() {
  const raw = process.env.OPERATOR_WALLET_PRIVATE_KEY;
  if (!raw) throw new Error("OPERATOR_WALLET_PRIVATE_KEY not set");
  const bytes = JSON.parse(raw);
  return Keypair.fromSecretKey(Uint8Array.from(bytes));
}

function getProgramStatePDA() {
  const [pda] = PublicKey.findProgramAddressSync(
    [Buffer.from("haven_state")],
    PROGRAM_ID
  );
  return pda;
}

function getVaultPDA() {
  const [pda] = PublicKey.findProgramAddressSync(
    [Buffer.from("haven_vault")],
    PROGRAM_ID
  );
  return pda;
}

function getValidatorListPDA() {
  const [pda] = PublicKey.findProgramAddressSync(
    [Buffer.from("validator_list")],
    PROGRAM_ID
  );
  return pda;
}

function getWithdrawalQueuePDA() {
  const [pda] = PublicKey.findProgramAddressSync(
    [Buffer.from("withdrawal_queue")],
    PROGRAM_ID
  );
  return pda;
}

function getUserBalancePDA(userPubkey) {
  const [pda] = PublicKey.findProgramAddressSync(
    [Buffer.from("user_balance"), new PublicKey(userPubkey).toBuffer()],
    PROGRAM_ID
  );
  return pda;
}

function lamportsToSol(lamports) {
  return lamports / LAMPORTS_PER_SOL;
}

function solToLamports(sol) {
  return Math.floor(sol * LAMPORTS_PER_SOL);
}

function log(msg) {
  console.log(`[${new Date().toISOString()}] ${msg}`);
}

module.exports = {
  PROGRAM_ID,
  MOCK_MODE,
  getConnection,
  getOperatorKeypair,
  getProgramStatePDA,
  getVaultPDA,
  getValidatorListPDA,
  getWithdrawalQueuePDA,
  getUserBalancePDA,
  lamportsToSol,
  solToLamports,
  log,
};
