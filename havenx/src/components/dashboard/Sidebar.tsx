"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LogoMark,
  IconGrid,
  IconFunnel,
  IconHandshake,
  IconTarget,
  IconSettings,
} from "@/components/icons";

const items = [
  { href: "/dashboard", icon: IconGrid, label: "Dashboard" },
  { href: "/dashboard/pipeline", icon: IconFunnel, label: "Pipeline" },
  { href: "/dashboard/interested", icon: IconHandshake, label: "Interested" },
  { href: "/dashboard/buybox", icon: IconTarget, label: "Buy-box" },
  { href: "/dashboard/settings", icon: IconSettings, label: "Settings" },
];

export default function Sidebar({ interestedNew }: { interestedNew: number }) {
  const pathname = usePathname();
  return (
    <aside className="sticky top-4 hidden h-[calc(100vh-2rem)] w-60 shrink-0 flex-col rounded-3xl border border-line bg-white p-4 lg:flex">
      <Link href="/" className="mb-6 flex items-center gap-2.5 px-2 pt-1">
        <LogoMark className="h-6 w-6" />
        <span className="text-[17px] font-semibold tracking-tight text-ink">
          HavenX
        </span>
      </Link>
      <nav className="space-y-1">
        {items.map((item) => {
          const active =
            item.href === "/dashboard"
              ? pathname === "/dashboard"
              : pathname.startsWith(item.href);
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-xl px-3 py-2.5 text-[14.5px] transition ${
                active
                  ? "bg-green-soft font-medium text-green-dark"
                  : "text-ink-soft hover:bg-cream hover:text-ink"
              }`}
            >
              <item.icon className="h-4.5 w-4.5" />
              {item.label}
              {item.label === "Interested" && interestedNew > 0 && (
                <span className="ml-auto rounded-full bg-green px-2 py-0.5 text-[11px] font-semibold text-white">
                  {interestedNew}
                </span>
              )}
            </Link>
          );
        })}
      </nav>
      <div className="mt-auto rounded-2xl bg-cream p-4">
        <div className="text-[13px] font-semibold text-ink">
          Outreach runs 24/7
        </div>
        <p className="mt-1 text-[12px] leading-relaxed text-ink-soft">
          Multi-channel outreach conducted in your name. Interested owners land
          here.
        </p>
      </div>
    </aside>
  );
}
