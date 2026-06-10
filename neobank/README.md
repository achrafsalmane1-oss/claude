# OpenBank — an onchain neobank powered by OpenFinance

A multi-chain neobank built on the OpenFinance (OF) MCP server:
Privy-provisioned wallets (EVM + Solana), fiat onramp, transfers, swaps, and investing —
all behind a clean banking UI.

## Features

- **Home** — total balance and per-chain holdings across Ethereum, Polygon, Base,
  Arbitrum, Optimism, and Solana, with live USD values.
- **Add funds** — fiat → crypto checkout. INR routes through Onramp.money (UPI/IMPS),
  everything else through Moonpay. Funds land directly in your wallet.
- **Send** — same-chain transfers (EVM ERC-20 + native, Solana SPL + SOL) with an
  explicit confirmation step for external (non-self) recipients.
- **Swap** — Solana↔Solana routes through Jupiter; same-chain EVM and all cross-chain
  pairs route through Relay (40+ chains).
- **Markets** — token search across 200+ chains with price, 24h change, market cap, and
  DexScreener verification links.
- **Invest** — Hyperliquid perps account summary + live mids, and trending Polymarket
  prediction markets.
- **Activity** — append-only ledger of every action initiated through the app.

## Architecture

```
Browser UI (Next.js app router, Tailwind)
        │  fetch
        ▼
API routes (src/app/api/*)        ← validation, normalization, external-send confirmation
        │  callOF(tool, args)
        ▼
OF client (src/lib/of/client.ts)  ← MCP client over Streamable HTTP, or mock mode
        │
        ▼
OpenFinance MCP server            ← wallets, onramp, sends, Relay, Jupiter,
                                    Hyperliquid, Polymarket
```

## Getting started

```bash
npm install
npm run dev
```

With no configuration the app runs in **mock mode** with realistic demo data.

To go live, copy `.env.example` to `.env.local` and set:

| Variable | Purpose |
| --- | --- |
| `OPENFINANCE_MCP_URL` | Streamable-HTTP endpoint of the OF MCP server |
| `OPENFINANCE_MCP_TOKEN` | Optional bearer token |
| `OF_MOCK` | Set to `1` to force mock mode |

## Notes & next steps

- The activity ledger persists to `data/ledger.json` — swap for a real database
  (Postgres/Prisma) before production.
- Sends to addresses that are not your own wallets require a second, explicit
  confirmation (mirrors the OF safety contract for `onchain_send_token`).
- Natural next steps: Hyperliquid order placement, Polymarket trading, user auth +
  multi-tenant wallets, webhook-driven transaction status updates.
