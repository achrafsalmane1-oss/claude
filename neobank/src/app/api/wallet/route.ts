import { NextResponse } from "next/server";
import { callOF, isMockMode } from "@/lib/of/client";
import type { WalletAddresses } from "@/lib/of/types";

export async function GET() {
  try {
    const res = await callOF<{ success: boolean; data: WalletAddresses }>(
      "get_wallet_addresses",
    );
    return NextResponse.json({ ...res.data, mock: isMockMode() });
  } catch (err) {
    return NextResponse.json({ error: String(err) }, { status: 502 });
  }
}
