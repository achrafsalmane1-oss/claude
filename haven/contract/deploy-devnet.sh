#!/bin/bash
# deploy-devnet.sh — run this locally after getting devnet SOL from faucet.solana.com
set -e

PROGRAM_ID="44pCUeEtEaKTLFHtrvvEu78N9Xv9A54yb3TTbTdoqif9"
KEYPAIR="./haven-keypair.json"
SO_PATH="./target/deploy/haven.so"

echo "=== Haven Devnet Deploy ==="
echo "Program ID: $PROGRAM_ID"
echo ""

# 1. Make sure Solana CLI points to devnet
solana config set --url devnet

# 2. Check operator balance (need ~3-4 SOL for program deploy)
BALANCE=$(solana balance --url devnet)
echo "Operator balance: $BALANCE"

# 3. Airdrop if needed (get SOL from https://faucet.solana.com if this fails)
if [[ "$BALANCE" == "0 SOL" ]]; then
  echo "Getting devnet SOL from faucet..."
  solana airdrop 2 --url devnet || {
    echo ""
    echo "Airdrop rate-limited. Get SOL manually:"
    echo "  1. Visit https://faucet.solana.com"
    echo "  2. Paste your address: $(solana-keygen pubkey $KEYPAIR)"
    echo "  3. Re-run this script"
    exit 1
  }
fi

# 4. Build (skips if already built)
echo "Building program..."
cargo-build-sbf

# 5. Deploy
echo "Deploying to devnet..."
solana program deploy "$SO_PATH" \
  --keypair "$KEYPAIR" \
  --url devnet \
  --program-id "$KEYPAIR"

echo ""
echo "=== Deploy complete! ==="
echo "Program ID: $PROGRAM_ID"
echo "Explorer: https://explorer.solana.com/address/$PROGRAM_ID?cluster=devnet"
echo ""
echo "Next: run initialize script to set up program state"
echo "  cd ../../scripts && node initialize.js"
