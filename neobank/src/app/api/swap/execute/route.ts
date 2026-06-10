import { NextRequest, NextResponse } from "next/server";
import { callOF } from "@/lib/of/client";
import { addEntry } from "@/lib/ledger";
import { WSOL_MINT } from "@/lib/of/chains";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { provider, fromChain, toChain, fromToken, toToken, amount, slippageBps, jupiterOrder, summary } = body as {
      provider: "relay" | "jupiter";
      fromChain: string;
      toChain: string;
      fromToken: string;
      toToken: string;
      amount: string;
      slippageBps?: number;
      /** raw onchain_jupiter_order response (needs transaction + requestId) */
      jupiterOrder?: { transaction?: string; requestId?: string };
      summary?: string;
    };

    let result: Record<string, unknown>;
    if (provider === "jupiter") {
      let order = jupiterOrder;
      if (!order?.transaction || !order?.requestId) {
        // Re-fetch a fresh order if the client didn't carry one over.
        order = await callOF<{ transaction?: string; requestId?: string }>(
          "onchain_jupiter_order",
          {
            inputMint: fromToken === "native" ? WSOL_MINT : fromToken,
            outputMint: toToken === "native" ? WSOL_MINT : toToken,
            amount,
            ...(slippageBps != null ? { slippageBps } : {}),
          },
        );
      }
      result = await callOF<Record<string, unknown>>("onchain_jupiter_execute", {
        transaction: order.transaction,
        requestId: order.requestId,
      });
    } else {
      result = await callOF<Record<string, unknown>>("relay_execute", {
        originChainId: fromChain,
        destinationChainId: toChain,
        originCurrency: fromToken,
        destinationCurrency: toToken,
        amount,
        tradeType: "EXACT_INPUT",
        ...(slippageBps != null ? { slippageTolerance: String(slippageBps) } : {}),
      });
    }

    const txHash = String(result.txHash ?? result.signature ?? "");
    await addEntry({
      type: "swap",
      chainId: fromChain,
      summary: summary ?? `Swap on chain ${fromChain} → ${toChain}`,
      status: "submitted",
      txHash: txHash || undefined,
      details: { provider, fromChain, toChain, fromToken, toToken, amount },
    });
    return NextResponse.json({ txHash, result });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 502 });
  }
}
