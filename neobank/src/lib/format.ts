export function fmtUsd(n: number | null | undefined): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: n < 1 && n > 0 ? 6 : 2,
  });
}

export function fmtAmount(n: number | null | undefined, maxDigits = 6): string {
  if (n == null || Number.isNaN(n)) return "—";
  return n.toLocaleString("en-US", { maximumFractionDigits: maxDigits });
}

export function shortAddr(addr: string | null | undefined): string {
  if (!addr) return "—";
  return addr.length > 12 ? `${addr.slice(0, 6)}…${addr.slice(-4)}` : addr;
}

/** Scale a decimal string amount to the token's smallest unit (integer string). */
export function toRawAmount(amount: string, decimals: number): string {
  const [whole = "0", frac = ""] = amount.trim().split(".");
  const fracPadded = (frac + "0".repeat(decimals)).slice(0, decimals);
  const raw = BigInt(whole || "0") * BigInt(10) ** BigInt(decimals) + BigInt(fracPadded || "0");
  return raw.toString();
}

export function fromRawAmount(raw: string, decimals: number): number {
  return Number(raw) / 10 ** decimals;
}
