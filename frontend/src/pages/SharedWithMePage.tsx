import React, { useState, useMemo, useEffect } from 'react';
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
} from '../components/Icons';
import { AdminNavItem } from '../components/AdminNavItem';
import { useAuth } from '../context/AuthContext';
import { sharingApi, documentApi } from '../services/api';
import {
  getUserPrivateKey,
  unwrapDek,
  decryptFile,
} from '../services/crypto';
import type { SharedDocumentResponse } from '../types/api';
import './SharedWithMePage.css';

interface SharedWithMePageProps {
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

export const SharedWithMePage: React.FC<SharedWithMePageProps> = ({ onNavigate }) => {
  const { user, logout } = useAuth();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [sharedDocs, setSharedDocs] = useState<SharedDocumentResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);

  // Search and filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [permissionFilter, setPermissionFilter] = useState<'all' | 'read' | 'download'>('all');

  const fetchSharedDocs = async () => {
    setIsLoading(true);
    try {
      const data = await sharingApi.listSharedWithMe();
      setSharedDocs(data);
    } catch (err: any) {
      console.warn('[DropSafe SharedWithMe] Error:', err);
      setErrorNotice(err.message || 'Failed to load shared files');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSharedDocs();
  }, []);

  // Format bytes helper
  const formatBytes = (bytes?: number): string => {
    if (!bytes || bytes === 0) return '—';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  // Filtered records calculation
  const filteredRecords = useMemo(() => {
    return sharedDocs.filter((item) => {
      const matchesSearch =
        item.document.display_name.toLowerCase().includes(searchQuery.trim().toLowerCase()) ||
        (item.grant.grantee_email && item.grant.grantee_email.toLowerCase().includes(searchQuery.trim().toLowerCase()));

      const matchesFilter =
        permissionFilter === 'all'
          ? true
          : item.grant.permissions.includes(permissionFilter);

      return matchesSearch && matchesFilter;
    });
  }, [sharedDocs, searchQuery, permissionFilter]);

  const resetFilters = () => {
    setSearchQuery('');
    setPermissionFilter('all');
  };

  // Recipient Decryption and Download
  const handleDownloadAndDecrypt = async (item: SharedDocumentResponse) => {
    if (!user || !item.document.current_version) return;
    setDownloadingId(item.document.id);
    setErrorNotice(null);

    try {
      // 1. Get presigned download URL and recipient-specific wrapped DEK
      const downloadInfo = await documentApi.getDownloadUrl(
        item.document.id,
        item.document.current_version.id
      );

      // 2. Fetch ciphertext from storage relay
      const ciphertext = await documentApi.fetchCiphertextFromStorage(downloadInfo.download_url);

      // 3. Retrieve user's private RSA encryption key from IndexedDB
      const privKey = await getUserPrivateKey(user.id, 'encryption');
      if (!privKey) {
        throw new Error('Local decryption private key not found in browser storage. Please ensure key setup is complete.');
      }

      // 4. Unwrap Document Encryption Key (DEK)
      const dek = await unwrapDek(downloadInfo.wrapped_dek, privKey);

      // 5. Decrypt ciphertext with AES-256-GCM
      const plaintextBuffer = await decryptFile(ciphertext, dek, downloadInfo.manifest as any);

      // 6. Trigger native browser save dialog
      const blob = new Blob([plaintextBuffer], {
        type: item.document.media_type || 'application/octet-stream',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = item.document.display_name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error('[DropSafe Recipient Decrypt Error]:', err);
      setErrorNotice(`Decryption failed: ${err.message}`);
    } finally {
      setDownloadingId(null);
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
            className="ds-sidebar__item ds-sidebar__item--active"
            aria-current="page"
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
            onClick={async () => {
              await logout();
              onNavigate('landing');
            }}
          >
            Log Out
          </button>
        </div>
      </aside>

      {/* Main Content Area */}
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
              <span style={{ cursor: 'pointer' }} onClick={() => onNavigate('dashboard')}>
                Dashboard
              </span>
              <span aria-hidden="true">/</span>
              <span className="ds-topbar__crumb--active">Shared with Me</span>
            </div>
          </div>

          <div className="ds-topbar__right">
            <button
              type="button"
              className="ds-btn ds-btn--secondary"
              onClick={fetchSharedDocs}
              style={{ fontSize: '12px', padding: '6px 12px' }}
            >
              Refresh
            </button>
          </div>
        </header>

        {/* Content Body */}
        <main className="ds-dashboard-content" role="main">
          {/* Header */}
          <section className="ds-workspace-header" aria-labelledby="shared-heading">
            <h1 id="shared-heading" className="ds-workspace-title">
              Shared with Me
            </h1>
            <p className="ds-workspace-subtitle">
              Documents securely shared with you via Attribute-Based Access Control and wrapped cryptographic envelopes.
            </p>
          </section>

          {/* Error Notice */}
          {errorNotice && (
            <div
              style={{
                marginBottom: '16px',
                padding: '12px 16px',
                background: 'rgba(239, 68, 68, 0.1)',
                border: '1px solid rgba(239, 68, 68, 0.3)',
                borderRadius: '8px',
                color: '#f87171',
                fontSize: '13px',
              }}
            >
              {errorNotice}
            </div>
          )}

          {/* Toolbar */}
          <section className="ds-shared-toolbar" aria-label="Filter shared files">
            <div className="ds-search-wrapper">
              <SearchIcon size={16} className="ds-search-icon" aria-hidden="true" />
              <input
                type="text"
                className="ds-search-input"
                placeholder="Search shared files by name..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                aria-label="Search shared files"
              />
              {searchQuery && (
                <button
                  type="button"
                  className="ds-search-clear"
                  onClick={() => setSearchQuery('')}
                  aria-label="Clear search input"
                >
                  <XCloseIcon size={14} aria-hidden="true" />
                </button>
              )}
            </div>

            <div className="ds-shared-filters" role="radiogroup" aria-label="Filter by permission">
              {(
                [
                  { id: 'all', label: 'All Shared' },
                  { id: 'download', label: 'Can Download' },
                  { id: 'read', label: 'Read Only' },
                ] as const
              ).map((f) => (
                <button
                  key={f.id}
                  type="button"
                  className={`ds-shared-pill ${permissionFilter === f.id ? 'ds-shared-pill--active' : ''}`}
                  onClick={() => setPermissionFilter(f.id)}
                  role="radio"
                  aria-checked={permissionFilter === f.id}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </section>

          {/* Records Table */}
          {isLoading ? (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--color-text-muted)' }}>
              Checking active access grants and cryptographic credentials...
            </div>
          ) : sharedDocs.length === 0 ? (
            <section className="ds-shared-empty-card" role="region" aria-labelledby="empty-shared-heading">
              <div className="ds-shared-empty-icon" aria-hidden="true">
                <ShareIcon size={26} />
              </div>
              <h2 id="empty-shared-heading" className="ds-shared-empty-title">
                Nothing shared with you yet
              </h2>
              <p className="ds-shared-empty-desc">
                When an owner grants your account access and wraps a document key for your encryption key, it will appear here.
              </p>
            </section>
          ) : filteredRecords.length === 0 ? (
            <section className="ds-shared-empty-card" role="region" aria-labelledby="no-results-heading">
              <div className="ds-shared-empty-icon" aria-hidden="true">
                <SearchIcon size={24} />
              </div>
              <h2 id="no-results-heading" className="ds-shared-empty-title">
                No matching results
              </h2>
              <p className="ds-shared-empty-desc">Try a different search query or filter.</p>
              <button type="button" className="ds-btn ds-btn--secondary" onClick={resetFilters}>
                Reset Filters
              </button>
            </section>
          ) : (
            <div className="ds-shared-table-container">
              <table className="ds-shared-table">
                <thead>
                  <tr>
                    <th>File</th>
                    <th>Permissions</th>
                    <th>Ciphertext Size</th>
                    <th>Date Granted</th>
                    <th>Status</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredRecords.map((item) => (
                    <tr key={item.grant.id}>
                      <td style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <DocumentIcon size={18} style={{ color: 'var(--color-accent)' }} />
                        <div style={{ display: 'flex', flexDirection: 'column' }}>
                          <span style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>
                            {item.document.display_name}
                          </span>
                          <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>
                            {item.document.media_type || 'binary/encrypted'}
                          </span>
                        </div>
                      </td>
                      <td>
                        <span className="ds-badge-permission ds-badge-permission--read">
                          {item.grant.permissions.join(', ')}
                        </span>
                      </td>
                      <td>
                        {item.document.current_version
                          ? formatBytes(item.document.current_version.ciphertext_size_bytes)
                          : '—'}
                      </td>
                      <td>{new Date(item.grant.created_at).toLocaleDateString()}</td>
                      <td>
                        <span style={{ color: item.grant.status === 'active' ? '#4ade80' : '#f87171', fontSize: '12px' }}>
                          {item.grant.status}
                        </span>
                      </td>
                      <td style={{ textAlign: 'right' }}>
                        <button
                          type="button"
                          className="ds-btn ds-btn--secondary"
                          style={{ fontSize: '11px', padding: '4px 10px' }}
                          disabled={downloadingId === item.document.id || !item.document.current_version}
                          onClick={() => handleDownloadAndDecrypt(item)}
                        >
                          {downloadingId === item.document.id ? 'Decrypting...' : 'Decrypt & Download'}
                        </button>
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
