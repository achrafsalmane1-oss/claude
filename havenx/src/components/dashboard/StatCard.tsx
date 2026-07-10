import { IconTrendUp, IconTrendDown } from "@/components/icons";
import { formatNumber } from "@/lib/format";

export default function StatCard({
  label,
  value,
  delta,
  hint,
}: {
  label: string;
  value: number;
  delta?: number;
  hint?: string;
}) {
  const up = (delta ?? 0) >= 0;
  return (
    <div className="rounded-2xl border border-line bg-white p-5">
      <div className="text-[13px] text-ink-soft">{label}</div>
      <div className="mt-2 flex items-end justify-between gap-2">
        <span className="display text-[34px] leading-none text-ink">
          {formatNumber(value)}
        </span>
        {delta !== undefined && (
          <span
            className={`flex items-center gap-1 pb-0.5 text-[12.5px] font-medium ${
              up ? "text-rise" : "text-fall"
            }`}
          >
            {up ? "+" : ""}
            {delta.toFixed(2)}%
            {up ? (
              <IconTrendUp className="h-3.5 w-3.5" />
            ) : (
              <IconTrendDown className="h-3.5 w-3.5" />
            )}
          </span>
        )}
      </div>
      {hint && <div className="mt-1.5 text-[11.5px] text-ink-faint">{hint}</div>}
    </div>
  );
}
