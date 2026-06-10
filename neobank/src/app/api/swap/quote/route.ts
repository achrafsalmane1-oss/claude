import { NextRequest, NextResponse } from "next/server";
import { callOF } from "@/lib/of/client";
import { WSOL_MINT } from "@/lib/of/chains";
import type { SwapQuote } from "@/lib/of/types";

/**
 * Routing per OF guidance:
 *   - Solana → Solana: Jupiter (onchain_jupiter_order)
 *   - everything else (EVM same-chain, any cross-chain): Relay (relay_get_quote)
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { fromChain, toChain, fromToken, toToken, amount, slippageBps } = body as {
      fromChain: string;
      toChain: string;
      fromToken: string;
      toToken: string;
      amount: string; // raw integer, smallest unit
      slippageBps?: number;
    };
    if (!fromChain || !toChain || !fromToken || !toToken || !amount) {
      return NextResponse.json({ error: "fromChain, toChain, fromToken, toToken, amount are required" }, { status: 400 });
    }

    const solanaSameChain = fromChain === "solana" && toChain === "solana";

    if (solanaSameChain) {
      const order = await callOF<Record<string, unknown>>("onchain_jupiter_order", {
        inputMint: fromToken === "native" ? WSOL_MINT : fromToken,
        outputMint: toToken === "native" ? WSOL_MINT : toToken,
        amount,
        ...(slippageBps != null ? { slippageBps } : {}),
      });
      const quote: SwapQuote = {
        provider: "jupiter",
        inAmount: String(order.inAmount ?? amount),
        outAmount: String(order.outAmount ?? "0"),
        raw: order,
      };
      return NextResponse.json(quote);
    }

    const relay = await callOF<Record<string, unknown>>("relay_get_quote", {
      originChainId: fromChain,
      destinationChainId: toChain,
      originCurrency: fromToken,
      destinationCurrency: toToken,
      amount,
      tradeType: "EXACT_INPUT",
      ...(slippageBps != null ? { slippageTolerance: String(slippageBps) } : {}),
    });
    const details = (relay.details ?? {}) as Record<string, Record<string, unknown>>;
    const quote: SwapQuote = {
      provider: "relay",
      inAmount: String(details.currencyIn?.amount ?? amount),
      outAmount: String(details.currencyOut?.amount ?? "0"),
      outAmountFormatted: details.currencyOut?.amountFormatted as string | undefined,
      rate: (details as Record<string, unknown>).rate as string | undefined,
      fees: relay.fees,
      raw: relay,
    };
    return NextResponse.json(quote);
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 502 });
  }
}
