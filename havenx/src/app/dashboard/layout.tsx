import { redirect } from "next/navigation";
import { getCurrentUser } from "@/lib/session";
import { db } from "@/lib/db";
import Sidebar from "@/components/dashboard/Sidebar";
import NotificationsBell from "@/components/dashboard/NotificationsBell";
import { IconSearch } from "@/components/icons";

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const user = await getCurrentUser();
  if (!user) redirect("/login");
  if (!user.subscription) redirect("/checkout");
  if (!user.mandate) redirect("/onboarding/buybox");

  const [notifications, interestedNew] = await Promise.all([
    db.notification.findMany({
      where: { userId: user.id },
      orderBy: { createdAt: "desc" },
      take: 12,
    }),
    db.prospect.count({
      where: {
        userId: user.id,
        replyDisposition: "INTERESTED",
        introStatus: "NEW",
      },
    }),
  ]);

  return (
    <div className="min-h-screen bg-cream">
      <div className="mx-auto flex max-w-[1400px] gap-4 p-4">
        <Sidebar interestedNew={interestedNew} />
        <div className="min-w-0 flex-1">
          {/* Top bar */}
          <header className="mb-4 flex items-center justify-between rounded-2xl border border-line bg-white px-4 py-2.5">
            <div className="flex items-center gap-2 text-[13.5px] text-ink-faint">
              <span>Workspace</span>
              <span>/</span>
              <span className="font-medium text-ink">
                {user.mandate.senderCompany}
              </span>
            </div>
            <div className="flex items-center gap-2">
              <div className="hidden items-center gap-2 rounded-xl bg-cream px-3.5 py-2 text-[13px] text-ink-faint md:flex">
                <IconSearch className="h-3.5 w-3.5" />
                Search pipeline
              </div>
              <NotificationsBell
                items={notifications.map((n) => ({
                  id: n.id,
                  title: n.title,
                  body: n.body,
                  href: n.href,
                  readAt: n.readAt?.toISOString() ?? null,
                  createdAt: n.createdAt.toISOString(),
                }))}
              />
              <div
                className="flex h-9 w-9 items-center justify-center rounded-xl bg-green-soft text-[13px] font-semibold text-green-dark"
                title={user.email}
              >
                {user.email.slice(0, 1).toUpperCase()}
              </div>
            </div>
          </header>
          {children}
        </div>
      </div>
    </div>
  );
}
