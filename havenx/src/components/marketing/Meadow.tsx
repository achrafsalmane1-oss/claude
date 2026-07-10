// Painterly rolling-meadow illustration, built as layered SVG so it ships
// with zero image assets. Flower speckles are placed with a seeded PRNG so
// server and client render identically.

function mulberry32(seed: number) {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const FLOWER_COLORS = [
  "#f5b8d0",
  "#f7d477",
  "#f1975a",
  "#c9a6ec",
  "#fdf6e3",
  "#f28d9a",
  "#ffffff",
];

function speckles(
  seed: number,
  count: number,
  yMin: number,
  yMax: number,
  rMin = 1.1,
  rMax = 2.6
) {
  const rand = mulberry32(seed);
  return Array.from({ length: count }, (_, i) => {
    const x = rand() * 1440;
    const y = yMin + rand() * (yMax - yMin);
    const r = rMin + rand() * (rMax - rMin);
    const color = FLOWER_COLORS[Math.floor(rand() * FLOWER_COLORS.length)];
    const o = 0.5 + rand() * 0.5;
    return <circle key={i} cx={x} cy={y} r={r} fill={color} opacity={o} />;
  });
}

export default function Meadow({ className = "" }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 1440 520"
      preserveAspectRatio="xMidYMax slice"
      className={className}
      aria-hidden
    >
      <defs>
        <linearGradient id="hillFar" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#8fce8f" />
          <stop offset="100%" stopColor="#5da96b" />
        </linearGradient>
        <linearGradient id="hillMid" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#7cc47d" />
          <stop offset="100%" stopColor="#4a9a5c" />
        </linearGradient>
        <linearGradient id="hillNear" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#66b56e" />
          <stop offset="100%" stopColor="#3c8a50" />
        </linearGradient>
        <linearGradient id="haze" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#cfe7f8" stopOpacity="0.9" />
          <stop offset="100%" stopColor="#cfe7f8" stopOpacity="0" />
        </linearGradient>
      </defs>

      {/* far hills */}
      <path
        d="M0 240 C 180 150 340 170 520 220 C 700 270 830 160 1010 180 C 1190 200 1310 150 1440 190 L 1440 520 L 0 520 Z"
        fill="url(#hillFar)"
      />
      <g opacity="0.65">{speckles(11, 90, 210, 300, 0.9, 1.8)}</g>
      {/* atmospheric haze on the far ridge */}
      <rect x="0" y="140" width="1440" height="140" fill="url(#haze)" />

      {/* middle hills */}
      <path
        d="M0 340 C 220 250 420 300 620 330 C 840 363 980 250 1160 275 C 1300 295 1390 260 1440 275 L 1440 520 L 0 520 Z"
        fill="url(#hillMid)"
      />
      <g opacity="0.85">{speckles(23, 150, 300, 410)}</g>

      {/* near hill */}
      <path
        d="M0 450 C 260 380 480 430 720 440 C 960 450 1140 380 1440 430 L 1440 520 L 0 520 Z"
        fill="url(#hillNear)"
      />
      <g>{speckles(37, 130, 430, 520, 1.4, 3.2)}</g>
    </svg>
  );
}
