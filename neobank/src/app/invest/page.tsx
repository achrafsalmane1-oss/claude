"use client";

import { Card, ErrorNote, SectionTitle, Spinner, useJson } from "@/components/ui";
import { fmtUsd } from "@/lib/format";

type HlSummary = {
  marginSummary?: { accountValue?: string; totalNtlPos?: string };
  withdrawable?: string;
  assetPositions?: unknown[];
};

type PmEvent = {
  id: string;
  title: string;
  volume?: number;
  markets?: { question?: string; outcomes?: string; outcomePrices?: string }[];
};

type InvestRes = {
  hyperliquid: HlSummary | null;
  mids: Record<string, string> | null;
  events: PmEvent[] | null;
};

const FEATURED_MIDS = ["BTC", "ETH", "SOL", "HYPE"];

function parsePair(json?: string): string[] {
  try {
    return JSON.parse(json ?? "[]");
  } catch {
    return [];
  }
}

export default function InvestPage() {
  const { data, error, loading } = useJson<InvestRes>("/api/invest");

  return (
    <div className="flex flex-col gap-8">
      <h1 className="text-2xl font-semibold tracking-tight">Invest</h1>
      {loading && <Spinner />}
      {error && <ErrorNote message={error} />}

      {data && (
        <>
          <section>
            <SectionTitle>Hyperliquid — perps account</SectionTitle>
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
              <Card>
                <p className="text-xs text-muted">Account value</p>
                <p className="mt-1 text-xl font-semibold">
                  {fmtUsd(Number(data.hyperliquid?.marginSummary?.accountValue ?? 0))}
                </p>
              </Card>
              <Card>
                <p className="text-xs text-muted">Open notional</p>
                <p className="mt-1 text-xl font-semibold">
                  {fmtUsd(Number(data.hyperliquid?.marginSummary?.totalNtlPos ?? 0))}
                </p>
              </Card>
              <Card>
                <p className="text-xs text-muted">Withdrawable</p>
                <p className="mt-1 text-xl font-semibold">
                  {fmtUsd(Number(data.hyperliquid?.withdrawable ?? 0))}
                </p>
              </Card>
            </div>
            {data.mids && (
              <div className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-4">
                {FEATURED_MIDS.filter((s) => data.mids?.[s]).map((s) => (
                  <Card key={s}>
                    <p className="text-xs text-muted">{s}</p>
                    <p className="mt-1 font-medium">{fmtUsd(Number(data.mids![s]))}</p>
                  </Card>
                ))}
              </div>
            )}
            <p className="mt-2 text-xs text-muted">
              Fund via USDC on Arbitrum → Hyperliquid deposit address. Positions and trading
              coming next.
            </p>
          </section>

          <section>
            <SectionTitle>Polymarket — trending predictions</SectionTitle>
            <div className="flex flex-col gap-3">
              {(data.events ?? []).map((ev) => {
                const m = ev.markets?.[0];
                const outcomes = parsePair(m?.outcomes);
                const prices = parsePair(m?.outcomePrices);
                return (
                  <Card key={ev.id} className="flex items-center justify-between gap-4">
                    <div>
                      <p className="text-sm font-medium">{ev.title}</p>
                      {ev.volume != null && (
                        <p className="mt-0.5 text-xs text-muted">
                          {fmtUsd(ev.volume)} volume
                        </p>
                      )}
                    </div>
                    <div className="flex shrink-0 gap-2">
                      {outcomes.slice(0, 2).map((o, i) => (
                        <span
                          key={o}
                          className={`rounded-lg px-3 py-1.5 text-sm font-medium ${
                            i === 0 ? "bg-positive/10 text-positive" : "bg-negative/10 text-negative"
                          }`}
                        >
                          {o} {prices[i] != null ? `${Math.round(Number(prices[i]) * 100)}¢` : ""}
                        </span>
                      ))}
                    </div>
                  </Card>
                );
              })}
              {(data.events ?? []).length === 0 && (
                <Card>
                  <p className="text-sm text-muted">No prediction markets available.</p>
                </Card>
              )}
            </div>
          </section>
        </>
      )}
    </div>
  );
}
