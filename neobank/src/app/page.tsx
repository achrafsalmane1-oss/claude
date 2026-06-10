"use client";

import Link from "next/link";
import { Card, ErrorNote, MockBadge, SectionTitle, Spinner, useJson } from "@/components/ui";
import { CHAINS, chainById } from "@/lib/of/chains";
import { fmtAmount, fmtUsd, shortAddr } from "@/lib/format";
import type { Holding, WalletAddresses } from "@/lib/of/types";

type WalletRes = WalletAddresses & { mock?: boolean };
type HoldingsRes = { holdings: Holding[]; totalUsd: number };

const ACTIONS = [
  { href: "/add-funds", label: "Add funds", desc: "Buy crypto with fiat" },
  { href: "/send", label: "Send", desc: "Transfer to any address" },
  { href: "/swap", label: "Swap", desc: "Same-chain & cross-chain" },
  { href: "/invest", label: "Invest", desc: "Perps & predictions" },
];

export default function Dashboard() {
  const wallet = useJson<WalletRes>("/api/wallet");
  const holdings = useJson<HoldingsRes>("/api/holdings");

  const byChain = new Map<string, Holding[]>();
  for (const h of holdings.data?.holdings ?? []) {
    byChain.set(h.chainId, [...(byChain.get(h.chainId) ?? []), h]);
  }

  return (
    <div className="flex flex-col gap-8">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Home</h1>
          <p className="mt-1 text-sm text-muted">
            EVM {shortAddr(wallet.data?.ethereum)} · Solana {shortAddr(wallet.data?.solana)}
          </p>
        </div>
        {wallet.data?.mock && <MockBadge />}
      </header>

      <Card className="bg-gradient-to-br from-surface to-surface-2">
        <p className="text-sm text-muted">Total balance</p>
        <p className="mt-1 text-4xl font-semibold tracking-tight">
          {holdings.loading ? "…" : fmtUsd(holdings.data?.totalUsd ?? 0)}
        </p>
        <p className="mt-2 text-xs text-muted">
          Across {CHAINS.length} chains · powered by OpenFinance
        </p>
      </Card>

      <section>
        <SectionTitle>Quick actions</SectionTitle>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
          {ACTIONS.map((a) => (
            <Link key={a.href} href={a.href}>
              <Card className="h-full transition-colors hover:border-accent">
                <p className="font-medium">{a.label}</p>
                <p className="mt-1 text-xs text-muted">{a.desc}</p>
              </Card>
            </Link>
          ))}
        </div>
      </section>

      <section>
        <SectionTitle>Holdings</SectionTitle>
        {holdings.error && <ErrorNote message={holdings.error} />}
        {holdings.loading && <Spinner />}
        {holdings.data && holdings.data.holdings.length === 0 && (
          <Card>
            <p className="text-sm text-muted">
              No holdings yet.{" "}
              <Link href="/add-funds" className="text-accent hover:underline">
                Add funds
              </Link>{" "}
              to get started.
            </p>
          </Card>
        )}
        <div className="flex flex-col gap-4">
          {[...byChain.entries()].map(([chainId, items]) => {
            const chain = chainById(chainId);
            return (
              <Card key={chainId}>
                <div className="mb-3 flex items-center gap-2">
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ background: chain?.color ?? "#888" }}
                  />
                  <span className="text-sm font-medium">{chain?.name ?? chainId}</span>
                </div>
                <ul className="divide-y divide-line">
                  {items.map((h) => (
                    <li
                      key={`${h.chainId}:${h.tokenAddress}`}
                      className="flex items-center justify-between py-2.5"
                    >
                      <div>
                        <p className="text-sm font-medium">{h.symbol}</p>
                        <p className="text-xs text-muted">{h.name}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-sm">{fmtAmount(h.balance)}</p>
                        <p className="text-xs text-muted">{fmtUsd(h.usdValue)}</p>
                      </div>
                    </li>
                  ))}
                </ul>
              </Card>
            );
          })}
        </div>
      </section>
    </div>
  );
}
