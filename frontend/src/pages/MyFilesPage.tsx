import React, { useState, useMemo, useEffect } from 'react';
import {
  DashboardIcon,
  FolderIcon,
  ShareIcon,
  ShieldIcon,
  VerifiedIcon,
  SettingsIcon,
  PlusIcon,
  SearchIcon,
  ListIcon,
  GridIcon,
  DocumentIcon,
  XCloseIcon,
} from '../components/Icons';
import { AdminNavItem } from '../components/AdminNavItem';
import { useAuth } from '../context/AuthContext';
import { documentApi } from '../services/api';
import {
  getUserPrivateKey,
  unwrapDek,
  decryptFile,
} from '../services/crypto';
import type { DocumentResponse } from '../types/api';
import type { FileCategory } from '../types/files';
import './MyFilesPage.css';

interface MyFilesPageProps {
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

export const MyFilesPage: React.FC<MyFilesPageProps> = ({ onNavigate }) => {
  const { user, logout } = useAuth();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [files, setFiles] = useState<DocumentResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [downloadingId, setDownloadingId] = useState<string | null>(null);
  const [errorNotice, setErrorNotice] = useState<string | null>(null);

  // Search, filter, and view mode state
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedCategory, setSelectedCategory] = useState<FileCategory>('all');
  const [viewMode, setViewMode] = useState<'list' | 'grid'>('list');

  const fetchFiles = async () => {
    setIsLoading(true);
    try {
      const data = await documentApi.list('owned');
      setFiles(data);
    } catch (err: any) {
      console.warn('[DropSafe MyFiles] Failed to load documents:', err);
      setErrorNotice(err.message || 'Failed to load documents');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchFiles();
  }, []);

  // Format bytes helper
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  // Category matching helper
  const matchesCategory = (file: DocumentResponse, category: FileCategory): boolean => {
    if (category === 'all') return true;
    const ext = file.display_name.split('.').pop()?.toLowerCase() || '';
    const mime = (file.media_type || '').toLowerCase();

    if (category === 'documents') {
      return (
        ['pdf', 'doc', 'docx', 'txt', 'rtf', 'odt', 'xlsx', 'csv'].includes(ext) ||
        mime.includes('text') ||
        mime.includes('pdf') ||
        mime.includes('document')
      );
    }
    if (category === 'images') {
      return (
        ['png', 'jpg', 'jpeg', 'gif', 'svg', 'webp', 'bmp'].includes(ext) ||
        mime.startsWith('image/')
      );
    }
    if (category === 'videos') {
      return (
        ['mp4', 'mov', 'avi', 'mkv', 'webm'].includes(ext) ||
        mime.startsWith('video/')
      );
    }
    if (category === 'audio') {
      return (
        ['mp3', 'wav', 'ogg', 'flac', 'm4a'].includes(ext) ||
        mime.startsWith('audio/')
      );
    }
    return true;
  };

  // Filtered files calculation
  const filteredFiles = useMemo(() => {
    return files.filter((file) => {
      const matchesSearch = file.display_name
        .toLowerCase()
        .includes(searchQuery.trim().toLowerCase());
      const matchesCat = matchesCategory(file, selectedCategory);
      return matchesSearch && matchesCat;
    });
  }, [files, searchQuery, selectedCategory]);

  const resetFilters = () => {
    setSearchQuery('');
    setSelectedCategory('all');
  };

  // Client-Side Zero-Knowledge Download & Decryption
  const handleDownloadAndDecrypt = async (doc: DocumentResponse) => {
    if (!user || !doc.current_version) return;
    setDownloadingId(doc.id);
    setErrorNotice(null);

    try {
      // 1. Get presigned download URL and caller's wrapped DEK
      const downloadInfo = await documentApi.getDownloadUrl(doc.id, doc.current_version.id);

      // 2. Download ciphertext bytes from cloud storage relay
      const ciphertext = await documentApi.fetchCiphertextFromStorage(downloadInfo.download_url);

      // 3. Retrieve user's private RSA encryption key from IndexedDB
      const privKey = await getUserPrivateKey(user.id, 'encryption');
      if (!privKey) {
        throw new Error('Local decryption private key not found in browser storage. Has this browser session expired?');
      }

      // 4. Unwrap Document Encryption Key (DEK)
      const dek = await unwrapDek(downloadInfo.wrapped_dek, privKey);

      // 5. Decrypt ciphertext with AES-256-GCM
      const plaintextBuffer = await decryptFile(ciphertext, dek, downloadInfo.manifest as any);

      // 6. Trigger native browser save dialog
      const blob = new Blob([plaintextBuffer], {
        type: doc.media_type || 'application/octet-stream',
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = doc.display_name;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (err: any) {
      console.error('[DropSafe Decrypt Error]:', err);
      setErrorNotice(`Decryption failed: ${err.message}`);
    } finally {
      setDownloadingId(null);
    }
  };

  const handleDelete = async (docId: string) => {
    if (!window.confirm('Are you sure you want to delete this encrypted document?')) return;
    try {
      await documentApi.delete(docId);
      await fetchFiles();
    } catch (err: any) {
      setErrorNotice(err.message || 'Failed to delete file');
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
            className="ds-sidebar__item ds-sidebar__item--active"
            aria-current="page"
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
            onClick={async () => {
              await logout();
              onNavigate('landing');
            }}
          >
            Log Out
          </button>
        </div>
      </aside>

      {/* Main Files Frame */}
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
              <span
                style={{ cursor: 'pointer' }}
                onClick={() => onNavigate('dashboard')}
              >
                Dashboard
              </span>
              <span aria-hidden="true">/</span>
              <span className="ds-topbar__crumb--active">My Files</span>
            </div>
          </div>

          <div className="ds-topbar__right">
            <button
              type="button"
              className="ds-topbar__upload-btn"
              onClick={() => onNavigate('upload')}
              aria-label="Upload files"
            >
              <PlusIcon size={16} aria-hidden="true" />
              <span>Upload File</span>
            </button>
          </div>
        </header>

        {/* Content Body */}
        <main className="ds-dashboard-content" role="main">
          {/* Section Header */}
          <section className="ds-workspace-header" aria-labelledby="files-heading">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <h1 id="files-heading" className="ds-workspace-title">
                  My Encrypted Files
                </h1>
                <p className="ds-workspace-subtitle">
                  Inspect, decrypt, share, and manage zero-knowledge encrypted documents in your repository.
                </p>
              </div>
              <button
                type="button"
                className="ds-btn ds-btn--secondary"
                onClick={fetchFiles}
                title="Refresh list"
              >
                Refresh
              </button>
            </div>
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

          {/* Controls Toolbar: Search, Filters, View Toggles */}
          <section
            className="ds-files-toolbar"
            aria-label="File search and filtering controls"
          >
            <div className="ds-files-toolbar__top">
              {/* Search Bar */}
              <div className="ds-search-wrapper">
                <SearchIcon size={16} className="ds-search-icon" aria-hidden="true" />
                <input
                  type="text"
                  className="ds-search-input"
                  placeholder="Search files by name..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  aria-label="Search files by name"
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

              {/* View Mode Controls */}
              <div
                className="ds-view-toggle-group"
                role="group"
                aria-label="View layout options"
              >
                <button
                  type="button"
                  className={`ds-view-toggle-btn ${
                    viewMode === 'list' ? 'ds-view-toggle-btn--active' : ''
                  }`}
                  onClick={() => setViewMode('list')}
                  aria-label="List view"
                  aria-pressed={viewMode === 'list'}
                >
                  <ListIcon size={16} aria-hidden="true" />
                </button>
                <button
                  type="button"
                  className={`ds-view-toggle-btn ${
                    viewMode === 'grid' ? 'ds-view-toggle-btn--active' : ''
                  }`}
                  onClick={() => setViewMode('grid')}
                  aria-label="Grid view"
                  aria-pressed={viewMode === 'grid'}
                >
                  <GridIcon size={16} aria-hidden="true" />
                </button>
              </div>
            </div>

            {/* Category Filter Pills */}
            <div
              className="ds-category-filters"
              role="radiogroup"
              aria-label="Filter files by type"
            >
              {(
                [
                  { id: 'all', label: 'All Files' },
                  { id: 'documents', label: 'Documents' },
                  { id: 'images', label: 'Images' },
                  { id: 'videos', label: 'Videos' },
                  { id: 'audio', label: 'Audio' },
                  { id: 'other', label: 'Other' },
                ] as const
              ).map((cat) => (
                <button
                  key={cat.id}
                  type="button"
                  className={`ds-category-pill ${
                    selectedCategory === cat.id ? 'ds-category-pill--active' : ''
                  }`}
                  onClick={() => setSelectedCategory(cat.id)}
                  role="radio"
                  aria-checked={selectedCategory === cat.id}
                >
                  {cat.label}
                </button>
              ))}
            </div>
          </section>

          {/* Files List / Grid or Honest Empty States */}
          {isLoading ? (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--color-text-muted)' }}>
              Loading encrypted repository...
            </div>
          ) : files.length === 0 ? (
            <section
              className="ds-files-empty-panel"
              role="region"
              aria-labelledby="empty-files-heading"
            >
              <div className="ds-files-empty-icon" aria-hidden="true">
                <FolderIcon size={26} />
              </div>
              <h2 id="empty-files-heading" className="ds-files-empty-title">
                No files uploaded yet
              </h2>
              <p className="ds-files-empty-desc">
                Your zero-knowledge encrypted files will appear here once uploaded.
              </p>
              <button
                type="button"
                className="ds-btn ds-btn--primary"
                onClick={() => onNavigate('upload')}
                style={{ marginTop: 'var(--space-2)' }}
              >
                Upload Your First File
              </button>
            </section>
          ) : filteredFiles.length === 0 ? (
            <section
              className="ds-files-empty-panel"
              role="region"
              aria-labelledby="no-matches-heading"
            >
              <div className="ds-files-empty-icon" aria-hidden="true">
                <SearchIcon size={24} />
              </div>
              <h2 id="no-matches-heading" className="ds-files-empty-title">
                No matching files
              </h2>
              <p className="ds-files-empty-desc">
                No files match your current search query or filter selection.
              </p>
              <button
                type="button"
                className="ds-btn ds-btn--secondary"
                onClick={resetFilters}
              >
                Reset Filters
              </button>
            </section>
          ) : viewMode === 'list' ? (
            <div className="ds-files-table-container">
              <table className="ds-files-table">
                <thead>
                  <tr>
                    <th>File</th>
                    <th>Media Type</th>
                    <th>Ciphertext Size</th>
                    <th>Uploaded Date</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredFiles.map((f) => (
                    <tr key={f.id}>
                      <td style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <DocumentIcon size={18} style={{ color: 'var(--color-accent)' }} />
                        <span style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>
                          {f.display_name}
                        </span>
                      </td>
                      <td>{f.media_type || 'binary/encrypted'}</td>
                      <td>{f.current_version ? formatBytes(f.current_version.ciphertext_size_bytes) : 'Pending'}</td>
                      <td>{new Date(f.created_at).toLocaleDateString()}</td>
                      <td style={{ textAlign: 'right' }}>
                        <div style={{ display: 'flex', gap: '6px', justifyContent: 'flex-end' }}>
                          <button
                            type="button"
                            className="ds-btn ds-btn--secondary"
                            style={{ fontSize: '11px', padding: '4px 8px' }}
                            disabled={downloadingId === f.id || !f.current_version}
                            onClick={() => handleDownloadAndDecrypt(f)}
                          >
                            {downloadingId === f.id ? 'Decrypting...' : 'Download & Decrypt'}
                          </button>
                          <button
                            type="button"
                            className="ds-btn ds-btn--ghost"
                            style={{ fontSize: '11px', padding: '4px 8px' }}
                            onClick={() => onNavigate('share')}
                          >
                            Share
                          </button>
                          <button
                            type="button"
                            className="ds-btn ds-btn--ghost"
                            style={{ fontSize: '11px', padding: '4px 8px', color: '#f87171' }}
                            onClick={() => handleDelete(f.id)}
                          >
                            Delete
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="ds-files-grid">
              {filteredFiles.map((f) => (
                <div key={f.id} className="ds-file-grid-card">
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <DocumentIcon size={24} style={{ color: 'var(--color-accent)' }} />
                    <button
                      type="button"
                      style={{ background: 'none', border: 'none', color: '#f87171', cursor: 'pointer', fontSize: '12px' }}
                      onClick={() => handleDelete(f.id)}
                    >
                      Delete
                    </button>
                  </div>
                  <span
                    style={{
                      fontSize: 'var(--text-sm)',
                      fontWeight: 500,
                      color: 'var(--color-text-primary)',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                    title={f.display_name}
                  >
                    {f.display_name}
                  </span>
                  <div
                    style={{
                      display: 'flex',
                      alignItems: 'center',
                      justifyContent: 'space-between',
                      fontSize: 'var(--text-xs)',
                      color: 'var(--color-text-muted)',
                    }}
                  >
                    <span>{f.current_version ? formatBytes(f.current_version.ciphertext_size_bytes) : 'Pending'}</span>
                    <span>{new Date(f.created_at).toLocaleDateString()}</span>
                  </div>
                  <div style={{ marginTop: '10px', display: 'flex', gap: '6px' }}>
                    <button
                      type="button"
                      className="ds-btn ds-btn--secondary"
                      style={{ fontSize: '11px', padding: '4px 8px', width: '100%' }}
                      disabled={downloadingId === f.id || !f.current_version}
                      onClick={() => handleDownloadAndDecrypt(f)}
                    >
                      {downloadingId === f.id ? 'Decrypting...' : 'Decrypt & Save'}
                    </button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </main>
      </div>
    </div>
  );
};
