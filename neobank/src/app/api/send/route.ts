import { NextRequest, NextResponse } from "next/server";
import { callOF } from "@/lib/of/client";
import { addEntry } from "@/lib/ledger";
import type { WalletAddresses } from "@/lib/of/types";

/**
 * Same-chain token transfer. External recipients (not one of the user's own
 * wallets) must be explicitly confirmed: the first call returns
 * { requiresConfirmation: true } and the client re-submits with
 * confirmExternal=true after the user acknowledges the warning.
 */
export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { chainId, tokenAddress, to, amount, symbol, confirmExternal } = body as {
      chainId: string;
      tokenAddress: string;
      to: string;
      amount: string; // raw integer in smallest unit
      symbol?: string;
      confirmExternal?: boolean;
    };
    if (!chainId || !tokenAddress || !to || !amount) {
      return NextResponse.json({ error: "chainId, tokenAddress, to, amount are required" }, { status: 400 });
    }

    const wallets = await callOF<{ data: WalletAddresses }>("get_wallet_addresses");
    const self = [wallets.data.ethereum, wallets.data.solana]
      .filter(Boolean)
      .map((a) => String(a).toLowerCase());
    const isExternal = !self.includes(to.toLowerCase());

    if (isExternal && !confirmExternal) {
      return NextResponse.json({
        requiresConfirmation: true,
        warning: `EXTERNAL TRANSFER — sending ${symbol ?? "tokens"} to ${to} on chain ${chainId}. This is NOT one of your wallets. Funds cannot be recovered if the address is wrong.`,
      });
    }

    const res = await callOF<{ success: boolean; data?: { txHash?: string }; txHash?: string }>(
      "onchain_send_token",
      { chainId, tokenAddress, to, amount },
    );
    const txHash = res.data?.txHash ?? res.txHash ?? null;

    await addEntry({
      type: "send",
      chainId,
      summary: `Sent ${symbol ?? "tokens"} to ${to.slice(0, 10)}…`,
      status: "submitted",
      txHash: txHash ?? undefined,
      details: { chainId, tokenAddress, to, amount, external: isExternal },
    });
    return NextResponse.json({ txHash });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 502 });
  }
}
