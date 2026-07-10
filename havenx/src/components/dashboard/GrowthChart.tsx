"use client";

// Single-series area chart (owners sourced, cumulative). One y-axis,
// recessive grid, crosshair + tooltip on hover; the panel title names the
// series so no legend is needed.

import { useRef, useState } from "react";

export type ChartPoint = { date: string; value: number };

const W = 720;
const H = 220;
const PAD = { top: 12, right: 12, bottom: 26, left: 44 };

export default function GrowthChart({ points }: { points: ChartPoint[] }) {
  const svgRef = useRef<SVGSVGElement>(null);
  const [hover, setHover] = useState<number | null>(null);

  if (points.length < 2) {
    return (
      <div className="flex h-52 items-center justify-center text-[13px] text-ink-faint">
        Not enough history yet — check back tomorrow.
      </div>
    );
  }

  const max = Math.max(...points.map((p) => p.value));
  const yMax = Math.ceil(max / 50) * 50 || 10;
  const innerW = W - PAD.left - PAD.right;
  const innerH = H - PAD.top - PAD.bottom;

  const x = (i: number) => PAD.left + (i / (points.length - 1)) * innerW;
  const y = (v: number) => PAD.top + innerH - (v / yMax) * innerH;

  const line = points
    .map((p, i) => `${i === 0 ? "M" : "L"} ${x(i).toFixed(1)} ${y(p.value).toFixed(1)}`)
    .join(" ");
  const area = `${line} L ${x(points.length - 1).toFixed(1)} ${PAD.top + innerH} L ${PAD.left} ${PAD.top + innerH} Z`;

  const gridLines = [0.25, 0.5, 0.75, 1].map((f) => ({
    yPos: y(yMax * f),
    label: Math.round(yMax * f),
  }));

  const onMove = (e: React.PointerEvent) => {
    const rect = svgRef.current?.getBoundingClientRect();
    if (!rect) return;
    const px = ((e.clientX - rect.left) / rect.width) * W;
    const i = Math.round(((px - PAD.left) / innerW) * (points.length - 1));
    setHover(Math.max(0, Math.min(points.length - 1, i)));
  };

  const h = hover !== null ? points[hover] : null;

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full touch-none select-none"
        role="img"
        aria-label="Owners sourced over time"
        onPointerMove={onMove}
        onPointerLeave={() => setHover(null)}
      >
        {gridLines.map((g) => (
          <g key={g.label}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={g.yPos}
              y2={g.yPos}
              stroke="#EEEBE0"
              strokeWidth={1}
            />
            <text
              x={PAD.left - 8}
              y={g.yPos + 3.5}
              textAnchor="end"
              className="fill-ink-faint"
              fontSize={11}
            >
              {g.label}
            </text>
          </g>
        ))}
        <line
          x1={PAD.left}
          x2={W - PAD.right}
          y1={PAD.top + innerH}
          y2={PAD.top + innerH}
          stroke="#E3E0D4"
          strokeWidth={1}
        />

        {[0, Math.floor((points.length - 1) / 2), points.length - 1].map((i) => (
          <text
            key={i}
            x={x(i)}
            y={H - 8}
            textAnchor={i === 0 ? "start" : i === points.length - 1 ? "end" : "middle"}
            className="fill-ink-faint"
            fontSize={11}
          >
            {new Date(points[i].date).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
            })}
          </text>
        ))}

        <path d="M0 0" />
        <path d={area} fill="#2FB44F" opacity={0.1} />
        <path d={line} fill="none" stroke="#1E7F3C" strokeWidth={2} />

        {h && hover !== null && (
          <g>
            <line
              x1={x(hover)}
              x2={x(hover)}
              y1={PAD.top}
              y2={PAD.top + innerH}
              stroke="#9199A4"
              strokeWidth={1}
              strokeDasharray="3 3"
            />
            <circle
              cx={x(hover)}
              cy={y(h.value)}
              r={4.5}
              fill="#1E7F3C"
              stroke="#fff"
              strokeWidth={2}
            />
          </g>
        )}
      </svg>

      {h && hover !== null && (
        <div
          className="pointer-events-none absolute -top-1 rounded-xl border border-line bg-white px-3 py-2 shadow-lg"
          style={{
            left: `${(x(hover) / W) * 100}%`,
            transform: `translateX(${hover > points.length / 2 ? "-110%" : "10%"})`,
          }}
        >
          <div className="text-[11px] text-ink-faint">
            {new Date(h.date).toLocaleDateString("en-US", {
              month: "short",
              day: "numeric",
              year: "numeric",
            })}
          </div>
          <div className="text-[14px] font-semibold text-ink">
            {h.value.toLocaleString()} <span className="font-normal text-ink-soft">sourced</span>
          </div>
        </div>
      )}
    </div>
  );
}
