import Link from "next/link";
import { redirect } from "next/navigation";
import { randomBytes } from "crypto";
import { db } from "@/lib/db";
import { notifications } from "@/services";
import { Logo, IconArrowRight } from "@/components/icons";

async function sendLink(formData: FormData) {
  "use server";
  const email = String(formData.get("email") ?? "").trim().toLowerCase();
  if (!email || !email.includes("@")) redirect("/login?error=email");

  const user = await db.user.findUnique({ where: { email } });
  // Don't reveal whether the account exists; only send when it does.
  if (user) {
    const token = randomBytes(32).toString("hex");
    await db.magicLinkToken.create({
      data: {
        token,
        email,
        expiresAt: new Date(Date.now() + 15 * 60 * 1000),
      },
    });
    const appUrl = process.env.NEXT_PUBLIC_APP_URL ?? "http://localhost:3000";
    await notifications.sendMagicLink(
      email,
      `${appUrl}/api/auth/verify?token=${token}`
    );
  }
  redirect("/login?sent=1");
}

export default async function LoginPage({
  searchParams,
}: {
  searchParams: Promise<{ sent?: string; error?: string }>;
}) {
  const { sent, error } = await searchParams;
  return (
    <main className="dot-grid-dark flex min-h-screen flex-col items-center bg-cream px-4 pt-8">
      <div className="w-full max-w-5xl">
        <Link href="/">
          <Logo />
        </Link>
      </div>
      <div className="mt-24 w-full max-w-md rounded-[24px] border border-line bg-white p-8 shadow-[0_24px_50px_-36px_rgba(30,60,40,0.5)]">
        <h1 className="display text-[34px] text-ink">Sign in</h1>
        <p className="mt-1.5 text-[15px] text-ink-soft">
          We&apos;ll email you a magic link — no password needed.
        </p>

        {sent ? (
          <div className="mt-6 rounded-xl bg-green-mist px-4 py-3.5 text-[14.5px] leading-relaxed text-green-dark">
            If an account exists for that address, a sign-in link is on its
            way. It expires in 15 minutes.
          </div>
        ) : (
          <form action={sendLink} className="mt-6 space-y-3.5">
            <input
              name="email"
              type="email"
              required
              placeholder="you@yourfund.com"
              className="w-full rounded-xl border border-line bg-panel px-3.5 py-2.5 text-[15px] text-ink outline-none transition placeholder:text-ink-faint focus:border-green focus:bg-white"
            />
            {error === "email" && (
              <p className="text-[12.5px] text-fall">
                Enter a valid email address.
              </p>
            )}
            <button
              type="submit"
              className="flex w-full items-center justify-center gap-2 rounded-2xl bg-ink px-6 py-3.5 text-[15.5px] font-semibold text-white transition hover:bg-black"
            >
              Email me a sign-in link
              <IconArrowRight className="h-4.5 w-4.5" />
            </button>
          </form>
        )}

        <p className="mt-6 text-center text-[13.5px] text-ink-faint">
          New to HavenX?{" "}
          <Link href="/checkout" className="font-medium text-green-dark">
            Start now
          </Link>
        </p>
      </div>
    </main>
  );
}
