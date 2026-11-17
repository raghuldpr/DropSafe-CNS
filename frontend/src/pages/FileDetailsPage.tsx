import { AdminNavItem } from '../components/AdminNavItem';
import React, { useState, useEffect } from 'react';
import {
  DashboardIcon,
  FolderIcon,
  ShareIcon,
  ShieldIcon,
  VerifiedIcon,
  SettingsIcon,
  DocumentIcon,
  ArrowLeftIcon,
  DownloadIcon,
  TrashIcon,
} from '../components/Icons';
import { documentApi, sharingApi } from '../services/api';
import { cryptoService } from '../services/crypto';
import type { DocumentItem, DocumentAccessOverview } from '../types/api';
import './FileDetailsPage.css';

interface FileDetailsPageProps {
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

export const FileDetailsPage: React.FC<FileDetailsPageProps> = ({
  onNavigate,
  selectedFiles = [],
}) => {
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [fileIdParam, setFileIdParam] = useState<string | null>(null);

  // Live document state
  const [document, setDocument] = useState<DocumentItem | null>(null);
  const [accessOverview, setAccessOverview] = useState<DocumentAccessOverview | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [downloading, setDownloading] = useState<boolean>(false);
  const [downloadStatus, setDownloadStatus] = useState<string | null>(null);

  // Extract query parameters from hash (e.g., #/file-details?id=123)
  useEffect(() => {
    const parseHashParams = () => {
      const hash = window.location.hash;
      const queryIndex = hash.indexOf('?');
      if (queryIndex !== -1) {
        const queryString = hash.substring(queryIndex + 1);
        const params = new URLSearchParams(queryString);
        setFileIdParam(params.get('id'));
      } else {
        setFileIdParam(null);
      }
    };

    parseHashParams();
    window.addEventListener('hashchange', parseHashParams);
    return () => window.removeEventListener('hashchange', parseHashParams);
  }, []);

  // Fetch document details when fileIdParam is set
  useEffect(() => {
    async function fetchDoc() {
      if (!fileIdParam) {
        setLoading(false);
        return;
      }
      try {
        setLoading(true);
        setError(null);
        const doc = await documentApi.get(fileIdParam);
        setDocument(doc);

        try {
          const overview = await sharingApi.getDocumentAccess(fileIdParam);
          setAccessOverview(overview);
        } catch {
          // May fail if caller is not owner; ignore
        }
      } catch (err: any) {
        console.error('Failed to load document details:', err);
        setError(err.message || 'Failed to fetch document metadata.');
      } finally {
        setLoading(false);
      }
    }

    fetchDoc();
  }, [fileIdParam]);

  // Format bytes helper
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  // Zero-Knowledge Decrypt & Download
  const handleDecryptAndDownload = async () => {
    if (!document) return;
    try {
      setDownloading(true);
      setDownloadStatus('Requesting presigned storage ticket...');
      const downloadInfo = await documentApi.getDownloadUrl(document.id, document.current_version?.id);

      setDownloadStatus('Fetching ciphertext stream from storage backend...');
      const response = await fetch(downloadInfo.download_url);
      if (!response.ok) {
        throw new Error(`Failed to retrieve ciphertext: ${response.statusText}`);
      }
      const encryptedBuffer = await response.arrayBuffer();

      setDownloadStatus('Unwrapping AES-256-GCM data encryption key with client private key...');
      const dek = await cryptoService.unwrapKey(downloadInfo.wrapped_dek);

      setDownloadStatus('Executing client-side zero-knowledge AES-256-GCM decryption...');
      const decryptedBytes = await cryptoService.decryptFile(
        encryptedBuffer,
        dek,
        { iv_base64: downloadInfo.manifest.iv_base64 }
      );

      setDownloadStatus('Triggering secure browser download...');
      const blob = new Blob([decryptedBytes], { type: document.media_type || 'application/octet-stream' });
      const url = URL.createObjectURL(blob);
      const a = window.document.createElement('a');
      a.href = url;
      a.download = document.display_name;
      window.document.body.appendChild(a);
      a.click();
      window.document.body.removeChild(a);
      URL.revokeObjectURL(url);
      setDownloadStatus('Download complete!');
      setTimeout(() => setDownloadStatus(null), 3000);
    } catch (err: any) {
      console.error('Decryption failed:', err);
      setDownloadStatus(`Error: ${err.message || 'Decryption failed'}`);
    } finally {
      setDownloading(false);
    }
  };

  const handleDelete = async () => {
    if (!document) return;
    if (!confirm(`Are you sure you want to delete ${document.display_name}?`)) return;
    try {
      await documentApi.delete(document.id);
      onNavigate('files');
    } catch (err: any) {
      alert(`Deletion failed: ${err.message}`);
    }
  };

  const localFile = selectedFiles.length > 0 ? selectedFiles[0] : null;

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
            className="ds-sidebar__item ds-sidebar__item--active"
            onClick={() => onNavigate('files')}
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
            <span>Encrypted Ledger</span>
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
                onClick={() => onNavigate('files')}
              >
                My Files
              </button>
              <span aria-hidden="true">/</span>
              <span className="ds-topbar__crumb--active">File Details</span>
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

        {/* File Details Content */}
        <main className="ds-file-details-content" id="main-content">
          <div className="ds-details-header">
            <div className="ds-details-header__text">
              <h1 className="ds-details-header__title">
                {document ? document.display_name : 'File Details'}
              </h1>
              <p className="ds-details-header__subtitle">
                Review cryptographic envelope metadata, ABAC policy status, and audit commitments.
              </p>
            </div>

            <button
              type="button"
              className="ds-details-back-btn"
              onClick={() => onNavigate('files')}
              aria-label="Return to My Files"
            >
              <ArrowLeftIcon size={16} aria-hidden="true" />
              <span>Back to My Files</span>
            </button>
          </div>

          {loading ? (
            <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--color-text-muted)' }}>
              Loading cryptographic document properties...
            </div>
          ) : error ? (
            <div className="ds-details-empty-card">
              <h2 className="ds-details-empty-title">Document Not Found</h2>
              <p className="ds-details-empty-desc">{error}</p>
              <button
                type="button"
                className="ds-btn ds-btn--primary"
                onClick={() => onNavigate('files')}
              >
                Back to My Files
              </button>
            </div>
          ) : document ? (
            <>
              {downloadStatus && (
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
                  {downloadStatus}
                </div>
              )}

              {/* Summary Card */}
              <section className="ds-file-summary-card" aria-label="File overview">
                <div className="ds-file-summary-left">
                  <div className="ds-file-summary-icon" aria-hidden="true">
                    <DocumentIcon size={28} />
                  </div>
                  <div className="ds-file-summary-info">
                    <h2 className="ds-file-summary-name">{document.display_name}</h2>
                    <div className="ds-file-summary-meta">
                      <span>{formatBytes(document.current_version?.ciphertext_size_bytes || 0)}</span>
                      <span aria-hidden="true">•</span>
                      <span>{document.media_type || 'application/octet-stream'}</span>
                      <span aria-hidden="true">•</span>
                      <span className="ds-file-summary-pill ds-file-summary-pill--local">
                        Version {document.current_version?.version_number || 1}
                      </span>
                    </div>
                  </div>
                </div>

                <div className="ds-file-summary-actions">
                  <button
                    type="button"
                    className="ds-btn ds-btn--primary"
                    onClick={handleDecryptAndDownload}
                    disabled={downloading}
                  >
                    <DownloadIcon size={16} aria-hidden="true" />
                    <span>{downloading ? 'Decrypting...' : 'Decrypt & Download'}</span>
                  </button>

                  <button
                    type="button"
                    className="ds-btn ds-btn--secondary"
                    onClick={() => {
                      window.location.hash = `#/share?id=${document.id}`;
                    }}
                  >
                    <ShareIcon size={16} aria-hidden="true" />
                    <span>Share File</span>
                  </button>

                  <button
                    type="button"
                    className="ds-btn ds-btn--secondary"
                    onClick={() => {
                      window.location.hash = `#/policies?id=${document.id}`;
                    }}
                  >
                    <ShieldIcon size={16} aria-hidden="true" />
                    <span>ABAC Policy</span>
                  </button>

                  <button
                    type="button"
                    className="ds-btn ds-btn--danger"
                    onClick={handleDelete}
                    title="Delete document"
                  >
                    <TrashIcon size={16} aria-hidden="true" />
                  </button>
                </div>
              </section>

              {/* Information Grid */}
              <div className="ds-details-grid">
                {/* File Information */}
                <section className="ds-details-section">
                  <div className="ds-details-section__header">
                    <h3 className="ds-details-section__title">
                      <DocumentIcon size={18} aria-hidden="true" />
                      <span>Document Record</span>
                    </h3>
                    <span className="ds-details-section__badge">Cloud Storage</span>
                  </div>

                  <div className="ds-meta-list">
                    <div className="ds-meta-row">
                      <span className="ds-meta-label">Document ID</span>
                      <span className="ds-meta-value" style={{ fontFamily: 'monospace', fontSize: '12px' }}>
                        {document.id}
                      </span>
                    </div>
                    <div className="ds-meta-row">
                      <span className="ds-meta-label">Ciphertext Size</span>
                      <span className="ds-meta-value">
                        {formatBytes(document.current_version?.ciphertext_size_bytes || 0)}
                      </span>
                    </div>
                    <div className="ds-meta-row">
                      <span className="ds-meta-label">Classification</span>
                      <span className="ds-meta-value" style={{ textTransform: 'uppercase' }}>
                        Standard
                      </span>
                    </div>
                    <div className="ds-meta-row">
                      <span className="ds-meta-label">Created At</span>
                      <span className="ds-meta-value">
                        {new Date(document.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div className="ds-meta-row">
                      <span className="ds-meta-label">Active Grants</span>
                      <span className="ds-meta-value">
                        {accessOverview ? `${accessOverview.grants.length} Recipients` : 'Owner Only'}
                      </span>
                    </div>
                  </div>
                </section>

                {/* Cryptographic Envelope Information */}
                <section className="ds-details-section">
                  <div className="ds-details-section__header">
                    <h3 className="ds-details-section__title">
                      <ShieldIcon size={18} aria-hidden="true" />
                      <span>Zero-Knowledge Envelope</span>
                    </h3>
                    <span className="ds-details-section__badge">Verified</span>
                  </div>

                  <div className="ds-meta-list">
                    <div className="ds-meta-row">
                      <span className="ds-meta-label">Payload Cipher</span>
                      <span className="ds-meta-value">AES-256-GCM (12-byte IV)</span>
                    </div>
                    <div className="ds-meta-row">
                      <span className="ds-meta-label">DEK Envelope</span>
                      <span className="ds-meta-value">RSA-OAEP-3072 / SHA-256</span>
                    </div>
                    <div className="ds-meta-row">
                      <span className="ds-meta-label">SHA-256 Digest</span>
                      <span
                        className="ds-meta-value"
                        style={{ fontFamily: 'monospace', fontSize: '11px', wordBreak: 'break-all' }}
                      >
                        {document.current_version?.ciphertext_sha256_hex || 'Calculated during upload'}
                      </span>
                    </div>
                    <div className="ds-meta-row">
                      <span className="ds-meta-label">Ledger Anchoring</span>
                      <span className="ds-meta-value">
                        Anchored in SHA-256 Hash Chain
                      </span>
                    </div>
                  </div>
                </section>
              </div>
            </>
          ) : localFile ? (
            /* Selected in upload buffer */
            <section className="ds-file-summary-card">
              <div className="ds-file-summary-left">
                <div className="ds-file-summary-icon">
                  <DocumentIcon size={28} />
                </div>
                <div className="ds-file-summary-info">
                  <h2 className="ds-file-summary-name">{localFile.name}</h2>
                  <div className="ds-file-summary-meta">
                    <span>{formatBytes(localFile.size)}</span>
                    <span aria-hidden="true">•</span>
                    <span>Local File Buffer</span>
                  </div>
                </div>
              </div>
              <div className="ds-file-summary-actions">
                <button
                  type="button"
                  className="ds-btn ds-btn--primary"
                  onClick={() => onNavigate('upload-progress')}
                >
                  Encrypt & Upload to Cloud
                </button>
              </div>
            </section>
          ) : (
            <section className="ds-details-empty-card">
              <DocumentIcon size={28} />
              <h2 className="ds-details-empty-title">No Document Specified</h2>
              <p className="ds-details-empty-desc">
                Select a document from your files list or upload a new file.
              </p>
              <div className="ds-details-empty-actions">
                <button
                  type="button"
                  className="ds-btn ds-btn--primary"
                  onClick={() => onNavigate('files')}
                >
                  Go to My Files
                </button>
              </div>
            </section>
          )}
        </main>
      </div>
    </div>
  );
};

export default FileDetailsPage;
