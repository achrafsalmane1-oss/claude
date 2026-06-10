import { NextResponse } from "next/server";
import { callOF } from "@/lib/of/client";
import { CHAINS } from "@/lib/of/chains";
import type { Holding, WalletAddresses } from "@/lib/of/types";

type RawBalance = Record<string, unknown>;

function pick(b: RawBalance, keys: string[]): unknown {
  for (const k of keys) if (b[k] != null) return b[k];
  return undefined;
}

function normalize(chainId: string, b: RawBalance): Holding | null {
  const tokenAddress = String(pick(b, ["tokenAddress", "token_address", "address", "mint"]) ?? "native");
  const decimals = Number(pick(b, ["decimals"]) ?? 18);
  const rawBalance = String(pick(b, ["balance", "rawBalance", "amount"]) ?? "0");
  const balance = Number(pick(b, ["balanceFormatted", "uiAmount"]) ?? Number(rawBalance) / 10 ** decimals);
  if (!balance) return null;
  const usdPrice = pick(b, ["usdPrice", "priceUsd", "price"]) as number | undefined;
  const usdValue = (pick(b, ["usdValue", "valueUsd"]) as number | undefined) ?? (usdPrice != null ? balance * usdPrice : null);
  return {
    chainId,
    tokenAddress,
    symbol: String(pick(b, ["symbol"]) ?? "?"),
    name: String(pick(b, ["name"]) ?? "Unknown token"),
    decimals,
    logo: (pick(b, ["logo", "logoURI", "thumbnail"]) as string | undefined) ?? null,
    rawBalance,
    balance,
    usdPrice: usdPrice ?? null,
    usdValue: usdValue ?? null,
  };
}

export async function GET() {
  try {
    const wallets = await callOF<{ data: WalletAddresses }>("get_wallet_addresses");
    const { ethereum, solana } = wallets.data;

    const perChain = await Promise.all(
      CHAINS.map(async (chain) => {
        const address = chain.kind === "solana" ? solana : ethereum;
        if (!address) return [] as Holding[];
        try {
          const res = await callOF<{ data: { balances: RawBalance[] } }>(
            "onchain_get_address_holdings",
            {
              chainId: chain.id,
              walletAddress: address,
              includePrice: true,
              includeMetadata: true,
            },
          );
          return (res.data?.balances ?? [])
            .map((b) => normalize(chain.id, b))
            .filter((h): h is Holding => h !== null);
        } catch {
          return [] as Holding[];
        }
      }),
    );

    const holdings = perChain.flat();
    const totalUsd = holdings.reduce((sum, h) => sum + (h.usdValue ?? 0), 0);
    return NextResponse.json({ holdings, totalUsd });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 502 });
  }
}
