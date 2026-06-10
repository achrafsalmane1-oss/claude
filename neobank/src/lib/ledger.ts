import { promises as fs } from "fs";
import path from "path";
import { randomUUID } from "crypto";
import type { LedgerEntry } from "./of/types";

/**
 * Minimal append-only transaction ledger persisted to data/ledger.json.
 * Records every action initiated through the app (sends, swaps, onramps)
 * so the Activity view has history even though chains don't expose a
 * unified one. Swap for a real database before production.
 */

const LEDGER_PATH = path.join(process.cwd(), "data", "ledger.json");

async function readAll(): Promise<LedgerEntry[]> {
  try {
    const raw = await fs.readFile(LEDGER_PATH, "utf8");
    return JSON.parse(raw) as LedgerEntry[];
  } catch {
    return [];
  }
}

export async function listEntries(): Promise<LedgerEntry[]> {
  const entries = await readAll();
  return entries.sort((a, b) => b.timestamp.localeCompare(a.timestamp));
}

export async function addEntry(
  entry: Omit<LedgerEntry, "id" | "timestamp">,
): Promise<LedgerEntry> {
  const full: LedgerEntry = {
    ...entry,
    id: randomUUID(),
    timestamp: new Date().toISOString(),
  };
  const entries = await readAll();
  entries.push(full);
  await fs.mkdir(path.dirname(LEDGER_PATH), { recursive: true });
  await fs.writeFile(LEDGER_PATH, JSON.stringify(entries, null, 2));
  return full;
}
