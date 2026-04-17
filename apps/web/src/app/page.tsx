'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getToken } from '../lib/api';

export default function HomePage() {
  const router = useRouter();
  const [isLoggedIn, setIsLoggedIn] = useState<boolean | null>(null);

  useEffect(() => {
    const token = getToken();
    if (token) {
      router.replace('/dashboard');
    } else {
      setIsLoggedIn(false);
    }
  }, [router]);

  // Show loading while checking auth
  if (isLoggedIn === null) {
    return (
      <div className="landing-loader">
        <div className="loading-spinner" style={{ width: '40px', height: '40px' }} />
      </div>
    );
  }

  // Landing page for non-logged in users
  return (
    <div className="landing-page">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="hero-bg-gradient" />
        <div className="hero-content">
          <div className="hero-badge">
            <span className="badge-dot" />
            AI-Powered Construction Management
          </div>
          <h1 className="hero-title">
            Build Smarter.<br />
            <span className="text-gradient">Communicate Better.</span>
          </h1>
          <p className="hero-subtitle">
            The all-in-one platform connecting construction consultants and clients. 
            Real-time collaboration, AI-powered insights, and seamless project management.
          </p>
          <div className="hero-cta">
            <a href="/login" className="button button-lg">
              Get Started Free
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="5" y1="12" x2="19" y2="12"/>
                <polyline points="12 5 19 12 12 19"/>
              </svg>
            </a>
            <a href="#features" className="button button-lg button-outline">
              See How It Works
            </a>
          </div>
          <div className="hero-stats">
            <div className="hero-stat">
              <span className="hero-stat-value">500+</span>
              <span className="hero-stat-label">Projects Managed</span>
            </div>
            <div className="hero-stat">
              <span className="hero-stat-value">98%</span>
              <span className="hero-stat-label">Client Satisfaction</span>
            </div>
            <div className="hero-stat">
              <span className="hero-stat-value">24/7</span>
              <span className="hero-stat-label">AI Support</span>
            </div>
          </div>
        </div>
        <div className="hero-visual">
          <div className="hero-mockup">
            <div className="mockup-header">
              <div className="mockup-dots">
                <span /><span /><span />
              </div>
              <span className="mockup-title">BuildAll Dashboard</span>
            </div>
            <div className="mockup-content">
              <div className="mockup-sidebar">
                <div className="mockup-nav-item active" />
                <div className="mockup-nav-item" />
                <div className="mockup-nav-item" />
              </div>
              <div className="mockup-main">
                <div className="mockup-card" />
                <div className="mockup-card" />
                <div className="mockup-chart" />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* Logos Section */}
      <section className="logos-section">
        <p className="logos-title">Trusted by leading construction companies</p>
        <div className="logos-grid">
          {['ConstructCo', 'BuildMax', 'UrbanDev', 'SkylineBuilders', 'MetroPlan'].map((name) => (
            <div key={name} className="logo-item">{name}</div>
          ))}
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="features-section">
        <div className="section-header">
          <span className="section-badge">Features</span>
          <h2 className="section-title">Everything you need to manage construction projects</h2>
          <p className="section-subtitle">
            From real-time chat to AI-powered document analysis, we have got you covered.
          </p>
        </div>
        <div className="features-grid">
          <div className="feature-card">
            <div className="feature-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/>
              </svg>
            </div>
            <h3 className="feature-title">Real-time Communication</h3>
            <p className="feature-desc">
              Instant messaging between consultants and clients. Share files, voice notes, and updates in real-time.
            </p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <circle cx="12" cy="12" r="10"/>
                <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3"/>
                <line x1="12" y1="17" x2="12.01" y2="17"/>
              </svg>
            </div>
            <h3 className="feature-title">AI Document Q&A</h3>
            <p className="feature-desc">
              Upload project documents and ask questions. Our AI provides instant answers with source citations.
            </p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="1" x2="12" y2="23"/>
                <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6"/>
              </svg>
            </div>
            <h3 className="feature-title">Cost Estimation</h3>
            <p className="feature-desc">
              AI-powered cost estimates based on project parameters. Make informed decisions with accurate projections.
            </p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
              </svg>
            </div>
            <h3 className="feature-title">Document Management</h3>
            <p className="feature-desc">
              Centralized storage for all project documents. Automatic indexing and intelligent search capabilities.
            </p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="18" y1="20" x2="18" y2="10"/>
                <line x1="12" y1="20" x2="12" y2="4"/>
                <line x1="6" y1="20" x2="6" y2="14"/>
              </svg>
            </div>
            <h3 className="feature-title">Analytics & Insights</h3>
            <p className="feature-desc">
              Track project progress with detailed analytics. Audit logs and activity monitoring for full transparency.
            </p>
          </div>
          <div className="feature-card">
            <div className="feature-icon">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/>
                <circle cx="9" cy="7" r="4"/>
                <path d="M23 21v-2a4 4 0 0 0-3-3.87"/>
                <path d="M16 3.13a4 4 0 0 1 0 7.75"/>
              </svg>
            </div>
            <h3 className="feature-title">Role-Based Access</h3>
            <p className="feature-desc">
              Secure access control for admins, consultants, and clients. Everyone sees only what they need.
            </p>
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="how-section">
        <div className="section-header">
          <span className="section-badge">How It Works</span>
          <h2 className="section-title">Get started in minutes</h2>
        </div>
        <div className="steps-grid">
          <div className="step-card">
            <div className="step-number">1</div>
            <h3 className="step-title">Create Your Account</h3>
            <p className="step-desc">Sign up as a consultant or get invited as a client by your consultant.</p>
          </div>
          <div className="step-card">
            <div className="step-number">2</div>
            <h3 className="step-title">Start a Project</h3>
            <p className="step-desc">Create projects, invite team members, and set up your workspace.</p>
          </div>
          <div className="step-card">
            <div className="step-number">3</div>
            <h3 className="step-title">Collaborate & Build</h3>
            <p className="step-desc">Chat, share documents, get AI insights, and track progress together.</p>
          </div>
        </div>
      </section>

      {/* CTA Section */}
      <section className="cta-section">
        <div className="cta-content">
          <h2 className="cta-title">Ready to transform your construction workflow?</h2>
          <p className="cta-subtitle">
            Join hundreds of construction professionals using BuildAll to streamline their projects.
          </p>
          <a href="/login" className="button button-lg">
            Start Building Today
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <line x1="5" y1="12" x2="19" y2="12"/>
              <polyline points="12 5 19 12 12 19"/>
            </svg>
          </a>
        </div>
      </section>

      {/* Footer */}
      <footer className="landing-footer">
        <div className="footer-content">
          <div className="footer-brand">
            <div className="logo">
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect x="3" y="10" width="7" height="11" rx="1" fill="currentColor" fillOpacity="0.6"/>
                <rect x="14" y="6" width="7" height="15" rx="1" fill="currentColor" fillOpacity="0.6"/>
                <rect x="8" y="3" width="8" height="18" rx="1" fill="currentColor"/>
              </svg>
              BuildAll
            </div>
            <p className="footer-tagline">AI-powered construction management platform</p>
          </div>
          <div className="footer-links">
            <div className="footer-column">
              <h4>Product</h4>
              <a href="#features">Features</a>
              <a href="#pricing">Pricing</a>
              <a href="#demo">Request Demo</a>
            </div>
            <div className="footer-column">
              <h4>Company</h4>
              <a href="#about">About Us</a>
              <a href="#careers">Careers</a>
              <a href="#contact">Contact</a>
            </div>
            <div className="footer-column">
              <h4>Legal</h4>
              <a href="#privacy">Privacy Policy</a>
              <a href="#terms">Terms of Service</a>
            </div>
          </div>
        </div>
        <div className="footer-bottom">
          <p>© 2026 BuildAll. All rights reserved.</p>
        </div>
      </footer>
    </div>
  );
}
