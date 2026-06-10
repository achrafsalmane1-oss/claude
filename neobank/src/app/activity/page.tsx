"use client";

import { Card, ErrorNote, Spinner, useJson } from "@/components/ui";
import { chainById } from "@/lib/of/chains";
import type { LedgerEntry } from "@/lib/of/types";

type ActivityRes = { entries: LedgerEntry[] };

const TYPE_ICONS: Record<LedgerEntry["type"], string> = {
  send: "↗",
  swap: "⇄",
  onramp: "＋",
};

export default function ActivityPage() {
  const { data, error, loading } = useJson<ActivityRes>("/api/activity");

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Activity</h1>
      {loading && <Spinner />}
      {error && <ErrorNote message={error} />}
      {data && data.entries.length === 0 && (
        <Card>
          <p className="text-sm text-muted">
            No activity yet. Sends, swaps, and deposits made through OpenBank will show up here.
          </p>
        </Card>
      )}
      {data && data.entries.length > 0 && (
        <Card className="p-0">
          <ul className="divide-y divide-line">
            {data.entries.map((e) => (
              <li key={e.id} className="flex items-center gap-4 px-5 py-3.5">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-accent-soft text-accent">
                  {TYPE_ICONS[e.type]}
                </span>
                <div className="min-w-0 flex-1">
                  <p className="truncate text-sm font-medium">{e.summary}</p>
                  <p className="text-xs text-muted">
                    {new Date(e.timestamp).toLocaleString()} ·{" "}
                    {chainById(e.chainId)?.name ?? e.chainId}
                    {e.txHash ? ` · tx ${e.txHash.slice(0, 14)}…` : ""}
                  </p>
                </div>
                <span
                  className={`rounded-full px-2.5 py-1 text-xs ${
                    e.status === "failed"
                      ? "bg-negative/10 text-negative"
                      : "bg-positive/10 text-positive"
                  }`}
                >
                  {e.status}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      )}
    </div>
  );
}
