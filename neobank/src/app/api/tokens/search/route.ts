import { NextRequest, NextResponse } from "next/server";
import { callOF } from "@/lib/of/client";
import type { TokenSearchResult } from "@/lib/of/types";

type RawResult = Record<string, unknown>;

function normalize(r: RawResult): TokenSearchResult {
  const token = (r.token ?? r) as Record<string, unknown>;
  return {
    address: String(token.address ?? ""),
    name: String(token.name ?? ""),
    symbol: String(token.symbol ?? ""),
    decimals: Number(token.decimals ?? 18),
    networkId: (token.networkId ?? "") as number | string,
    logo: (token.logo as string | undefined) ?? null,
    priceUSD: r.priceUSD != null ? Number(r.priceUSD) : null,
    change24: r.change24 != null ? Number(r.change24) : null,
    volume24: r.volume24 != null ? Number(r.volume24) : null,
    liquidity: r.liquidity != null ? Number(r.liquidity) : null,
    marketCap: r.marketCap != null ? Number(r.marketCap) : null,
    blueCheckmark: Boolean(token.blueCheckmark),
  };
}

export async function GET(req: NextRequest) {
  const q = req.nextUrl.searchParams.get("q")?.trim();
  if (!q) return NextResponse.json({ results: [] });
  try {
    const res = await callOF<{ count: number; results: RawResult[] }>(
      "onchain_search_tokens",
      { query: q, limit: 25 },
    );
    return NextResponse.json({ results: (res.results ?? []).map(normalize) });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 502 });
  }
}
