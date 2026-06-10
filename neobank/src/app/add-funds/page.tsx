"use client";

import { useState } from "react";
import { buttonCls, Card, ErrorNote, inputCls, selectCls } from "@/components/ui";

const FIAT = ["usd", "eur", "gbp", "inr", "aed", "php"];
const COINS = ["usdc", "usdt", "eth", "sol", "btc"];
const CHAIN_SLUGS = ["ethereum", "polygon", "base", "arbitrum", "optimism", "bsc", "solana"];

export default function AddFundsPage() {
  const [baseCurrency, setBaseCurrency] = useState("usd");
  const [amount, setAmount] = useState("100");
  const [currency, setCurrency] = useState("usdc");
  const [chain, setChain] = useState("polygon");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<{ provider: string; url: string } | null>(null);

  async function submit() {
    setBusy(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch("/api/onramp", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ baseCurrency, amount: Number(amount), currency, chain }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
      setResult(body);
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Add funds</h1>
      <Card className="flex flex-col gap-4">
        <div className="grid grid-cols-2 gap-3">
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-muted">You pay with</span>
            <select className={selectCls} value={baseCurrency} onChange={(e) => setBaseCurrency(e.target.value)}>
              {FIAT.map((f) => (
                <option key={f} value={f}>{f.toUpperCase()}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-muted">Amount</span>
            <input className={inputCls} inputMode="decimal" value={amount} onChange={(e) => setAmount(e.target.value)} />
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-muted">You receive</span>
            <select className={selectCls} value={currency} onChange={(e) => setCurrency(e.target.value)}>
              {COINS.map((c) => (
                <option key={c} value={c}>{c.toUpperCase()}</option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-muted">On chain</span>
            <select className={selectCls} value={chain} onChange={(e) => setChain(e.target.value)}>
              {CHAIN_SLUGS.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
          </label>
        </div>
        <button className={buttonCls} disabled={busy || !Number(amount)} onClick={submit}>
          {busy ? "Preparing checkout…" : "Continue to checkout"}
        </button>
        {error && <ErrorNote message={error} />}
        {result && (
          <div className="rounded-xl border border-positive/30 bg-positive/10 px-4 py-3 text-sm">
            <p className="text-positive">Checkout ready via {result.provider}.</p>
            <a
              href={result.url}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 inline-block break-all text-accent hover:underline"
            >
              Open secure payment page ↗
            </a>
          </div>
        )}
      </Card>
      <p className="text-xs text-muted">
        INR payments route through Onramp.money (UPI/IMPS); other currencies use Moonpay.
        Funds land directly in your OpenBank wallet for the selected chain. Note: INR supports
        USDC only on Polygon or BSC.
      </p>
    </div>
  );
}
