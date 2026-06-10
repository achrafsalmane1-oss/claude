"use client";

import { useState } from "react";
import { buttonCls, Card, ErrorNote, inputCls, Spinner } from "@/components/ui";
import { fmtUsd } from "@/lib/format";
import type { TokenSearchResult } from "@/lib/of/types";

const DEX_SLUGS: Record<string, string> = {
  "1": "ethereum",
  "137": "polygon",
  "8453": "base",
  "42161": "arbitrum",
  "10": "optimism",
  "56": "bsc",
  "1399811149": "solana",
};

export default function MarketsPage() {
  const [q, setQ] = useState("");
  const [results, setResults] = useState<TokenSearchResult[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function search() {
    if (!q.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch(`/api/tokens/search?q=${encodeURIComponent(q)}`);
      const body = await res.json();
      if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
      setResults(body.results as TokenSearchResult[]);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Markets</h1>
      <div className="flex gap-2">
        <input
          className={inputCls}
          placeholder="Search any token across 200+ chains — PEPE, wrapped bitcoin, 0x…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && search()}
        />
        <button className={buttonCls} onClick={search} disabled={busy}>
          Search
        </button>
      </div>
      {busy && <Spinner />}
      {error && <ErrorNote message={error} />}
      {results && results.length === 0 && (
        <Card>
          <p className="text-sm text-muted">No tokens found for “{q}”.</p>
        </Card>
      )}
      {results && results.length > 0 && (
        <Card className="overflow-x-auto p-0">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-line text-left text-xs uppercase tracking-wider text-muted">
                <th className="px-5 py-3 font-medium">Token</th>
                <th className="px-5 py-3 font-medium">Price</th>
                <th className="px-5 py-3 font-medium">24h</th>
                <th className="px-5 py-3 font-medium">Market cap</th>
                <th className="px-5 py-3 font-medium">Verify</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {results.map((r) => {
                const slug = DEX_SLUGS[String(r.networkId)];
                return (
                  <tr key={`${r.networkId}:${r.address}`}>
                    <td className="px-5 py-3">
                      <span className="font-medium">{r.symbol}</span>{" "}
                      {r.blueCheckmark && <span title="verified">✔</span>}
                      <span className="block text-xs text-muted">{r.name}</span>
                    </td>
                    <td className="px-5 py-3">{fmtUsd(r.priceUSD)}</td>
                    <td className={`px-5 py-3 ${(r.change24 ?? 0) >= 0 ? "text-positive" : "text-negative"}`}>
                      {r.change24 != null ? `${r.change24 > 0 ? "+" : ""}${r.change24.toFixed(2)}%` : "—"}
                    </td>
                    <td className="px-5 py-3">{fmtUsd(r.marketCap)}</td>
                    <td className="px-5 py-3">
                      {slug ? (
                        <a
                          className="text-accent hover:underline"
                          href={`https://dexscreener.com/${slug}/${r.address.toLowerCase()}`}
                          target="_blank"
                          rel="noopener noreferrer"
                        >
                          DexScreener ↗
                        </a>
                      ) : (
                        <span className="text-muted">—</span>
                      )}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
