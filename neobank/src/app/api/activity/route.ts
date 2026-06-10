import { NextResponse } from "next/server";
import { listEntries } from "@/lib/ledger";

export async function GET() {
  return NextResponse.json({ entries: await listEntries() });
}
