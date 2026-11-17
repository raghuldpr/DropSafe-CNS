import React, { useState, useEffect } from 'react';
import {
  DashboardIcon,
  FolderIcon,
  ShareIcon,
  ShieldIcon,
  VerifiedIcon,
  SettingsIcon,
  UploadCloudIcon,
  PlusIcon,
  DocumentIcon,
} from '../components/Icons';
import { AdminNavItem } from '../components/AdminNavItem';
import { useAuth } from '../context/AuthContext';
import { workspaceApi } from '../services/api';
import type { WorkspaceOverviewResponse } from '../types/api';
import './DashboardPage.css';

interface DashboardPageProps {
  onNavigate: (
    route:
      | 'landing'
      | 'login'
      | 'register'
      | 'upload'
      | 'upload-progress'
      | 'dashboard'
      | 'files'
      | 'file-details'
      | 'share'
      | 'shared-with-me'
      | 'shared-by-me'
      | 'policies'
      | 'access-denied'
      | 'audit-log'
      | 'settings'
  ) => void;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({ onNavigate }) => {
  const { user, logout } = useAuth();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [sharedFilesModalOpen, setSharedFilesModalOpen] = useState(false);
  const [overview, setOverview] = useState<WorkspaceOverviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    let isMounted = true;
    const fetchOverview = async () => {
      try {
        const data = await workspaceApi.getOverview();
        if (isMounted) setOverview(data);
      } catch (err) {
        console.warn('[DropSafe Dashboard] Failed to load workspace overview:', err);
      } finally {
        if (isMounted) setIsLoading(false);
      }
    };
    fetchOverview();
    return () => {
      isMounted = false;
    };
  }, []);

  const handleLogout = async () => {
    await logout();
    onNavigate('landing');
  };

  return (
    <div className="ds-dashboard-shell">
      {/* Mobile Backdrop */}
      <div
        className={`ds-sidebar-backdrop ${
          mobileSidebarOpen ? 'ds-sidebar-backdrop--visible' : ''
        }`}
        onClick={() => setMobileSidebarOpen(false)}
        aria-hidden="true"
      />

      {/* Application Sidebar */}
      <aside
        className={`ds-sidebar ${mobileSidebarOpen ? 'ds-sidebar--open' : ''}`}
        aria-label="Workspace navigation"
      >
        <div className="ds-sidebar__header">
          <a
            href="#/"
            className="ds-sidebar__brand"
            onClick={(e) => {
              e.preventDefault();
              onNavigate('dashboard');
            }}
            aria-label="DropSafe Home"
          >
            <img
              src="/assets/dropsafe-logo.png"
              alt="DropSafe"
              className="ds-sidebar__logo"
            />
          </a>
        </div>

        <nav className="ds-sidebar__nav">
          <span className="ds-sidebar__section-label">Workspace</span>

          <button
            type="button"
            className="ds-sidebar__item ds-sidebar__item--active"
            aria-current="page"
          >
            <span className="ds-sidebar__icon" aria-hidden="true">
              <DashboardIcon size={18} />
            </span>
            <span>Dashboard</span>
          </button>

          <button
            type="button"
            className="ds-sidebar__item"
            onClick={() => onNavigate('files')}
          >
            <span className="ds-sidebar__icon" aria-hidden="true">
              <FolderIcon size={18} />
            </span>
            <span>My Files</span>
          </button>

          <button
            type="button"
            className="ds-sidebar__item"
            onClick={() => onNavigate('shared-with-me')}
          >
            <span className="ds-sidebar__icon" aria-hidden="true">
              <ShareIcon size={18} />
            </span>
            <span>Shared with Me</span>
          </button>

          <button
            type="button"
            className="ds-sidebar__item"
            onClick={() => onNavigate('shared-by-me')}
          >
            <span className="ds-sidebar__icon" aria-hidden="true">
              <ShareIcon size={18} />
            </span>
            <span>Shared by Me</span>
          </button>

          <span className="ds-sidebar__section-label" style={{ marginTop: 'var(--space-3)' }}>
            Governance
          </span>

          <button
            type="button"
            className="ds-sidebar__item"
            onClick={() => onNavigate('policies')}
          >
            <span className="ds-sidebar__icon" aria-hidden="true">
              <ShieldIcon size={18} />
            </span>
            <span>Access Policies</span>
          </button>

          <button
            type="button"
            className="ds-sidebar__item"
            onClick={() => onNavigate('audit-log')}
          >
            <span className="ds-sidebar__icon" aria-hidden="true">
              <VerifiedIcon size={18} />
            </span>
            <span>Audit Log</span>
          </button>

          <AdminNavItem onNavigate={onNavigate} />

          <span className="ds-sidebar__section-label" style={{ marginTop: 'var(--space-3)' }}>
            System
          </span>

          <button
            type="button"
            className="ds-sidebar__item"
            onClick={() => onNavigate('settings')}
          >
            <span className="ds-sidebar__icon" aria-hidden="true">
              <SettingsIcon size={18} />
            </span>
            <span>Settings</span>
          </button>
        </nav>

        <div className="ds-sidebar__footer">
          <div className="ds-sidebar__badge">
            <span className="ds-sidebar__badge-dot" aria-hidden="true" />
            <span>{user ? user.email : 'Signed In'}</span>
          </div>
          <button
            type="button"
            style={{
              fontSize: '11px',
              color: 'var(--color-text-secondary)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              marginTop: '6px',
            }}
            onClick={handleLogout}
          >
            Log Out
          </button>
        </div>
      </aside>

      {/* Main Workspace Frame */}
      <div className="ds-dashboard-main">
        {/* Top Navbar */}
        <header className="ds-topbar" role="banner">
          <div className="ds-topbar__left">
            <button
              type="button"
              className="ds-topbar__menu-toggle"
              onClick={() => setMobileSidebarOpen(!mobileSidebarOpen)}
              aria-label="Toggle navigation menu"
            >
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>

            <div className="ds-topbar__breadcrumb" aria-label="Breadcrumb">
              <span>Dashboard</span>
              <span aria-hidden="true">/</span>
              <span className="ds-topbar__crumb--active">Your Workspace</span>
            </div>
          </div>

          <div className="ds-topbar__right">
            <div className="ds-topbar__session-pill">
              <span className="ds-sidebar__badge-dot" aria-hidden="true" />
              <span>{user?.display_name || user?.email || 'Authenticated'}</span>
            </div>

            <button
              type="button"
              className="ds-topbar__upload-btn"
              onClick={() => onNavigate('upload')}
              aria-label="Upload files"
            >
              <PlusIcon size={16} aria-hidden="true" />
              <span>Upload Files</span>
            </button>
          </div>
        </header>

        {/* Dashboard Body */}
        <main className="ds-dashboard-content" role="main">
          {/* Workspace Intro */}
          <section className="ds-workspace-header" aria-labelledby="workspace-heading">
            <h1 id="workspace-heading" className="ds-workspace-title">
              Your Workspace
            </h1>
            <p className="ds-workspace-subtitle">
              Manage your zero-knowledge encrypted files and decentralized sharing activity.
            </p>
          </section>

          {/* Metrics Bar */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px', marginBottom: '24px' }}>
            <div style={{ padding: '16px 20px', borderRadius: '12px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>Owned Documents</div>
              <div style={{ fontSize: '24px', fontWeight: 600, color: '#fff' }}>{overview?.owned_documents_count ?? (isLoading ? '...' : 0)}</div>
            </div>
            <div style={{ padding: '16px 20px', borderRadius: '12px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>Shared with Me</div>
              <div style={{ fontSize: '24px', fontWeight: 600, color: '#fff' }}>{overview?.shared_with_me_count ?? (isLoading ? '...' : 0)}</div>
            </div>
            <div style={{ padding: '16px 20px', borderRadius: '12px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>Active Grants Issued</div>
              <div style={{ fontSize: '24px', fontWeight: 600, color: '#fff' }}>{overview?.active_grants_issued_count ?? (isLoading ? '...' : 0)}</div>
            </div>
            <div style={{ padding: '16px 20px', borderRadius: '12px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.06)' }}>
              <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginBottom: '4px' }}>Key Security Status</div>
              <div style={{ fontSize: '14px', fontWeight: 600, color: overview?.has_active_encryption_key ? '#4ade80' : '#f59e0b', marginTop: '6px' }}>
                {overview?.has_active_encryption_key ? 'Active & Ready' : 'Setting up...'}
              </div>
            </div>
          </div>

          {/* Primary Action Card */}
          <section className="ds-upload-cta-card" aria-labelledby="upload-cta-heading">
            <div className="ds-upload-cta-info">
              <div className="ds-upload-cta-icon" aria-hidden="true">
                <UploadCloudIcon size={24} />
              </div>
              <div className="ds-upload-cta-text">
                <h2 id="upload-cta-heading" style={{ fontSize: 'var(--text-lg)', fontWeight: 600, color: 'var(--color-text-primary)' }}>
                  Upload Files
                </h2>
                <p>
                  Encrypt your files in the browser and upload them to secure cloud relays.
                </p>
              </div>
            </div>

            <button
              type="button"
              className="ds-btn ds-btn--primary"
              onClick={() => onNavigate('upload')}
            >
              Choose Files
            </button>
          </section>

          {/* Workspace Feature Overview Shortcuts */}
          <section className="ds-overview-section" aria-labelledby="overview-heading">
            <h2 id="overview-heading" className="ds-section-heading">
              Workspace Overview
            </h2>

            <div className="ds-shortcuts-grid">
              <button
                type="button"
                className="ds-shortcut-card"
                onClick={() => onNavigate('files')}
              >
                <div className="ds-shortcut-icon" aria-hidden="true">
                  <FolderIcon size={18} />
                </div>
                <h4>My Files</h4>
                <p>Access your encrypted files repository.</p>
              </button>

              <button
                type="button"
                className="ds-shortcut-card"
                onClick={() => setSharedFilesModalOpen(true)}
              >
                <div className="ds-shortcut-icon" aria-hidden="true">
                  <ShareIcon size={18} />
                </div>
                <h4>Shared Files</h4>
                <p>Inspect delegated inbound and outbound files.</p>
              </button>

              <button
                type="button"
                className="ds-shortcut-card"
                onClick={() => onNavigate('policies')}
              >
                <div className="ds-shortcut-icon" aria-hidden="true">
                  <ShieldIcon size={18} />
                </div>
                <h4>Access Policies</h4>
                <p>Manage attribute-based delegation criteria.</p>
              </button>

              <button
                type="button"
                className="ds-shortcut-card"
                onClick={() => onNavigate('audit-log')}
              >
                <div className="ds-shortcut-icon" aria-hidden="true">
                  <VerifiedIcon size={18} />
                </div>
                <h4>Audit Log</h4>
                <p>Review cryptographically auditable history.</p>
              </button>
            </div>
          </section>

          {/* Two Columns: Recent Files & Recent Activity */}
          <section className="ds-dashboard-split">
            {/* Recent Files Panel */}
            <div className="ds-split-panel" aria-labelledby="recent-files-heading">
              <h2 id="recent-files-heading" className="ds-section-heading">
                Recent Files
              </h2>
              {overview && overview.recent_documents.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {overview.recent_documents.map((doc) => (
                    <div
                      key={doc.id}
                      style={{
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        padding: '12px 14px',
                        background: 'rgba(255,255,255,0.02)',
                        border: '1px solid rgba(255,255,255,0.05)',
                        borderRadius: '8px',
                        cursor: 'pointer',
                      }}
                      onClick={() => onNavigate('files')}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
                        <DocumentIcon size={18} />
                        <span style={{ fontWeight: 500, fontSize: '13px', color: '#fff' }}>
                          {doc.display_name}
                        </span>
                      </div>
                      <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
                        {new Date(doc.updated_at).toLocaleDateString()}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="ds-empty-state-panel">
                  <div className="ds-empty-state-icon" aria-hidden="true">
                    <DocumentIcon size={22} />
                  </div>
                  <h3 className="ds-empty-state-title">No files uploaded yet</h3>
                  <p className="ds-empty-state-desc">
                    Your zero-knowledge encrypted files will appear here once uploaded.
                  </p>
                  <button
                    type="button"
                    className="ds-btn ds-btn--secondary"
                    onClick={() => onNavigate('upload')}
                    style={{ marginTop: 'var(--space-2)' }}
                  >
                    Upload Your First File
                  </button>
                </div>
              )}
            </div>

            {/* Recent Activity Panel */}
            <div className="ds-split-panel" aria-labelledby="recent-activity-heading">
              <h2 id="recent-activity-heading" className="ds-section-heading">
                Recent Audit Activity
              </h2>
              {overview && overview.recent_audit_events.length > 0 ? (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  {overview.recent_audit_events.map((ev) => (
                    <div
                      key={ev.id}
                      style={{
                        padding: '10px 14px',
                        background: 'rgba(255,255,255,0.02)',
                        border: '1px solid rgba(255,255,255,0.05)',
                        borderRadius: '8px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                      }}
                    >
                      <div>
                        <div style={{ fontSize: '12px', fontWeight: 500, color: '#e2e8f0' }}>
                          {ev.event_type}
                        </div>
                        <div style={{ fontSize: '10px', color: 'var(--color-text-muted)', fontFamily: 'monospace' }}>
                          Hash: {ev.event_hash_hex.substring(0, 16)}...
                        </div>
                      </div>
                      <span
                        style={{
                          fontSize: '11px',
                          padding: '2px 8px',
                          borderRadius: '12px',
                          background: ev.outcome === 'success' ? 'rgba(74, 222, 128, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                          color: ev.outcome === 'success' ? '#4ade80' : '#f87171',
                        }}
                      >
                        {ev.outcome}
                      </span>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="ds-empty-state-panel">
                  <div className="ds-empty-state-icon" aria-hidden="true">
                    <VerifiedIcon size={22} />
                  </div>
                  <h3 className="ds-empty-state-title">Audit trail active</h3>
                  <p className="ds-empty-state-desc">
                    All document operations and sharing grants will record cryptographic events here.
                  </p>
                </div>
              )}
            </div>
          </section>
        </main>
      </div>

      {/* Shared Files Destination Selection Modal */}
      {sharedFilesModalOpen && (
        <div
          className="ds-modal-backdrop"
          onClick={() => setSharedFilesModalOpen(false)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="ds-modal-content"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="ds-modal-header">
              <h3 className="ds-modal-title">Shared Files</h3>
              <button
                type="button"
                className="ds-modal-close"
                onClick={() => setSharedFilesModalOpen(false)}
                aria-label="Close modal"
              >
                ✕
              </button>
            </div>
            <p className="ds-modal-desc">
              Choose which direction of shared documents you would like to view:
            </p>
            <div className="ds-modal-options">
              <button
                type="button"
                className="ds-modal-option-btn"
                onClick={() => {
                  setSharedFilesModalOpen(false);
                  onNavigate('shared-with-me');
                }}
              >
                <div className="ds-modal-option-icon">
                  <ShareIcon size={18} />
                </div>
                <div>
                  <strong>Shared with Me</strong>
                  <p>Documents that others have granted you access to.</p>
                </div>
              </button>
              <button
                type="button"
                className="ds-modal-option-btn"
                onClick={() => {
                  setSharedFilesModalOpen(false);
                  onNavigate('shared-by-me');
                }}
              >
                <div className="ds-modal-option-icon">
                  <ShareIcon size={18} />
                </div>
                <div>
                  <strong>Shared by Me</strong>
                  <p>Your documents currently delegated to other recipients.</p>
                </div>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
