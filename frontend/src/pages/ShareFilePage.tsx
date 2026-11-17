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
} from '../components/Icons';
import { AdminNavItem } from '../components/AdminNavItem';
import { useAuth } from '../context/AuthContext';
import { documentApi, userApi, sharingApi } from '../services/api';
import {
  getUserPrivateKey,
  unwrapDek,
  wrapDek,
} from '../services/crypto';
import type { DocumentResponse, UserKeyDirectoryResponse } from '../types/api';
import './ShareFilePage.css';

export type AccessLevel = 'viewer' | 'download';

interface ShareFilePageProps {
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

export const ShareFilePage: React.FC<ShareFilePageProps> = ({
  onNavigate,
}) => {
  const { user, logout } = useAuth();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  // File selection
  const [ownedDocs, setOwnedDocs] = useState<DocumentResponse[]>([]);
  const [selectedDocId, setSelectedDocId] = useState<string>('');
  const [isLoadingDocs, setIsLoadingDocs] = useState(true);

  // Form states
  const [recipientEmail, setRecipientEmail] = useState('');
  const [emailError, setEmailError] = useState<string | null>(null);
  const [accessLevel, setAccessLevel] = useState<AccessLevel>('download');
  const [expiryEnabled, setExpiryEnabled] = useState(false);
  const [expiryDate, setExpiryDate] = useState('');
  const [dateError, setDateError] = useState<string | null>(null);

  // Progress and submission state
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [statusNotice, setStatusNotice] = useState<{ type: 'success' | 'error'; message: string } | null>(null);

  const [todayString] = useState(() => new Date().toISOString().split('T')[0]);

  useEffect(() => {
    const fetchDocs = async () => {
      try {
        const docs = await documentApi.list('owned');
        setOwnedDocs(docs);
        if (docs.length > 0) {
          setSelectedDocId(docs[0].id);
        }
      } catch (err) {
        console.warn('Failed to load owned docs for sharing:', err);
      } finally {
        setIsLoadingDocs(false);
      }
    };
    fetchDocs();
  }, []);

  const selectedDoc = ownedDocs.find((d) => d.id === selectedDocId);

  const validateForm = (): boolean => {
    let isValid = true;
    if (!selectedDocId) {
      setStatusNotice({ type: 'error', message: 'Please select a document to share.' });
      return false;
    }

    const trimmed = recipientEmail.trim();
    if (!trimmed) {
      setEmailError('Please enter a recipient email address.');
      isValid = false;
    } else {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(trimmed)) {
        setEmailError('Please enter a valid email address.');
        isValid = false;
      } else {
        setEmailError(null);
      }
    }

    if (expiryEnabled && !expiryDate) {
      setDateError('Please specify an expiration date.');
      isValid = false;
    } else {
      setDateError(null);
    }

    return isValid;
  };

  const handleShare = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validateForm() || !user || !selectedDoc) return;

    setIsSubmitting(true);
    setStatusNotice(null);

    try {
      // 1. Recipient Directory Lookup
      let recipient: UserKeyDirectoryResponse;
      try {
        recipient = await userApi.lookupByEmail(recipientEmail.trim());
      } catch (lookupErr: any) {
        throw new Error(`Recipient not found: ${lookupErr.message}`);
      }

      const recipientEncKey = recipient.active_keys.find((k) => k.key_purpose === 'encryption');
      if (!recipientEncKey) {
        throw new Error(`Recipient (${recipient.email}) has not registered an encryption key yet.`);
      }

      // 2. Pre-flight ABAC Policy Evaluation
      const evalResult = await sharingApi.evaluateAccess(selectedDoc.id, recipient.user_id);
      if (!evalResult.eligible) {
        throw new Error(
          `Recipient is not eligible under active document ABAC policy: ${evalResult.reasons.join(', ')}`
        );
      }

      // 3. Retrieve caller's wrapped DEK
      if (!selectedDoc.current_version) {
        throw new Error('This document does not have an active version uploaded yet.');
      }
      const downloadInfo = await documentApi.getDownloadUrl(selectedDoc.id, selectedDoc.current_version.id);

      // 4. Unwrap DEK using owner private key
      const ownerPrivKey = await getUserPrivateKey(user.id, 'encryption');
      if (!ownerPrivKey) {
        throw new Error('Owner decryption key missing from browser store.');
      }
      const rawDek = await unwrapDek(downloadInfo.wrapped_dek, ownerPrivKey);

      // 5. Re-wrap DEK for recipient's RSA-OAEP public key
      const recipientWrappedDekB64 = await wrapDek(rawDek, recipientEncKey.public_key_jwk);

      // 6. Commit Access Grant to Backend
      const permissions = accessLevel === 'viewer' ? ['read'] : ['read', 'download'];
      const expiresAtIso = expiryEnabled && expiryDate ? new Date(expiryDate).toISOString() : undefined;

      await sharingApi.createGrant(
        selectedDoc.id,
        recipient.user_id,
        recipientWrappedDekB64,
        recipientEncKey.id,
        permissions,
        expiresAtIso
      );

      setStatusNotice({
        type: 'success',
        message: `Successfully shared "${selectedDoc.display_name}" with ${recipient.email}! DEK envelope re-wrapped with recipient's public key.`,
      });
      setRecipientEmail('');
    } catch (err: any) {
      console.error('[DropSafe Share Error]:', err);
      setStatusNotice({
        type: 'error',
        message: err.message || 'Failed to share document.',
      });
    } finally {
      setIsSubmitting(false);
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

      {/* Main Area */}
      <div className="ds-dashboard-main">
        {/* Top Bar */}
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

            <nav className="ds-topbar__breadcrumb" aria-label="Breadcrumb">
              <span style={{ cursor: 'pointer' }} onClick={() => onNavigate('dashboard')}>
                Dashboard
              </span>
              <span aria-hidden="true">/</span>
              <span style={{ cursor: 'pointer' }} onClick={() => onNavigate('files')}>
                My Files
              </span>
              <span aria-hidden="true">/</span>
              <span className="ds-topbar__crumb--active">Share File</span>
            </nav>
          </div>
        </header>

        {/* Share File Content */}
        <main className="ds-dashboard-content" id="main-content">
          <div className="ds-share-header">
            <div className="ds-share-header__text">
              <h1 className="ds-share-header__title">Share Encrypted File</h1>
              <p className="ds-share-header__subtitle">
                Grant access to eligible recipients with automated cryptographic key wrapping and ABAC enforcement.
              </p>
            </div>

            <button
              type="button"
              className="ds-share-back-btn"
              onClick={() => onNavigate('files')}
              aria-label="Return to My Files"
            >
              <ArrowLeftIcon size={16} aria-hidden="true" />
              <span>Back to My Files</span>
            </button>
          </div>

          {/* Status / Alert Banner */}
          {statusNotice && (
            <div
              style={{
                marginBottom: '20px',
                padding: '12px 16px',
                borderRadius: '8px',
                background: statusNotice.type === 'success' ? 'rgba(74, 222, 128, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                border: `1px solid ${statusNotice.type === 'success' ? 'rgba(74, 222, 128, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                color: statusNotice.type === 'success' ? '#4ade80' : '#f87171',
                fontSize: '13px',
              }}
              role="alert"
            >
              <strong>{statusNotice.type === 'success' ? 'Success:' : 'Sharing Denied:'}</strong> {statusNotice.message}
            </div>
          )}

          {isLoadingDocs ? (
            <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--color-text-muted)' }}>
              Loading repository documents...
            </div>
          ) : ownedDocs.length === 0 ? (
            <section className="ds-share-empty-card" role="region">
              <div className="ds-share-empty-icon" aria-hidden="true">
                <DocumentIcon size={28} />
              </div>
              <h2 className="ds-share-empty-title">No files to share</h2>
              <p className="ds-share-empty-desc">
                You have not uploaded any files yet. Upload a file to begin sharing.
              </p>
              <div className="ds-share-empty-actions">
                <button
                  type="button"
                  className="ds-btn ds-btn--primary"
                  onClick={() => onNavigate('upload')}
                >
                  Upload a File
                </button>
              </div>
            </section>
          ) : (
            <form className="ds-share-form-card" onSubmit={handleShare} noValidate>
              {/* Document Selection */}
              <section className="ds-share-section">
                <label className="ds-share-label">Select Document to Share</label>
                <select
                  value={selectedDocId}
                  onChange={(e) => setSelectedDocId(e.target.value)}
                  style={{
                    width: '100%',
                    padding: '10px 14px',
                    borderRadius: '8px',
                    background: 'rgba(255,255,255,0.05)',
                    border: '1px solid rgba(255,255,255,0.1)',
                    color: '#fff',
                    fontSize: '14px',
                  }}
                >
                  {ownedDocs.map((doc) => (
                    <option key={doc.id} value={doc.id} style={{ background: '#1e293b' }}>
                      {doc.display_name} ({doc.current_version ? `${doc.current_version.ciphertext_size_bytes} bytes` : 'pending'})
                    </option>
                  ))}
                </select>
              </section>

              {/* Recipient Email */}
              <section className="ds-share-section">
                <h2 className="ds-share-section__title">Recipient Identity</h2>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label htmlFor="recipient-email-input" className="ds-share-label">
                    Recipient Email Address
                  </label>
                  <input
                    id="recipient-email-input"
                    type="email"
                    placeholder="e.g. bob@dropsafe.local"
                    value={recipientEmail}
                    onChange={(e) => {
                      setRecipientEmail(e.target.value);
                      if (emailError) setEmailError(null);
                    }}
                    className={`ds-share-input ${emailError ? 'ds-share-input--error' : ''}`}
                    disabled={isSubmitting}
                  />
                  {emailError && <span className="ds-share-error-msg">{emailError}</span>}

                  {/* Demo Helper Pills */}
                  <div style={{ display: 'flex', gap: '8px', marginTop: '6px' }}>
                    <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>Quick Recipient:</span>
                    <button
                      type="button"
                      style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#93c5fd', cursor: 'pointer' }}
                      onClick={() => setRecipientEmail('bob@dropsafe.local')}
                    >
                      bob@dropsafe.local (Finance)
                    </button>
                    <button
                      type="button"
                      style={{ fontSize: '11px', padding: '2px 8px', borderRadius: '4px', background: 'rgba(255,255,255,0.05)', border: '1px solid rgba(255,255,255,0.1)', color: '#93c5fd', cursor: 'pointer' }}
                      onClick={() => setRecipientEmail('charlie@dropsafe.local')}
                    >
                      charlie@dropsafe.local (Engineering)
                    </button>
                  </div>
                </div>
              </section>

              {/* Access Permissions */}
              <section className="ds-share-section">
                <h2 className="ds-share-section__title">Permissions</h2>
                <div className="ds-access-options-grid">
                  <label className={`ds-access-card ${accessLevel === 'download' ? 'ds-access-card--selected' : ''}`}>
                    <input
                      type="radio"
                      name="access-level"
                      value="download"
                      checked={accessLevel === 'download'}
                      onChange={() => setAccessLevel('download')}
                      className="ds-access-radio"
                    />
                    <div className="ds-access-card-body">
                      <span className="ds-access-card-label">Download &amp; Decrypt</span>
                      <span className="ds-access-card-desc">Can unwrap DEK and download the decrypted file.</span>
                    </div>
                  </label>
                  <label className={`ds-access-card ${accessLevel === 'viewer' ? 'ds-access-card--selected' : ''}`}>
                    <input
                      type="radio"
                      name="access-level"
                      value="viewer"
                      checked={accessLevel === 'viewer'}
                      onChange={() => setAccessLevel('viewer')}
                      className="ds-access-radio"
                    />
                    <div className="ds-access-card-body">
                      <span className="ds-access-card-label">Read Only</span>
                      <span className="ds-access-card-desc">Can view file metadata and presence in shared directory.</span>
                    </div>
                  </label>
                </div>
              </section>

              {/* Expiry */}
              <section className="ds-share-section">
                <h2 className="ds-share-section__title">Access Expiry</h2>
                <label className="ds-expiry-toggle-row">
                  <input
                    type="checkbox"
                    checked={expiryEnabled}
                    onChange={(e) => setExpiryEnabled(e.target.checked)}
                    className="ds-expiry-checkbox"
                  />
                  <span className="ds-expiry-toggle-label">Set an expiration date</span>
                </label>
                {expiryEnabled && (
                  <div className="ds-expiry-date-wrapper" style={{ marginTop: '8px' }}>
                    <input
                      type="date"
                      min={todayString}
                      value={expiryDate}
                      onChange={(e) => setExpiryDate(e.target.value)}
                      className={`ds-share-date-input ${dateError ? 'ds-share-input--error' : ''}`}
                    />
                    {dateError && <span className="ds-share-error-msg">{dateError}</span>}
                  </div>
                )}
              </section>

              {/* Submit Buttons */}
              <div className="ds-share-actions-row">
                <button
                  type="button"
                  className="ds-btn ds-btn--secondary"
                  onClick={() => onNavigate('files')}
                  disabled={isSubmitting}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="ds-btn ds-btn--primary"
                  disabled={isSubmitting}
                >
                  {isSubmitting ? 'Evaluating ABAC & Wrapping Key...' : 'Share File'}
                </button>
              </div>
            </form>
          )}
        </main>
      </div>
    </div>
  );
};
