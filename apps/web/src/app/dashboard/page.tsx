'use client';

import { useEffect, useState } from 'react';
import { apiFetch, clearToken, getToken } from '../../lib/api';
import { useRouter } from 'next/navigation';

type User = {
  id: number;
  email: string;
  role: 'ADMIN' | 'CONSULTANT' | 'CLIENT';
  full_name?: string;
};

type Project = {
  id: number;
  name: string;
  location?: string;
  created_at?: string;
};

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [projects, setProjects] = useState<Project[]>([]);
  const [name, setName] = useState('');
  const [location, setLocation] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [showModal, setShowModal] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  const loadUser = async () => {
    try {
      const data = await apiFetch<User>('/me');
      setUser(data);
      return data;
    } catch {
      clearToken();
      router.push('/login');
      return null;
    }
  };

  const loadProjects = async () => {
    try {
      // The backend will filter based on user role
      const data = await apiFetch<Project[]>('/projects/my');
      setProjects(data);
    } catch {
      // Fallback to regular endpoint
      try {
        const data = await apiFetch<Project[]>('/projects');
        setProjects(data);
      } catch {
        router.push('/login');
      }
    }
  };

  useEffect(() => {
    // Check token first before making any API calls
    const token = getToken();
    if (!token) {
      router.push('/login');
      return;
    }
    
    const init = async () => {
      setIsLoading(true);
      const userData = await loadUser();
      if (userData) {
        await loadProjects();
      }
      setIsLoading(false);
    };
    init();
  }, []);

  const create = async () => {
    if (!name.trim()) return;
    setIsCreating(true);
    try {
      await apiFetch('/projects', {
        method: 'POST',
        body: JSON.stringify({ name, location }),
      });
      setName('');
      setLocation('');
      setShowModal(false);
      loadProjects();
    } finally {
      setIsCreating(false);
    }
  };

  const logout = () => {
    clearToken();
    router.push('/');
  };

  const getRoleLabel = (role: string) => {
    const labels: Record<string, string> = {
      ADMIN: 'Administrator',
      CONSULTANT: 'Consultant',
      CLIENT: 'Client',
    };
    return labels[role] || role;
  };

  const getRoleBadgeClass = (role: string) => {
    const classes: Record<string, string> = {
      ADMIN: 'badge-error',
      CONSULTANT: 'badge-success',
      CLIENT: 'badge-warning',
    };
    return classes[role] || 'badge-success';
  };

  const canCreateProject = user?.role === 'ADMIN' || user?.role === 'CONSULTANT';

  if (isLoading) {
    return (
      <div className="login-container">
        <div className="stack" style={{ alignItems: 'center', gap: '24px' }}>
          <div className="loading-spinner" style={{ width: '40px', height: '40px' }} />
          <p className="muted">Loading your dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="animate-fade-in">
      {/* Dashboard Header */}
      <div className="dashboard-header">
        <div className="dashboard-welcome">
          <h1>
            Welcome back
            {user?.full_name ? `, ${user.full_name.split(' ')[0]}` : ''}! 👋
          </h1>
          <p className="muted">
            {user?.role === 'CLIENT' 
              ? 'View your project updates and communicate with your consultant.'
              : user?.role === 'CONSULTANT'
              ? 'Manage your assigned projects and collaborate with clients.'
              : 'Full access to all projects and system management.'}
          </p>
        </div>
        <div className="dashboard-actions">
          <div className="user-info">
            <span className={`badge ${getRoleBadgeClass(user?.role || '')}`}>
              {getRoleLabel(user?.role || '')}
            </span>
            <span className="muted">{user?.email}</span>
          </div>
          {canCreateProject && (
            <button className="button" onClick={() => setShowModal(true)}>
              <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              New Project
            </button>
          )}
          <button className="button button-secondary" onClick={logout}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>
              <polyline points="16 17 21 12 16 7"/>
              <line x1="21" y1="12" x2="9" y2="12"/>
            </svg>
            Logout
          </button>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', marginBottom: '32px' }}>
        <div className="stat-card">
          <div className="stat-value">{projects.length}</div>
          <div className="stat-label">
            {user?.role === 'CLIENT' ? 'Your Projects' : 'Active Projects'}
          </div>
        </div>
        <div className="stat-card">
          <div className="stat-value">
            {user?.role === 'ADMIN' ? '∞' : user?.role === 'CONSULTANT' ? 'Pro' : 'Basic'}
          </div>
          <div className="stat-label">Access Level</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">24/7</div>
          <div className="stat-label">AI Assistant</div>
        </div>
      </div>

      {/* Section Title */}
      <div className="row" style={{ justifyContent: 'space-between', marginBottom: '24px' }}>
        <h2>
          {user?.role === 'CLIENT' 
            ? 'Your Projects' 
            : user?.role === 'CONSULTANT'
            ? 'Your Assigned Projects'
            : 'All Projects'}
        </h2>
      </div>

      {/* Projects Grid */}
      {projects.length === 0 ? (
        <div className="card">
          <div className="empty-state">
            <div className="empty-state-icon">🏗️</div>
            <h3>
              {user?.role === 'CLIENT'
                ? 'No projects assigned yet'
                : 'No projects yet'}
            </h3>
            <p className="muted" style={{ marginBottom: '24px' }}>
              {user?.role === 'CLIENT'
                ? 'Your consultant will add you to a project soon.'
                : 'Create your first project to get started.'}
            </p>
            {canCreateProject && (
              <button className="button" onClick={() => setShowModal(true)}>
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                Create Your First Project
              </button>
            )}
          </div>
        </div>
      ) : (
        <div className="grid" style={{ gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))' }}>
          {projects.map((p) => (
            <a key={p.id} href={`/projects/${p.id}`} style={{ textDecoration: 'none' }}>
              <div className="project-card">
                <div className="row" style={{ justifyContent: 'space-between', alignItems: 'flex-start' }}>
                  <div>
                    <h3 style={{ marginBottom: '8px' }}>{p.name}</h3>
                    {p.location && (
                      <div className="row muted" style={{ gap: '6px' }}>
                        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/>
                          <circle cx="12" cy="10" r="3"/>
                        </svg>
                        {p.location}
                      </div>
                    )}
                  </div>
                  <div className="badge badge-success">Active</div>
                </div>
                <div style={{ marginTop: '20px', paddingTop: '16px', borderTop: '1px solid var(--border-color)' }}>
                  <div className="row" style={{ justifyContent: 'space-between' }}>
                    <span className="muted" style={{ fontSize: '13px' }}>Project #{p.id}</span>
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ color: 'var(--accent-primary)' }}>
                      <line x1="5" y1="12" x2="19" y2="12"/>
                      <polyline points="12 5 19 12 12 19"/>
                    </svg>
                  </div>
                </div>
              </div>
            </a>
          ))}
        </div>
      )}

      {/* Create Project Modal */}
      {showModal && (
        <div style={{
          position: 'fixed',
          inset: 0,
          background: 'rgba(0, 0, 0, 0.7)',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          zIndex: 1000,
          padding: '20px',
        }} onClick={() => setShowModal(false)}>
          <div className="card animate-fade-in" style={{ maxWidth: '480px', width: '100%' }} onClick={e => e.stopPropagation()}>
            <div className="row" style={{ justifyContent: 'space-between', marginBottom: '24px' }}>
              <h2>Create New Project</h2>
              <button className="button button-secondary button-icon" onClick={() => setShowModal(false)} style={{ width: '36px', height: '36px' }}>
                ×
              </button>
            </div>
            <div className="stack">
              <div>
                <label className="muted" style={{ display: 'block', marginBottom: '8px' }}>Project Name *</label>
                <input
                  className="input"
                  placeholder="e.g., Downtown Office Building"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  autoFocus
                />
              </div>
              <div>
                <label className="muted" style={{ display: 'block', marginBottom: '8px' }}>Location</label>
                <input
                  className="input"
                  placeholder="e.g., Istanbul, Turkey"
                  value={location}
                  onChange={(e) => setLocation(e.target.value)}
                />
              </div>
              <div className="row" style={{ justifyContent: 'flex-end', gap: '12px', marginTop: '8px' }}>
                <button className="button button-secondary" onClick={() => setShowModal(false)}>
                  Cancel
                </button>
                <button className="button" onClick={create} disabled={isCreating || !name.trim()}>
                  {isCreating ? (
                    <>
                      <span className="loading-spinner" />
                      Creating...
                    </>
                  ) : (
                    'Create Project'
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
