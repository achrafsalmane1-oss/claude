export type ChainInfo = {
  id: string; // "1", "137", "solana"
  name: string;
  shortName: string;
  nativeSymbol: string;
  kind: "evm" | "solana";
  color: string;
  onrampSlug?: string; // slug accepted by get_onramp_url
};

export const CHAINS: ChainInfo[] = [
  { id: "1", name: "Ethereum", shortName: "ETH", nativeSymbol: "ETH", kind: "evm", color: "#627eea", onrampSlug: "ethereum" },
  { id: "137", name: "Polygon", shortName: "POL", nativeSymbol: "POL", kind: "evm", color: "#8247e5", onrampSlug: "polygon" },
  { id: "8453", name: "Base", shortName: "BASE", nativeSymbol: "ETH", kind: "evm", color: "#0052ff", onrampSlug: "base" },
  { id: "42161", name: "Arbitrum", shortName: "ARB", nativeSymbol: "ETH", kind: "evm", color: "#28a0f0", onrampSlug: "arbitrum" },
  { id: "10", name: "Optimism", shortName: "OP", nativeSymbol: "ETH", kind: "evm", color: "#ff0420", onrampSlug: "optimism" },
  { id: "solana", name: "Solana", shortName: "SOL", nativeSymbol: "SOL", kind: "solana", color: "#9945ff", onrampSlug: "solana" },
];

export const NATIVE_TOKEN_EVM = "0x0000000000000000000000000000000000000000";
export const WSOL_MINT = "So11111111111111111111111111111111111111112";

export function chainById(id: string): ChainInfo | undefined {
  return CHAINS.find((c) => c.id === id);
}
