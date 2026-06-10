import { NextRequest, NextResponse } from "next/server";
import { callOF } from "@/lib/of/client";
import { addEntry } from "@/lib/ledger";

export async function POST(req: NextRequest) {
  try {
    const body = await req.json();
    const { baseCurrency = "usd", amount, currency = "usdc", chain } = body as {
      baseCurrency?: string;
      amount?: number;
      currency?: string;
      chain?: string;
    };
    if (!amount || amount <= 0) {
      return NextResponse.json({ error: "amount must be > 0" }, { status: 400 });
    }
    const res = await callOF<{ provider: string; url: string }>("get_onramp_url", {
      baseCurrency: baseCurrency.toLowerCase(),
      amount,
      currency: currency.toLowerCase(),
      ...(chain ? { chain } : {}),
    });
    await addEntry({
      type: "onramp",
      chainId: chain ?? "evm",
      summary: `Add funds: ${amount} ${baseCurrency.toUpperCase()} → ${currency.toUpperCase()}`,
      status: "submitted",
      details: { provider: res.provider, baseCurrency, amount, currency, chain },
    });
    return NextResponse.json(res);
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 502 });
  }
}
