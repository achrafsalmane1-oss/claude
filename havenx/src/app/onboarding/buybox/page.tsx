import Link from "next/link";
import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/session";
import { Logo } from "@/components/icons";
import BuyBoxForm from "./BuyBoxForm";

export default async function BuyBoxPage() {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (!user.subscription) redirect("/checkout");

  return (
    <main className="dot-grid-dark flex min-h-screen flex-col items-center bg-cream px-4 pb-20 pt-8">
      <div className="w-full max-w-5xl">
        <Link href="/">
          <Logo />
        </Link>
      </div>
      <div className="mt-12 w-full max-w-2xl">
        <div className="mb-8 text-center">
          <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-line bg-white px-3.5 py-1.5 text-[13px] font-medium text-green-dark">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-green" />
            Subscription active — infrastructure provisioning
          </div>
          <h1 className="display text-[42px] leading-tight text-ink">
            Define your <span className="italic text-green-deep">buy-box</span>
          </h1>
          <p className="mx-auto mt-2 max-w-md text-[15.5px] text-ink-soft">
            This becomes your standing acquisition mandate. Sourcing starts the
            moment you activate it.
          </p>
        </div>
        <div className="flex justify-center">
          <BuyBoxForm userEmail={user.email} />
        </div>
      </div>
    </main>
  );
}
