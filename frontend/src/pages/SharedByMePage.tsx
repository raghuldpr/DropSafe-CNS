import { AdminNavItem } from '../components/AdminNavItem';
import React, { useState, useEffect, useMemo } from 'react';
import {
  DashboardIcon,
  FolderIcon,
  ShareIcon,
  ShieldIcon,
  VerifiedIcon,
  SettingsIcon,
  SearchIcon,
  XCloseIcon,
  DocumentIcon,
  TrashIcon,
} from '../components/Icons';
import { documentApi, sharingApi } from '../services/api';
import type { AccessGrantResponse } from '../types/api';
import './SharedWithMePage.css';
import './SharedByMePage.css';

interface SharedByMePageProps {
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
  selectedFiles?: File[];
}

interface OutgoingGrantRecord extends AccessGrantResponse {
  fileName: string;
}

export const SharedByMePage: React.FC<SharedByMePageProps> = ({
  onNavigate,
  selectedFiles = [],
}) => {
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFilter, setSelectedFilter] = useState<string>('all');
  const [grants, setGrants] = useState<OutgoingGrantRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionMessage, setActionMessage] = useState<string | null>(null);

  const loadOutgoingGrants = async () => {
    try {
      setLoading(true);
      const ownedDocs = await documentApi.list('owned');
      const allGrants: OutgoingGrantRecord[] = [];

      for (const doc of ownedDocs) {
        try {
          const docGrants = await sharingApi.listGrants(doc.id);
          for (const g of docGrants) {
            allGrants.push({
              ...g,
              fileName: doc.display_name,
            });
          }
        } catch {
          // ignore individual document grant fetch error
        }
      }

      setGrants(allGrants);
    } catch (err: any) {
      console.error('Failed to load outgoing grants:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadOutgoingGrants();
  }, []);

  const handleRevoke = async (docId: string, grantId: string, fileName: string) => {
    if (!confirm(`Revoke recipient access grant for "${fileName}"?`)) return;
    try {
      setActionMessage(`Revoking recipient envelope grant...`);
      await sharingApi.revokeGrant(docId, grantId);
      setActionMessage(`Grant revoked successfully.`);
      await loadOutgoingGrants();
      setTimeout(() => setActionMessage(null), 3000);
    } catch (err: any) {
      setActionMessage(`Revocation failed: ${err.message}`);
    }
  };

  const filteredRecords = useMemo(() => {
    return grants.filter((rec) => {
      const recipientText = rec.grantee_email || rec.grantee_user_id || '';
      const matchesSearch =
        rec.fileName.toLowerCase().includes(searchQuery.trim().toLowerCase()) ||
        recipientText.toLowerCase().includes(searchQuery.trim().toLowerCase());

      const permissions = rec.permissions || [];
      const matchesLevel =
        selectedFilter === 'all'
          ? true
          : selectedFilter === 'editor'
          ? permissions.includes('write') || permissions.includes('admin')
          : permissions.includes('read') || permissions.includes('download');

      return matchesSearch && matchesLevel;
    });
  }, [grants, searchQuery, selectedFilter]);

  const resetFilters = () => {
    setSearchQuery('');
    setSelectedFilter('all');
  };

  const handleShareFileNavigation = () => {
    if (selectedFiles.length > 0) {
      onNavigate('share');
    } else {
      onNavigate('files');
    }
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
            className="ds-sidebar__item ds-sidebar__item--active"
            aria-current="page"
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
            <span>Active Envelopes</span>
          </div>
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
              <span className="ds-topbar__crumb--active">Shared by Me</span>
            </nav>
          </div>

          <div className="ds-topbar__right">
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
        <main className="ds-shared-by-content" id="main-content">
          <div className="ds-shared-by-header">
            <div className="ds-shared-by-header__text">
              <h1 className="ds-shared-by-header__title">Shared by Me</h1>
              <p className="ds-shared-by-header__subtitle">
                Review recipient access grants, verify cryptographic DEK re-wrapping, and revoke access on demand.
              </p>
            </div>

            <button
              type="button"
              className="ds-btn ds-btn--primary"
              onClick={handleShareFileNavigation}
            >
              Share a File
            </button>
          </div>

          {actionMessage && (
            <div
              style={{
                padding: 'var(--space-2) var(--space-3)',
                background: 'rgba(255, 255, 255, 0.05)',
                border: '1px solid var(--color-border)',
                borderRadius: 'var(--radius-md)',
                marginBottom: 'var(--space-3)',
                fontSize: '13px',
                color: 'var(--color-text-primary)',
              }}
            >
              {actionMessage}
            </div>
          )}

          {/* Controls Toolbar */}
          <section className="ds-shared-toolbar" aria-label="Search and filter outgoing shares">
            <div className="ds-shared-toolbar__top">
              <div className="ds-shared-search-wrapper">
                <span className="ds-shared-search-icon" aria-hidden="true">
                  <SearchIcon size={16} />
                </span>
                <input
                  type="text"
                  className="ds-shared-search-input"
                  placeholder="Search shared files or recipients..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  aria-label="Search shared files or recipients"
                />
                {searchQuery && (
                  <button
                    type="button"
                    className="ds-shared-search-clear"
                    onClick={() => setSearchQuery('')}
                    aria-label="Clear search input"
                  >
                    <XCloseIcon size={14} />
                  </button>
                )}
              </div>
            </div>

            {/* Filter Pills */}
            <div className="ds-shared-filters" role="radiogroup" aria-label="Filter by access level">
              {[
                { id: 'all', label: 'All Grants' },
                { id: 'viewer', label: 'Viewer / Download' },
                { id: 'editor', label: 'Editor / Admin' },
              ].map((f) => (
                <button
                  key={f.id}
                  type="button"
                  className={`ds-shared-pill ${
                    selectedFilter === f.id ? 'ds-shared-pill--active' : ''
                  }`}
                  onClick={() => setSelectedFilter(f.id)}
                  role="radio"
                  aria-checked={selectedFilter === f.id}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </section>

          {/* Table */}
          {loading ? (
            <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--color-text-muted)' }}>
              Loading issued access grants...
            </div>
          ) : grants.length === 0 ? (
            <section className="ds-shared-empty-card" role="region">
              <div className="ds-shared-empty-icon" aria-hidden="true">
                <ShareIcon size={26} />
              </div>
              <h2 className="ds-shared-empty-title">You haven't shared any files yet</h2>
              <p className="ds-shared-empty-desc">
                Files you choose to share with recipients will appear here with active DEK envelopes.
              </p>
              <div style={{ marginTop: 'var(--space-2)' }}>
                <button
                  type="button"
                  className="ds-btn ds-btn--primary"
                  onClick={handleShareFileNavigation}
                >
                  Share a File
                </button>
              </div>
            </section>
          ) : filteredRecords.length === 0 ? (
            <section className="ds-shared-empty-card" role="region">
              <div className="ds-shared-empty-icon" aria-hidden="true">
                <SearchIcon size={24} />
              </div>
              <h2 className="ds-shared-empty-title">No matching grants</h2>
              <p className="ds-shared-empty-desc">Try a different search or filter query.</p>
              <div style={{ marginTop: 'var(--space-2)' }}>
                <button
                  type="button"
                  className="ds-btn ds-btn--secondary"
                  onClick={resetFilters}
                >
                  Reset Filters
                </button>
              </div>
            </section>
          ) : (
            <div className="ds-shared-table-container">
              <table className="ds-shared-table">
                <thead>
                  <tr>
                    <th>File</th>
                    <th>Recipient</th>
                    <th>Permissions</th>
                    <th>Date Granted</th>
                    <th>Status</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRecords.map((r) => (
                    <tr key={r.id}>
                      <td style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <DocumentIcon size={18} style={{ color: 'var(--color-accent)' }} />
                        <span style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>
                          {r.fileName}
                        </span>
                      </td>
                      <td>
                        <div>
                          <div>{r.grantee_email || 'Recipient Key ID'}</div>
                          <div style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
                            {r.grantee_user_id ? `${r.grantee_user_id.slice(0, 10)}...` : 'Link Grant'}
                          </div>
                        </div>
                      </td>
                      <td>
                        <span className="ds-badge-permission ds-badge-permission--viewer">
                          {r.permissions.join(', ') || 'read'}
                        </span>
                      </td>
                      <td>{new Date(r.created_at).toLocaleDateString()}</td>
                      <td>
                        <span
                          className={`ds-badge-permission ${
                            r.status === 'active'
                              ? 'ds-badge-permission--editor'
                              : 'ds-badge-permission--viewer'
                          }`}
                          style={{ textTransform: 'uppercase', fontSize: '11px' }}
                        >
                          {r.status}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        {r.status === 'active' && (
                          <button
                            type="button"
                            className="ds-btn ds-btn--danger"
                            onClick={() => handleRevoke(r.document_id, r.id, r.fileName)}
                            style={{ padding: '4px 8px', fontSize: '12px' }}
                            title="Revoke grant immediately"
                          >
                            <TrashIcon size={14} aria-hidden="true" />
                            <span>Revoke</span>
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>
    </div>
  );
};

export default SharedByMePage;
