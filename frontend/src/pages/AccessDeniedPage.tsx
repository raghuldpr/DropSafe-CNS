import { AdminNavItem } from '../components/AdminNavItem';
import React, { useState } from 'react';
import {
  DashboardIcon,
  FolderIcon,
  ShareIcon,
  ShieldIcon,
  VerifiedIcon,
  SettingsIcon,
  LockIcon,
} from '../components/Icons';
import './AccessDeniedPage.css';

interface AccessDeniedPageProps {
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

export const AccessDeniedPage: React.FC<AccessDeniedPageProps> = ({ onNavigate }) => {
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

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
              onNavigate('landing');
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
            className="ds-sidebar__item"
            onClick={() => onNavigate('dashboard')}
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

          <span
            className="ds-sidebar__section-label"
            style={{ marginTop: 'var(--space-3)' }}
          >
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

          <span
            className="ds-sidebar__section-label"
            style={{ marginTop: 'var(--space-3)' }}
          >
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
            <span>Frontend Preview</span>
          </div>
          <button
            type="button"
            style={{
              fontSize: '11px',
              color: 'var(--color-text-secondary)',
              background: 'none',
              border: 'none',
              cursor: 'pointer',
            }}
            onClick={() => onNavigate('landing')}
          >
            Exit
          </button>
        </div>
      </aside>

      {/* Main Area */}
      <div className="ds-main-area">
        {/* Top Bar */}
        <header className="ds-topbar" role="banner">
          <div className="ds-topbar__left">
            <button
              type="button"
              className="ds-topbar__menu-toggle"
              onClick={() => setMobileSidebarOpen(!mobileSidebarOpen)}
              aria-label="Toggle navigation menu"
            >
              <svg
                width="20"
                height="20"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
              >
                <line x1="3" y1="12" x2="21" y2="12" />
                <line x1="3" y1="6" x2="21" y2="6" />
                <line x1="3" y1="18" x2="21" y2="18" />
              </svg>
            </button>

            {/* Breadcrumb Navigation */}
            <nav className="ds-topbar__breadcrumb" aria-label="Breadcrumb">
              <button
                type="button"
                style={{
                  background: 'none',
                  border: 'none',
                  color: 'var(--color-text-muted)',
                  cursor: 'pointer',
                  padding: 0,
                  fontSize: 'inherit',
                }}
                onClick={() => onNavigate('dashboard')}
              >
                Dashboard
              </button>
              <span aria-hidden="true">/</span>
              <span className="ds-topbar__crumb--active">Access Restricted</span>
            </nav>
          </div>

          <div className="ds-topbar__right">
            <div className="ds-topbar__session-pill">
              <span className="ds-sidebar__badge-dot" aria-hidden="true" />
              <span>Workspace Prototype</span>
            </div>

            <button
              type="button"
              className="ds-topbar__upload-btn"
              onClick={() => onNavigate('upload')}
              aria-label="Upload New File"
            >
              Upload
            </button>
          </div>
        </header>

        {/* Content Area */}
        <main className="ds-denied-content" id="main-content">
          <section
            className="ds-denied-card"
            role="region"
            aria-labelledby="denied-heading"
          >
            {/* Status Pill Badge */}
            <span className="ds-denied-pill">
              ACCESS RESTRICTED
            </span>

            {/* Status Icon */}
            <div className="ds-denied-icon" aria-hidden="true">
              <LockIcon size={30} />
            </div>

            {/* Headings */}
            <h1 id="denied-heading" className="ds-denied-title">
              Access unavailable
            </h1>

            <p className="ds-denied-lead">
              You don't currently have access to this resource.
            </p>

            <p className="ds-denied-subtext">
              If you believe you should have access, contact the person who manages
              the file's sharing permissions.
            </p>

            {/* Guidance Informational Box */}
            <div className="ds-denied-guidance" role="note" aria-label="Guidance on requesting access">
              <span className="ds-denied-guidance__heading">Need access?</span>
              <p className="ds-denied-guidance__body">
                Ask the file owner or the person who shared the resource to review your access.
              </p>
            </div>

            {/* Navigation Actions */}
            <div className="ds-denied-actions">
              <button
                type="button"
                className="ds-btn ds-btn--primary"
                onClick={() => onNavigate('dashboard')}
              >
                Return to Dashboard
              </button>

              <button
                type="button"
                className="ds-btn ds-btn--secondary"
                onClick={() => onNavigate('files')}
              >
                Go to My Files
              </button>
            </div>

            {/* Policy Reference Link */}
            <button
              type="button"
              className="ds-denied-link"
              onClick={() => onNavigate('policies')}
            >
              Review Access Policies
            </button>
          </section>
        </main>
      </div>


    </div>
  );
};
