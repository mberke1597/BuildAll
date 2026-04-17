'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { apiFetch, setToken } from '../../lib/api';

export default function LoginPage() {
  const router = useRouter();
  const [email, setEmail] = useState('consultant@demo.com');
  const [password, setPassword] = useState('Consultant123!');
  const [error, setError] = useState<string | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    setIsLoading(true);
    try {
      const res = await apiFetch<{ access_token: string }>('/auth/login', {
        method: 'POST',
        body: JSON.stringify({ email, password }),
      });
      setToken(res.access_token);
      router.push('/projects');
    } catch (err) {
      setError('Invalid email or password. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="login-container">
      <div className="login-card animate-fade-in">
        <div className="login-header">
          <h1 className="login-title">
            Welcome back
          </h1>
          <p className="login-subtitle">
            Sign in to access your construction projects
          </p>
        </div>

        <form onSubmit={onSubmit} className="stack">
          <div className="stack">
            <label className="muted" style={{ marginBottom: '-8px' }}>Email</label>
            <input
              className="input"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="Enter your email"
              autoComplete="email"
            />
          </div>

          <div className="stack">
            <label className="muted" style={{ marginBottom: '-8px' }}>Password</label>
            <input
              className="input"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="Enter your password"
              autoComplete="current-password"
            />
          </div>

          {error && (
            <div className="badge badge-error" style={{ padding: '12px 16px', width: '100%', justifyContent: 'center' }}>
              {error}
            </div>
          )}

          <button className="button" type="submit" disabled={isLoading} style={{ marginTop: '8px' }}>
            {isLoading ? (
              <>
                <span className="loading-spinner" />
                Signing in...
              </>
            ) : (
              <>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"/>
                  <polyline points="10 17 15 12 10 7"/>
                  <line x1="15" y1="12" x2="3" y2="12"/>
                </svg>
                Sign in
              </>
            )}
          </button>
        </form>

        <div style={{ marginTop: '32px', paddingTop: '24px', borderTop: '1px solid var(--border-color)' }}>
          <p className="muted" style={{ marginBottom: '16px', textAlign: 'center' }}>Demo accounts</p>
          <div className="stack" style={{ gap: '8px' }}>
            {[
              { email: 'admin@demo.com', pass: 'Admin123!', role: 'Admin' },
              { email: 'consultant@demo.com', pass: 'Consultant123!', role: 'Consultant' },
              { email: 'client@demo.com', pass: 'Client123!', role: 'Client' },
            ].map((demo) => (
              <button
                key={demo.email}
                type="button"
                className="button button-secondary"
                style={{ justifyContent: 'space-between', padding: '12px 16px' }}
                onClick={() => {
                  setEmail(demo.email);
                  setPassword(demo.pass);
                }}
              >
                <span>{demo.role}</span>
                <span className="muted" style={{ fontSize: '12px' }}>{demo.email}</span>
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
