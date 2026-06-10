"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "Home", icon: "◈" },
  { href: "/add-funds", label: "Add funds", icon: "＋" },
  { href: "/send", label: "Send", icon: "↗" },
  { href: "/swap", label: "Swap", icon: "⇄" },
  { href: "/markets", label: "Markets", icon: "◷" },
  { href: "/invest", label: "Invest", icon: "▲" },
  { href: "/activity", label: "Activity", icon: "≡" },
];

export default function Sidebar() {
  const pathname = usePathname();
  return (
    <aside className="sticky top-0 flex h-screen w-56 shrink-0 flex-col border-r border-line bg-surface px-4 py-6 max-md:w-16 max-md:px-2">
      <Link href="/" className="mb-8 flex items-center gap-2 px-2">
        <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent text-sm font-bold text-white">
          OB
        </span>
        <span className="text-lg font-semibold tracking-tight max-md:hidden">
          OpenBank
        </span>
      </Link>
      <nav className="flex flex-col gap-1">
        {NAV.map((item) => {
          const active = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors max-md:justify-center max-md:px-0 ${
                active
                  ? "bg-accent-soft font-medium text-accent"
                  : "text-muted hover:bg-surface-2 hover:text-foreground"
              }`}
            >
              <span className="w-4 text-center">{item.icon}</span>
              <span className="max-md:hidden">{item.label}</span>
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto px-2 text-xs text-muted max-md:hidden">
        Powered by OpenFinance
      </div>
    </aside>
  );
}
