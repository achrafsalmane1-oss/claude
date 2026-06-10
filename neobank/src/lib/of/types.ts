export type WalletAddresses = {
  ethereum: string | null;
  solana: string | null;
};

export type Holding = {
  chainId: string;
  tokenAddress: string;
  symbol: string;
  name: string;
  decimals: number;
  logo?: string | null;
  /** Raw integer balance in smallest unit, as a string. */
  rawBalance: string;
  /** Human-readable balance (rawBalance scaled by decimals). */
  balance: number;
  usdPrice?: number | null;
  usdValue?: number | null;
};

export type TokenSearchResult = {
  address: string;
  name: string;
  symbol: string;
  decimals: number;
  networkId: number | string;
  logo?: string | null;
  priceUSD?: number | null;
  change24?: number | null;
  volume24?: number | null;
  liquidity?: number | null;
  marketCap?: number | null;
  blueCheckmark?: boolean;
};

export type SwapQuote = {
  provider: "relay" | "jupiter";
  inAmount: string;
  outAmount: string;
  outAmountFormatted?: string;
  rate?: string;
  fees?: unknown;
  raw: unknown;
};

export type LedgerEntry = {
  id: string;
  type: "send" | "swap" | "onramp";
  timestamp: string;
  chainId: string;
  summary: string;
  status: "submitted" | "completed" | "failed";
  txHash?: string;
  details: Record<string, unknown>;
};
