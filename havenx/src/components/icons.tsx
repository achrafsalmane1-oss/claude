import type { SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;

const base = {
  fill: "none",
  stroke: "currentColor",
  strokeWidth: 1.8,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  viewBox: "0 0 24 24",
};

export function LogoMark({ className }: { className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} aria-hidden>
      <rect
        x="4.6"
        y="4.6"
        width="14.8"
        height="14.8"
        rx="3.4"
        transform="rotate(45 12 12)"
        fill="#2FB44F"
      />
      <rect
        x="8.4"
        y="8.4"
        width="7.2"
        height="7.2"
        rx="1.6"
        transform="rotate(45 12 12)"
        fill="#166C31"
      />
    </svg>
  );
}

export function Logo({ className = "" }: { className?: string }) {
  return (
    <span className={`inline-flex items-center gap-2 ${className}`}>
      <LogoMark className="h-6 w-6" />
      <span className="text-[17px] font-semibold tracking-tight text-ink">
        HavenX
      </span>
    </span>
  );
}

export const IconGrid = (p: P) => (
  <svg {...base} {...p}>
    <rect x="4" y="4" width="6.5" height="6.5" rx="2" />
    <rect x="13.5" y="4" width="6.5" height="6.5" rx="2" />
    <rect x="4" y="13.5" width="6.5" height="6.5" rx="2" />
    <rect x="13.5" y="13.5" width="6.5" height="6.5" rx="2" />
  </svg>
);

export const IconFunnel = (p: P) => (
  <svg {...base} {...p}>
    <path d="M4 5h16l-6.2 7.2V19l-3.6-2v-4.8L4 5Z" />
  </svg>
);

export const IconSpark = (p: P) => (
  <svg {...base} {...p}>
    <path d="M12 3.5 13.8 9l5.7 1.9-5.7 1.9L12 18.5l-1.8-5.7-5.7-1.9L10.2 9 12 3.5Z" />
    <path d="M19 15.5l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2Z" strokeWidth={1.4} />
  </svg>
);

export const IconTarget = (p: P) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="8.2" />
    <circle cx="12" cy="12" r="4.6" />
    <circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none" />
  </svg>
);

export const IconUsers = (p: P) => (
  <svg {...base} {...p}>
    <circle cx="9" cy="8.5" r="3.2" />
    <path d="M3.5 19.5c.6-3.2 2.9-4.8 5.5-4.8s4.9 1.6 5.5 4.8" />
    <path d="M15.5 5.6a3.2 3.2 0 0 1 0 5.8M17.6 14.9c1.7.7 2.7 2.2 3 4.6" />
  </svg>
);

export const IconChart = (p: P) => (
  <svg {...base} {...p}>
    <path d="M4 4v14.5A1.5 1.5 0 0 0 5.5 20H20" />
    <path d="M8 15.5v-3M12.5 15.5V8.5M17 15.5V11" />
  </svg>
);

export const IconTrendUp = (p: P) => (
  <svg {...base} {...p}>
    <path d="M4 16.5 9.5 11l3.5 3.5L20 8" />
    <path d="M15.5 8H20v4.5" />
  </svg>
);

export const IconTrendDown = (p: P) => (
  <svg {...base} {...p}>
    <path d="M4 8l5.5 5.5L13 10l7 6.5" />
    <path d="M15.5 16.5H20V12" />
  </svg>
);

export const IconDoc = (p: P) => (
  <svg {...base} {...p}>
    <path d="M7 3.8h7.2L18.8 8v12.2H7z" strokeWidth={0} fill="currentColor" opacity={0.15} />
    <path d="M7 3.8h7.2L18.8 8v12.2a0 0 0 0 1 0 0H7a0 0 0 0 1 0 0z" />
    <path d="M14 4v4.2h4.6M10 12.5h4.5M10 15.8h4.5" />
  </svg>
);

export const IconMail = (p: P) => (
  <svg {...base} {...p}>
    <rect x="3.5" y="5.5" width="17" height="13" rx="2.5" />
    <path d="m4.5 7.5 7.5 5.5 7.5-5.5" />
  </svg>
);

export const IconPhone = (p: P) => (
  <svg {...base} {...p}>
    <path d="M7.1 3.8c.6 0 2 2.5 2 3.2 0 1-1.4 1.4-1.4 2.3 0 1.2 3.8 5.1 5 5.1.9 0 1.3-1.4 2.3-1.4.7 0 3.2 1.4 3.2 2 0 1.6-1.7 3.2-3.2 3.2-4.6 0-11.2-6.4-11.2-11.2 0-1.5 1.7-3.2 3.3-3.2Z" />
  </svg>
);

export const IconLinkedIn = (p: P) => (
  <svg {...base} {...p}>
    <rect x="4" y="4" width="16" height="16" rx="3" />
    <path d="M8.2 10.5v6M8.2 7.8v.1M12 16.5v-3.4c0-1.4.9-2.4 2.1-2.4s1.9.9 1.9 2.4v3.4" />
  </svg>
);

export const IconBell = (p: P) => (
  <svg {...base} {...p}>
    <path d="M12 4a5.5 5.5 0 0 1 5.5 5.5c0 4 1.5 5.4 1.5 5.4H5s1.5-1.4 1.5-5.4A5.5 5.5 0 0 1 12 4Z" />
    <path d="M10 18.5a2.1 2.1 0 0 0 4 0" />
  </svg>
);

export const IconSearch = (p: P) => (
  <svg {...base} {...p}>
    <circle cx="11" cy="11" r="6.2" />
    <path d="m16 16 4 4" />
  </svg>
);

export const IconArrowUpRight = (p: P) => (
  <svg {...base} {...p}>
    <path d="M7 17 17 7M9.5 7H17v7.5" />
  </svg>
);

export const IconArrowRight = (p: P) => (
  <svg {...base} {...p}>
    <path d="M4.5 12h15M13.5 6l6 6-6 6" />
  </svg>
);

export const IconCheck = (p: P) => (
  <svg {...base} {...p}>
    <path d="m5 12.5 4.5 4.5L19 7.5" />
  </svg>
);

export const IconCalendar = (p: P) => (
  <svg {...base} {...p}>
    <rect x="4" y="5.5" width="16" height="14.5" rx="2.5" />
    <path d="M4 10h16M8.5 3.5v4M15.5 3.5v4" />
  </svg>
);

export const IconBuilding = (p: P) => (
  <svg {...base} {...p}>
    <path d="M5 20V5.5A1.5 1.5 0 0 1 6.5 4h7A1.5 1.5 0 0 1 15 5.5V20M15 9.5h3.5A1.5 1.5 0 0 1 20 11v9M3.5 20h17" />
    <path d="M8 8h1.5M11 8h1.5M8 11.5h1.5M11 11.5h1.5M8 15h1.5M11 15h1.5" />
  </svg>
);

export const IconMap = (p: P) => (
  <svg {...base} {...p}>
    <path d="M12 21s6.5-5.4 6.5-10.2A6.5 6.5 0 0 0 5.5 10.8C5.5 15.6 12 21 12 21Z" />
    <circle cx="12" cy="10.5" r="2.3" />
  </svg>
);

export const IconLink = (p: P) => (
  <svg {...base} {...p}>
    <path d="M10 14.5 14 10.5" />
    <path d="M8.5 12 6.8 13.7a3.6 3.6 0 0 0 5.1 5.1l1.6-1.7M15.5 12.5l1.7-1.7a3.6 3.6 0 0 0-5.1-5.1l-1.6 1.7" />
  </svg>
);

export const IconHandshake = (p: P) => (
  <svg {...base} {...p}>
    <path d="m3 8 4-2 5 2.5L17 6l4 2v7l-4 2.5-4-2-4 2L3 15V8Z" />
    <path d="m12 8.5-3.5 3.4a1.3 1.3 0 0 0 1.8 1.8L12 12l2 1.8" />
  </svg>
);

export const IconSettings = (p: P) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="3" />
    <path d="M12 3.8v2M12 18.2v2M20.2 12h-2M5.8 12h-2M17.8 6.2l-1.4 1.4M7.6 16.4l-1.4 1.4M17.8 17.8l-1.4-1.4M7.6 7.6 6.2 6.2" />
  </svg>
);

export const IconClock = (p: P) => (
  <svg {...base} {...p}>
    <circle cx="12" cy="12" r="8.2" />
    <path d="M12 7.5V12l3 2" />
  </svg>
);

export const IconShield = (p: P) => (
  <svg {...base} {...p}>
    <path d="M12 3.5 19 6v5.5c0 4.6-3 7.7-7 9-4-1.3-7-4.4-7-9V6l7-2.5Z" />
    <path d="m9 11.8 2.2 2.2 3.8-4" />
  </svg>
);

export const IconLightning = (p: P) => (
  <svg {...base} {...p}>
    <path d="M13 3 5.5 13.5H11L10 21l7.5-10.5H12L13 3Z" />
  </svg>
);
