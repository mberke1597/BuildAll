'use client';

import Link from 'next/link';
import { useEffect, useState } from 'react';
import { clearToken, getToken } from '../lib/api';
import { useRouter } from 'next/navigation';

export default function Header() {
  const router = useRouter();
  const [isLoggedIn, setIsLoggedIn] = useState(false);

  useEffect(() => {
    // Only read localStorage on the client after mount — prevents hydration mismatch
    setIsLoggedIn(Boolean(getToken()));
  }, []);

  const onLogout = () => {
    clearToken();
    router.push('/login');
  };

  return (
    <header className="app-header">
      <Link href="/" className="logo">
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <rect x="3" y="10" width="7" height="11" rx="1" fill="url(#grad1)" />
          <rect x="14" y="6" width="7" height="15" rx="1" fill="url(#grad1)" />
          <rect x="8" y="3" width="8" height="18" rx="1" fill="url(#grad2)" />
          <defs>
            <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#3b82f6" />
              <stop offset="100%" stopColor="#8b5cf6" />
            </linearGradient>
            <linearGradient id="grad2" x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="#60a5fa" />
              <stop offset="100%" stopColor="#a78bfa" />
            </linearGradient>
          </defs>
        </svg>
        BuildAll
      </Link>

      <div className="header-user-menu">
        {isLoggedIn ? (
          <>
            <Link href="/dashboard" className="header-user-link">
              Profile
            </Link>
            <button type="button" className="header-user-button" onClick={onLogout}>
              Logout
            </button>
          </>
        ) : (
          <Link href="/login" className="header-user-link">
            Login
          </Link>
        )}
      </div>
    </header>
  );
}

