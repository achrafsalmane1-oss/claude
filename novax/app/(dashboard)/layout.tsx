import Link from 'next/link';
import { requireUser } from '@/auth/session';

/**
 * Dashboard shell. Every page under this layout requires a session.
 * Deliberately plain — the spec says not to spend time here.
 */
export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const user = await requireUser();

  return (
    <>
      <nav className="top">
        <span className="brand">novaX</span>
        <Link href="/domains">Domains</Link>
        <Link href="/searches">Saved searches</Link>
        <Link href="/keys">API keys</Link>
        <span style={{ marginLeft: 'auto' }} className="muted small">
          {user.email}
        </span>
        <form action="/api/auth/sign-out" method="post">
          <button className="secondary small" type="submit">
            Sign out
          </button>
        </form>
      </nav>
      {children}
    </>
  );
}
