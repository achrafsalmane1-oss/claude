"use client";

import { useState } from "react";
import { buttonCls, Card, ErrorNote, inputCls, selectCls, Spinner, useJson } from "@/components/ui";
import { CHAINS, chainById, NATIVE_TOKEN_EVM } from "@/lib/of/chains";
import { fmtAmount, fromRawAmount, toRawAmount } from "@/lib/format";
import type { Holding, SwapQuote, TokenSearchResult } from "@/lib/of/types";

type HoldingsRes = { holdings: Holding[] };

export default function SwapPage() {
  const holdings = useJson<HoldingsRes>("/api/holdings");
  const [fromKey, setFromKey] = useState("");
  const [toChain, setToChain] = useState("8453");
  const [toQuery, setToQuery] = useState("");
  const [toToken, setToToken] = useState<TokenSearchResult | null>(null);
  const [searchResults, setSearchResults] = useState<TokenSearchResult[]>([]);
  const [amount, setAmount] = useState("");
  const [quote, setQuote] = useState<SwapQuote | null>(null);
  const [busy, setBusy] = useState<"search" | "quote" | "execute" | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [done, setDone] = useState<string | null>(null);

  const items = holdings.data?.holdings ?? [];
  const from = items.find((h) => `${h.chainId}:${h.tokenAddress}` === fromKey);

  async function search() {
    if (!toQuery.trim()) return;
    setBusy("search");
    setError(null);
    try {
      const res = await fetch(`/api/tokens/search?q=${encodeURIComponent(toQuery)}`);
      const body = await res.json();
      if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
      const wanted = toChain === "solana" ? "1399811149" : toChain;
      const results = (body.results as TokenSearchResult[]).filter(
        (r) => String(r.networkId) === wanted || toChain === "solana",
      );
      setSearchResults(results.slice(0, 6));
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(null);
    }
  }

  async function getQuote() {
    if (!from || !toToken || !Number(amount)) return;
    setBusy("quote");
    setError(null);
    setDone(null);
    try {
      const res = await fetch("/api/swap/quote", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          fromChain: from.chainId,
          toChain,
          fromToken:
            from.tokenAddress === "native" && from.chainId !== "solana"
              ? NATIVE_TOKEN_EVM
              : from.tokenAddress,
          toToken: toToken.address,
          amount: toRawAmount(amount, from.decimals),
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
      setQuote(body as SwapQuote);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(null);
    }
  }

  async function execute() {
    if (!from || !toToken || !quote) return;
    setBusy("execute");
    setError(null);
    try {
      const res = await fetch("/api/swap/execute", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: quote.provider,
          fromChain: from.chainId,
          toChain,
          fromToken:
            from.tokenAddress === "native" && from.chainId !== "solana"
              ? NATIVE_TOKEN_EVM
              : from.tokenAddress,
          toToken: toToken.address,
          amount: toRawAmount(amount, from.decimals),
          jupiterOrder: quote.provider === "jupiter" ? quote.raw : undefined,
          summary: `Swap ${amount} ${from.symbol} → ${toToken.symbol}`,
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
      setDone(body.txHash || "(submitted)");
      setQuote(null);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(null);
    }
  }

  const outAmount =
    quote && toToken ? fromRawAmount(quote.outAmount, toToken.decimals) : null;

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Swap</h1>
      {holdings.loading && <Spinner />}
      {holdings.error && <ErrorNote message={holdings.error} />}
      {holdings.data && (
        <Card className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-muted">You pay</span>
            <select className={selectCls} value={fromKey} onChange={(e) => { setFromKey(e.target.value); setQuote(null); }}>
              <option value="">Select a token…</option>
              {items.map((h) => (
                <option key={`${h.chainId}:${h.tokenAddress}`} value={`${h.chainId}:${h.tokenAddress}`}>
                  {h.symbol} on {chainById(h.chainId)?.name ?? h.chainId} — {fmtAmount(h.balance)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-muted">Amount {from ? `(${from.symbol})` : ""}</span>
            <input className={inputCls} placeholder="0.00" inputMode="decimal" value={amount}
              onChange={(e) => { setAmount(e.target.value); setQuote(null); }} />
          </label>

          <div className="flex flex-col gap-1.5 text-sm">
            <span className="text-muted">You receive — on</span>
            <select className={selectCls} value={toChain} onChange={(e) => { setToChain(e.target.value); setToToken(null); setSearchResults([]); setQuote(null); }}>
              {CHAINS.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
            <div className="mt-1 flex gap-2">
              <input className={inputCls} placeholder="Search token (USDC, ETH, PEPE…)" value={toQuery}
                onChange={(e) => setToQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && search()} />
              <button className={buttonCls} onClick={search} disabled={busy === "search"}>
                {busy === "search" ? "…" : "Find"}
              </button>
            </div>
            {searchResults.length > 0 && !toToken && (
              <ul className="mt-1 divide-y divide-line rounded-xl border border-line">
                {searchResults.map((r) => (
                  <li key={`${r.networkId}:${r.address}`}>
                    <button
                      className="flex w-full items-center justify-between px-4 py-2.5 text-left hover:bg-surface-2"
                      onClick={() => { setToToken(r); setQuote(null); }}
                    >
                      <span>
                        {r.symbol} <span className="text-xs text-muted">{r.name}</span>
                      </span>
                      <span className="text-xs text-muted">
                        {r.priceUSD != null ? `$${r.priceUSD}` : ""}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
            {toToken && (
              <div className="mt-1 flex items-center justify-between rounded-xl border border-line bg-surface-2 px-4 py-2.5">
                <span className="text-sm">{toToken.symbol} — {toToken.name}</span>
                <button className="text-xs text-muted hover:text-foreground" onClick={() => setToToken(null)}>
                  change
                </button>
              </div>
            )}
          </div>

          {!quote ? (
            <button className={buttonCls} disabled={!from || !toToken || !Number(amount) || busy === "quote"} onClick={getQuote}>
              {busy === "quote" ? "Fetching quote…" : "Get quote"}
            </button>
          ) : (
            <div className="flex flex-col gap-3">
              <div className="rounded-xl border border-line bg-surface-2 px-4 py-3 text-sm">
                <p>
                  Estimated out:{" "}
                  <span className="font-medium">
                    {quote.outAmountFormatted ?? (outAmount != null ? fmtAmount(outAmount) : quote.outAmount)}{" "}
                    {toToken?.symbol}
                  </span>
                </p>
                <p className="mt-1 text-xs text-muted">
                  Route: {quote.provider === "jupiter" ? "Jupiter (Solana)" : "Relay"}
                </p>
              </div>
              <button className={buttonCls} disabled={busy === "execute"} onClick={execute}>
                {busy === "execute" ? "Executing…" : "Confirm swap"}
              </button>
            </div>
          )}

          {error && <ErrorNote message={error} />}
          {done && (
            <div className="rounded-xl border border-positive/30 bg-positive/10 px-4 py-3 text-sm text-positive">
              Swap submitted · tx {done}
            </div>
          )}
        </Card>
      )}
      <p className="text-xs text-muted">
        Solana↔Solana swaps route through Jupiter; everything else (same-chain EVM and all
        cross-chain pairs) routes through Relay.
      </p>
    </div>
  );
}
