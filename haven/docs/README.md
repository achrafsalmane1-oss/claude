# Haven — Technical Documentation

## Overview

Haven is a halal savings app that allows Muslim users to earn ~6-7% APY through Sharia-compliant Solana staking. Users interact with a simple dollar-balance interface; all crypto infrastructure is invisible.

## Architecture

```
User (mobile app)
       │
       ▼
Haven Backend API (Node.js/Express)
       │
       ├── Stripe (payment collection)
       ├── Persona (KYC)
       ├── Supabase (user data / balances in USD)
       │
       └── Haven Solana Program (on-chain)
               │
               └── Solana Validators (staking)
```

## Repository Structure

```
/haven
  /contract    — Solana program (Rust + Anchor)
  /backend     — Node.js + Express API
  /mobile      — React Native (Expo)
  /scripts     — Operator cron scripts
  /docs        — This documentation
```

## Smart Contract

### Program: Haven (`/contract`)

**Language:** Rust (Anchor framework)  
**Network:** Solana Devnet (testnet first, mainnet after audit)

### Instructions

| Instruction | Who calls | Description |
|---|---|---|
| `initialize` | Operator (once) | Sets up program state, vault, validator list, withdrawal queue |
| `deposit` | Operator (on behalf of user) | Pools user SOL into vault |
| `add_validator` | Operator | Adds a validator vote pubkey to approved list |
| `remove_validator` | Operator | Removes a validator |
| `distribute_rewards` | Operator (daily) | Records total reward distribution |
| `credit_user_reward` | Operator (daily, per user) | Credits yield to user's on-chain balance |
| `request_withdrawal` | Operator (on behalf of user) | Queues a withdrawal request |
| `operator_withdraw_for_user` | Operator | Executes a queued withdrawal, sends SOL |
| `pause` / `unpause` | Operator | Emergency circuit breaker |
| `transfer_operator` | Operator | Transfer operator role |

### State Accounts (PDAs)

| Account | Seeds | Description |
|---|---|---|
| `ProgramState` | `["haven_state"]` | Global state: operator, total staked, user count, paused flag |
| Vault | `["haven_vault"]` | SOL holder — receives all deposits |
| `ValidatorList` | `["validator_list"]` | Approved validator vote pubkeys (max 20) |
| `WithdrawalQueue` | `["withdrawal_queue"]` | Pending withdrawal requests (max 500) |
| `UserBalance` | `["user_balance", user_pubkey]` | Per-user balance and pending withdrawal |

## Backend API

### Environment variables

See `/backend/.env.example`

### Key flows

**Deposit flow:**
1. User taps "Add money" → selects amount
2. App calls `POST /deposit/stripe-intent` → gets Stripe `client_secret`
3. Stripe PaymentSheet opens (handles Apple Pay / Google Pay / card)
4. On success: Stripe fires webhook to `POST /deposit/webhook`
5. Backend converts USD → SOL at current price (Jupiter API)
6. Backend calls `deposit()` on Haven program
7. User's DB balance updated

**Yield flow (daily cron):**
1. `distribute_rewards.js` reads all user balances
2. Calculates daily yield at current APY minus 1.5% Haven margin
3. Calls `credit_user_reward` on-chain for each user
4. Inserts row in `yield_logs` table

**Withdrawal flow:**
1. User requests withdrawal via app
2. Backend calls `request_withdrawal` on-chain
3. Every 6 hours: `process_withdrawals.js` reads queue
4. Checks 20% liquidity buffer — only processes if vault has enough
5. `operator_withdraw_for_user` sends SOL back to operator wallet
6. Operator uses Bridge/ACH to send USD back to user's bank

## Mobile App

**Framework:** React Native (Expo), file-based routing via Expo Router  
**Key screens:** Splash → Onboarding → Signup → KYC → Home → Add Money → Withdraw → Settings

### Yield animation (home screen)

The balance ticks upward every 3 seconds using:
```
yield_per_second = (balance * apy) / 365 / 24 / 3600
```
The last two decimal places (`cents`) animate using `react-native-reanimated` with an opacity pulse. This is purely cosmetic — actual yield is credited once daily.

## Operator Scripts (Cron Schedule)

| Script | Schedule | Action |
|---|---|---|
| `status.js` | Every hour | Logs pool health |
| `distribute_rewards.js` | Daily at midnight UTC | Credits yield to all users |
| `process_withdrawals.js` | Every 6 hours | Processes pending withdrawals |
| `stake.js` | When deposits > 10 SOL | Delegates to validators |

## Security Model

- Operator key is the only signer for privileged instructions
- `is_paused` flag blocks all user activity in emergencies
- All arithmetic uses Rust's `checked_add/sub` — no overflows possible
- 20% liquidity buffer enforced in process_withdrawals.js
- Withdrawals are queued and batched — prevents race conditions

## Deployment

### Devnet (current)
```bash
cd contract
anchor build
anchor deploy --provider.cluster devnet
```

### Mainnet (after audit)
- Do NOT deploy to mainnet until a professional security audit is complete
- Recommend Ottersec, Zellic, or Spearbit

## Third-party Services

| Service | Purpose | Sign up |
|---|---|---|
| Stripe | Payment collection (Apple Pay / Google Pay / card) | stripe.com |
| Persona | KYC / identity verification | withpersona.com |
| Supabase | PostgreSQL database + auth | supabase.com |
| Jupiter | SOL price feed | jup.ag |
| Solana RPC | Blockchain connection | helius.dev (recommended) |
