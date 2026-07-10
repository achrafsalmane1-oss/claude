import Link from "next/link";
import { Logo } from "@/components/icons";

const links = [
  { href: "#how-it-works", label: "How it works" },
  { href: "#who-its-for", label: "Who it's for" },
  { href: "#whats-included", label: "What's included" },
  { href: "#pricing", label: "Pricing" },
];

export default function Nav() {
  return (
    <div className="pointer-events-none fixed inset-x-0 top-5 z-50 flex justify-center px-4">
      <nav className="pointer-events-auto flex items-center gap-1 rounded-2xl border border-black/5 bg-white/95 py-2 pl-4 pr-2 shadow-[0_10px_30px_-12px_rgba(30,60,40,0.25)] backdrop-blur">
        <Link href="/" className="mr-3">
          <Logo />
        </Link>
        <div className="hidden items-center md:flex">
          {links.map((l) => (
            <a
              key={l.href}
              href={l.href}
              className="rounded-xl px-3.5 py-2 text-[15px] text-ink-soft transition hover:bg-cream hover:text-ink"
            >
              {l.label}
            </a>
          ))}
        </div>
        <Link
          href="/checkout"
          className="ml-2 rounded-xl bg-ink px-4 py-2 text-[14px] font-medium text-white transition hover:bg-black"
        >
          Start now
        </Link>
      </nav>
    </div>
  );
}
