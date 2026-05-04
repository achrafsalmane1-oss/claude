/**
 * Solana service — wraps interactions with the Haven on-chain program.
 */
const anchor = require("@coral-xyz/anchor");
const { Connection, Keypair, PublicKey, LAMPORTS_PER_SOL } = require("@solana/web3.js");

const PROGRAM_ID = new PublicKey(
  process.env.PROGRAM_ID || "44pCUeEtEaKTLFHtrvvEu78N9Xv9A54yb3TTbTdoqif9"
);

function getConnection() {
  return new Connection(process.env.SOLANA_RPC_URL || "https://api.devnet.solana.com", "confirmed");
}

function getOperatorKeypair() {
  const raw = process.env.OPERATOR_WALLET_PRIVATE_KEY;
  if (!raw) throw new Error("OPERATOR_WALLET_PRIVATE_KEY not set");
  return Keypair.fromSecretKey(Uint8Array.from(JSON.parse(raw)));
}

function getPDA(seeds) {
  const [pda] = PublicKey.findProgramAddressSync(seeds, PROGRAM_ID);
  return pda;
}

function programStatePDA() { return getPDA([Buffer.from("haven_state")]); }
function vaultPDA()         { return getPDA([Buffer.from("haven_vault")]); }
function userBalancePDA(userPubkey) {
  return getPDA([Buffer.from("user_balance"), new PublicKey(userPubkey).toBuffer()]);
}
function withdrawalQueuePDA() { return getPDA([Buffer.from("withdrawal_queue")]); }

async function getProgram() {
  const connection = getConnection();
  const operator = getOperatorKeypair();
  let idl;
  try {
    idl = require("../../contract/target/idl/haven.json");
  } catch {
    throw new Error("IDL not found — run `anchor build` first");
  }
  const provider = new anchor.AnchorProvider(connection, new anchor.Wallet(operator), {});
  return new anchor.Program(idl, provider);
}

async function depositToProgram(userPubkeyStr, lamports) {
  const program = await getProgram();
  const connection = getConnection();
  const operator = getOperatorKeypair();

  // In the current design, the backend operator calls deposit on behalf of the user.
  // The user's on-chain presence is represented by their Solana pubkey (generated at signup).
  const userPubkey = new PublicKey(userPubkeyStr);

  const sig = await program.methods
    .deposit(new anchor.BN(lamports))
    .accounts({
      programState: programStatePDA(),
      userBalance: userBalancePDA(userPubkeyStr),
      vault: vaultPDA(),
      user: operator.publicKey,  // operator funds on behalf (fundOnBehalf pattern)
      systemProgram: anchor.web3.SystemProgram.programId,
    })
    .signers([operator])
    .rpc();

  return sig;
}

async function requestWithdrawal(userPubkeyStr, lamports) {
  const program = await getProgram();
  const operator = getOperatorKeypair();

  // Operator queues the withdrawal on behalf of the user
  const sig = await program.methods
    .requestWithdrawal(new anchor.BN(lamports))
    .accounts({
      programState: programStatePDA(),
      userBalance: userBalancePDA(userPubkeyStr),
      withdrawalQueue: withdrawalQueuePDA(),
      user: operator.publicKey,
      systemProgram: anchor.web3.SystemProgram.programId,
    })
    .signers([operator])
    .rpc();

  return sig;
}

async function getUserBalance(userPubkeyStr) {
  const program = await getProgram();
  const pda = userBalancePDA(userPubkeyStr);
  try {
    const account = await program.account.userBalance.fetch(pda);
    return {
      balanceLamports: account.balanceLamports.toNumber(),
      pendingWithdrawalLamports: account.pendingWithdrawalLamports.toNumber(),
    };
  } catch {
    return { balanceLamports: 0, pendingWithdrawalLamports: 0 };
  }
}

module.exports = {
  depositToProgram,
  requestWithdrawal,
  getUserBalance,
  getConnection,
  LAMPORTS_PER_SOL,
};
