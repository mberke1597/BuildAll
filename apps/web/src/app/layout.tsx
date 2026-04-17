import './globals.css';
import type { ReactNode } from 'react';
import Header from '../components/Header';

export const metadata = {
  title: 'BuildAll - Construction Management Platform',
  description: 'Professional Construction Consultant ↔ Client Collaboration Platform',
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="app-shell">
          <Header />
          <main className="app-main">{children}</main>
        </div>
      </body>
    </html>
  );
}
