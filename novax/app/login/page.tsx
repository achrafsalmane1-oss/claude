'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { createAuthClient } from 'better-auth/react';

/**
 * Dashboard sign-in / sign-up.
 *
 * Email and password only, per spec §3. There is no marketing page and no
 * password-reset email flow in v1 — accounts are issued by an operator
 * alongside API keys.
 */

const authClient = createAuthClient();

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<'sign-in' | 'sign-up'>('sign-in');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);

    const result =
      mode === 'sign-in'
        ? await authClient.signIn.email({ email, password })
        : await authClient.signUp.email({ email, password, name: email.split('@')[0] ?? email });

    setBusy(false);

    if (result.error) {
      setError(result.error.message ?? 'Sign in failed.');
      return;
    }
    router.push('/domains');
    router.refresh();
  }

  return (
    <main className="wrap narrow" style={{ paddingTop: 64 }}>
      <h1>novaX</h1>
      <p className="muted small">Newly registered domain signal engine.</p>

      <div className="panel" style={{ marginTop: 20 }}>
        <form onSubmit={submit}>
          <label className="field">
            Email
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoComplete="email"
            />
          </label>
          <label className="field" style={{ marginTop: 10 }}>
            Password
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={12}
              autoComplete={mode === 'sign-in' ? 'current-password' : 'new-password'}
            />
          </label>

          {error && (
            <div className="notice error small" style={{ marginTop: 12 }}>
              {error}
            </div>
          )}

          <div style={{ marginTop: 14, display: 'flex', gap: 10, alignItems: 'center' }}>
            <button type="submit" disabled={busy}>
              {busy ? 'Working…' : mode === 'sign-in' ? 'Sign in' : 'Create account'}
            </button>
            <button
              type="button"
              className="secondary"
              onClick={() => {
                setMode(mode === 'sign-in' ? 'sign-up' : 'sign-in');
                setError(null);
              }}
            >
              {mode === 'sign-in' ? 'Create an account' : 'I already have an account'}
            </button>
          </div>
        </form>
      </div>

      <p className="small muted" style={{ marginTop: 20 }}>
        Own a domain that appears here? <a href="/opt-out">Remove it from novaX</a>.
      </p>
    </main>
  );
}
