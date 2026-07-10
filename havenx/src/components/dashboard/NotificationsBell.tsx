"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { IconBell } from "@/components/icons";
import { markNotificationsRead } from "@/app/dashboard/actions";
import { formatRelative } from "@/lib/format";

export type NotificationItem = {
  id: string;
  title: string;
  body: string;
  href: string | null;
  readAt: string | null;
  createdAt: string;
};

export default function NotificationsBell({
  items,
}: {
  items: NotificationItem[];
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const unread = items.filter((n) => !n.readAt).length;

  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", onClick);
    return () => document.removeEventListener("mousedown", onClick);
  }, []);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        aria-label="Notifications"
        onClick={() => {
          setOpen(!open);
          if (!open && unread > 0) markNotificationsRead();
        }}
        className="relative flex h-9 w-9 items-center justify-center rounded-xl text-ink-soft transition hover:bg-cream hover:text-ink"
      >
        <IconBell className="h-4.5 w-4.5" />
        {unread > 0 && (
          <span className="absolute right-1.5 top-1.5 flex h-2 w-2 rounded-full bg-green ring-2 ring-white" />
        )}
      </button>

      {open && (
        <div className="absolute right-0 top-11 z-40 w-96 rounded-2xl border border-line bg-white p-2 shadow-[0_24px_50px_-24px_rgba(30,60,40,0.4)]">
          <div className="px-3 py-2 text-[13px] font-semibold text-ink">
            Notifications
          </div>
          <div className="max-h-96 space-y-1 overflow-y-auto">
            {items.length === 0 && (
              <p className="px-3 py-6 text-center text-[13px] text-ink-faint">
                Nothing yet — interested owners will show up here.
              </p>
            )}
            {items.map((n) => (
              <Link
                key={n.id}
                href={n.href ?? "/dashboard"}
                onClick={() => setOpen(false)}
                className={`block rounded-xl px-3 py-2.5 transition hover:bg-cream ${
                  n.readAt ? "" : "bg-green-mist"
                }`}
              >
                <div className="flex items-baseline justify-between gap-2">
                  <span className="text-[13.5px] font-medium text-ink">
                    {n.title}
                  </span>
                  <span className="shrink-0 text-[11px] text-ink-faint">
                    {formatRelative(n.createdAt)}
                  </span>
                </div>
                <p className="mt-0.5 line-clamp-2 text-[12.5px] leading-relaxed text-ink-soft">
                  {n.body}
                </p>
              </Link>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
