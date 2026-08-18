import { redirect } from 'next/navigation';
import { getUser } from '@/auth/session';

/** No marketing page (spec §9): straight to the product or to sign-in. */
export default async function RootPage() {
  const user = await getUser();
  redirect(user ? '/domains' : '/login');
}
