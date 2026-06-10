"use client";

import { useState } from "react";
import { buttonCls, Card, ErrorNote, inputCls, selectCls, Spinner, useJson } from "@/components/ui";
import { chainById } from "@/lib/of/chains";
import { fmtAmount, toRawAmount } from "@/lib/format";
import type { Holding } from "@/lib/of/types";

type HoldingsRes = { holdings: Holding[] };

export default function SendPage() {
  const holdings = useJson<HoldingsRes>("/api/holdings");
  const [tokenKey, setTokenKey] = useState("");
  const [to, setTo] = useState("");
  const [amount, setAmount] = useState("");
  const [warning, setWarning] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [txHash, setTxHash] = useState<string | null>(null);

  const items = holdings.data?.holdings ?? [];
  const selected = items.find((h) => `${h.chainId}:${h.tokenAddress}` === tokenKey);

  async function submit(confirmExternal: boolean) {
    if (!selected) return;
    setBusy(true);
    setError(null);
    try {
      const res = await fetch("/api/send", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chainId: selected.chainId,
          tokenAddress: selected.tokenAddress,
          to: to.trim(),
          amount: toRawAmount(amount, selected.decimals),
          symbol: selected.symbol,
          confirmExternal,
        }),
      });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
      if (body.requiresConfirmation) {
        setWarning(body.warning);
        return;
      }
      setWarning(null);
      setTxHash(body.txHash ?? "(submitted)");
    } catch (err) {
      setError(String(err));
    } finally {
      setBusy(false);
    }
  }

  const valid = selected && to.trim().length > 20 && Number(amount) > 0;

  return (
    <div className="mx-auto flex max-w-lg flex-col gap-6">
      <h1 className="text-2xl font-semibold tracking-tight">Send</h1>
      {holdings.loading && <Spinner />}
      {holdings.error && <ErrorNote message={holdings.error} />}
      {holdings.data && (
        <Card className="flex flex-col gap-4">
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-muted">Asset</span>
            <select
              className={selectCls}
              value={tokenKey}
              onChange={(e) => setTokenKey(e.target.value)}
            >
              <option value="">Select a token…</option>
              {items.map((h) => (
                <option
                  key={`${h.chainId}:${h.tokenAddress}`}
                  value={`${h.chainId}:${h.tokenAddress}`}
                >
                  {h.symbol} on {chainById(h.chainId)?.name ?? h.chainId} — {fmtAmount(h.balance)}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-muted">Recipient address (same chain)</span>
            <input
              className={inputCls}
              placeholder="0x… or Solana address"
              value={to}
              onChange={(e) => {
                setTo(e.target.value);
                setWarning(null);
              }}
            />
          </label>
          <label className="flex flex-col gap-1.5 text-sm">
            <span className="text-muted">Amount {selected ? `(${selected.symbol})` : ""}</span>
            <input
              className={inputCls}
              placeholder="0.00"
              inputMode="decimal"
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          </label>

          {warning ? (
            <div className="flex flex-col gap-3">
              <ErrorNote message={`⚠️ ${warning}`} />
              <div className="flex gap-3">
                <button
                  className={buttonCls + " bg-negative"}
                  disabled={busy}
                  onClick={() => submit(true)}
                >
                  {busy ? "Sending…" : "Yes, send anyway"}
                </button>
                <button
                  className="rounded-xl border border-line px-5 py-2.5 text-sm"
                  onClick={() => setWarning(null)}
                >
                  Cancel
                </button>
              </div>
            </div>
          ) : (
            <button className={buttonCls} disabled={!valid || busy} onClick={() => submit(false)}>
              {busy ? "Sending…" : "Review & send"}
            </button>
          )}

          {error && <ErrorNote message={error} />}
          {txHash && (
            <div className="rounded-xl border border-positive/30 bg-positive/10 px-4 py-3 text-sm text-positive">
              Transfer submitted · tx {txHash}
            </div>
          )}
        </Card>
      )}
      <p className="text-xs text-muted">
        Same-chain transfers only. For cross-chain moves use{" "}
        <a href="/swap" className="text-accent hover:underline">
          Swap
        </a>
        , which routes through Relay.
      </p>
    </div>
  );
}
