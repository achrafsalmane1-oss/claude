"use client";

import { useEffect, useState } from "react";

export function Card({
  children,
  className = "",
}: {
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={`rounded-2xl border border-line bg-surface p-5 ${className}`}>
      {children}
    </div>
  );
}

export function SectionTitle({ children }: { children: React.ReactNode }) {
  return (
    <h2 className="mb-3 text-sm font-medium uppercase tracking-wider text-muted">
      {children}
    </h2>
  );
}

export function Spinner() {
  return (
    <div className="flex justify-center py-10">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-line border-t-accent" />
    </div>
  );
}

export function ErrorNote({ message }: { message: string }) {
  return (
    <div className="rounded-xl border border-negative/30 bg-negative/10 px-4 py-3 text-sm text-negative">
      {message}
    </div>
  );
}

export function MockBadge() {
  return (
    <span className="rounded-full border border-line bg-surface-2 px-2.5 py-1 text-xs text-muted">
      demo data — set OPENFINANCE_MCP_URL for live mode
    </span>
  );
}

export const inputCls =
  "w-full rounded-xl border border-line bg-surface-2 px-4 py-2.5 text-sm outline-none placeholder:text-muted focus:border-accent";

export const buttonCls =
  "rounded-xl bg-accent px-5 py-2.5 text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40";

export const selectCls =
  "rounded-xl border border-line bg-surface-2 px-3 py-2.5 text-sm outline-none focus:border-accent";

export function useJson<T>(url: string | null): {
  data: T | null;
  error: string | null;
  loading: boolean;
  reload: () => void;
} {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(Boolean(url));
  const [tick, setTick] = useState(0);

  useEffect(() => {
    if (!url) return;
    let cancelled = false;
    fetch(url)
      .then(async (res) => {
        const body = await res.json();
        if (cancelled) return;
        if (!res.ok) throw new Error(body.error ?? `HTTP ${res.status}`);
        setData(body as T);
      })
      .catch((err) => !cancelled && setError(String(err)))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [url, tick]);

  const reload = () => {
    setLoading(true);
    setError(null);
    setTick((t) => t + 1);
  };
  return { data, error, loading, reload };
}
