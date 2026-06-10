/**
 * Mock responses for OF tools so the app runs with zero configuration.
 * Shapes mirror the real OpenFinance MCP server responses.
 */

const DEMO_EVM = "0x1111111111111111111111111111111111111111";
const DEMO_SOL = "DemoSo1anaWa11etAddre55xxxxxxxxxxxxxxxxxxxx";

const HOLDINGS: Record<string, unknown[]> = {
  "1": [
    bal("0x0000000000000000000000000000000000000000", "Ethereum", "ETH", 18, "412503100000000000", 3120.5),
    bal("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "USD Coin", "USDC", 6, "1250000000", 1.0),
  ],
  "137": [
    bal("0x0000000000000000000000000000000000000000", "Polygon", "POL", 18, "85000000000000000000", 0.42),
    bal("0x3c499c542cef5e3811e1192ce70d8cc03d5c3359", "USD Coin", "USDC", 6, "240000000", 1.0),
  ],
  "8453": [
    bal("0x0000000000000000000000000000000000000000", "Ethereum", "ETH", 18, "150000000000000000", 3120.5),
    bal("0x833589fcd6edb6e08f4c7c32d4f71b54bda02913", "USD Coin", "USDC", 6, "500000000", 1.0),
  ],
  "42161": [],
  "10": [],
  solana: [
    bal("native", "Solana", "SOL", 9, "2500000000", 168.3),
    bal("EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v", "USD Coin", "USDC", 6, "320000000", 1.0),
  ],
};

function bal(
  address: string,
  name: string,
  symbol: string,
  decimals: number,
  balance: string,
  usdPrice: number,
) {
  const human = Number(balance) / 10 ** decimals;
  return {
    tokenAddress: address,
    name,
    symbol,
    decimals,
    balance,
    usdPrice,
    usdValue: human * usdPrice,
    logo: null,
  };
}

const SEARCH_RESULTS = [
  searchHit("0xa0b86991c6218b36c1d19d4a2e9eb0ce3606eb48", "USD Coin", "USDC", 6, 1, 1.0, 0.01, 5_400_000_000),
  searchHit("0x0000000000000000000000000000000000000000", "Ethereum", "ETH", 18, 1, 3120.5, 2.4, 380_000_000_000),
  searchHit("So11111111111111111111111111111111111111112", "Wrapped SOL", "SOL", 9, "solana", 168.3, -1.1, 78_000_000_000),
  searchHit("0x6982508145454ce325ddbe47a25d4ec3d2311933", "Pepe", "PEPE", 18, 1, 0.0000112, 5.6, 4_700_000_000),
];

function searchHit(
  address: string,
  name: string,
  symbol: string,
  decimals: number,
  networkId: number | string,
  priceUSD: number,
  change24: number,
  marketCap: number,
) {
  return {
    token: { id: `${networkId}:${address}`, address, name, symbol, decimals, networkId, logo: null, blueCheckmark: true },
    priceUSD,
    change24,
    volume24: marketCap / 50,
    liquidity: marketCap / 200,
    marketCap,
  };
}

export async function mockCall(
  tool: string,
  args: Record<string, unknown>,
): Promise<unknown> {
  switch (tool) {
    case "get_wallet_addresses":
      return { success: true, data: { ethereum: DEMO_EVM, solana: DEMO_SOL } };

    case "onchain_get_address_holdings": {
      const chainId = String(args.chainId ?? "1");
      return { success: true, data: { balances: HOLDINGS[chainId] ?? [] } };
    }

    case "onchain_search_tokens": {
      const q = String(args.query ?? "").toLowerCase();
      const results = SEARCH_RESULTS.filter(
        (r) =>
          r.token.symbol.toLowerCase().includes(q) ||
          r.token.name.toLowerCase().includes(q) ||
          r.token.address.toLowerCase() === q,
      );
      return { count: results.length, results };
    }

    case "onchain_get_token_usd_price":
      return { usdPrice: 1.0, symbol: "USDC", name: "USD Coin", decimals: 6 };

    case "get_onramp_url":
      return {
        provider: String(args.baseCurrency) === "inr" ? "onramp.money" : "moonpay",
        url: "https://buy.moonpay.com/?demo=1&apiKey=mock",
      };

    case "onchain_send_token":
      return {
        success: true,
        data: { txHash: "0xmocked" + Math.random().toString(16).slice(2, 10) },
      };

    case "relay_get_quote":
      return {
        details: {
          currencyIn: { amount: args.amount, amountFormatted: "100.0", amountUsd: "100.00" },
          currencyOut: { amount: "99500000", amountFormatted: "99.5", amountUsd: "99.50" },
          rate: "0.995",
        },
        fees: { gas: { amountUsd: "0.02" }, relayer: { amountUsd: "0.30" } },
        steps: [],
      };

    case "relay_execute":
      return { success: true, txHash: "0xmockedrelay" + Math.random().toString(16).slice(2, 8) };

    case "onchain_jupiter_order":
      return {
        inputMint: args.inputMint,
        outputMint: args.outputMint,
        inAmount: args.amount,
        outAmount: "99400000",
        priceImpactPct: "0.01",
        requestId: "mock-request-id",
        transaction: "bW9ja1Vuc2lnbmVkVHJhbnNhY3Rpb24=",
      };

    case "onchain_jupiter_execute":
      return { signature: "mockedSolanaSignature", status: "Success" };

    case "hyperliquid": {
      const action = String(args.action);
      if (action === "get_account_summary") {
        return {
          marginSummary: { accountValue: "0.0", totalNtlPos: "0.0", totalRawUsd: "0.0" },
          withdrawable: "0.0",
          assetPositions: [],
        };
      }
      if (action === "get_all_mids") {
        return { BTC: "104250.0", ETH: "3120.5", SOL: "168.3", HYPE: "38.2" };
      }
      return {};
    }

    case "polymarket": {
      const action = String(args.action);
      if (action === "get_events") {
        return [
          {
            id: "demo-1",
            title: "Will the Fed cut rates in July 2026?",
            volume: 12_400_000,
            markets: [{ question: "Fed cut in July?", outcomePrices: '["0.62","0.38"]', outcomes: '["Yes","No"]' }],
          },
          {
            id: "demo-2",
            title: "Bitcoin above $120k by end of Q3?",
            volume: 8_100_000,
            markets: [{ question: "BTC > $120k?", outcomePrices: '["0.41","0.59"]', outcomes: '["Yes","No"]' }],
          },
        ];
      }
      if (action === "get_user_positions") return [];
      return {};
    }

    default:
      throw new Error(`No mock implemented for OF tool: ${tool}`);
  }
}
