import { auth } from '@/auth';
import { toNextJsHandler } from 'better-auth/next-js';

/** Better Auth's own endpoints (sign-in, sign-up, sign-out, session). */
export const { GET, POST } = toNextJsHandler(auth);
