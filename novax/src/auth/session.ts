import { headers } from 'next/headers';
import { redirect } from 'next/navigation';
import { auth } from './index';

/**
 * Server-side session helpers for dashboard pages.
 *
 * `requireUser` redirects rather than throwing, so a page can call it as its
 * first line and everything after is guaranteed authenticated.
 */

export async function getUser() {
  const session = await auth.api.getSession({ headers: await headers() });
  return session?.user ?? null;
}

export async function requireUser() {
  const user = await getUser();
  if (!user) redirect('/login');
  return user;
}
