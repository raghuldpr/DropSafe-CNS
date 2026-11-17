import React, { useState, useEffect } from 'react';
import {
  DashboardIcon,
  FolderIcon,
  ShareIcon,
  ShieldIcon,
  VerifiedIcon,
  SettingsIcon,
  LockIcon,
  KeyIcon,
  UserIcon,
} from '../components/Icons';
import { AdminNavItem } from '../components/AdminNavItem';
import { useAuth } from '../context/AuthContext';
import { userApi } from '../services/api';
import { cryptoService } from '../services/crypto';
import type { PublicKeyRecord } from '../types/api';
import './SettingsPage.css';

interface SettingsPageProps {
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

export const SettingsPage: React.FC<SettingsPageProps> = ({ onNavigate }) => {
  const { user, isAuthenticated, logout, initializeCryptoKeys } = useAuth();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  // Local interactive preferences
  const [confirmDestructive, setConfirmDestructive] = useState<boolean>(true);
  const [compactTables, setCompactTables] = useState<boolean>(false);
  const [showEncryptionDrawer, setShowEncryptionDrawer] = useState<boolean>(true);

  // Live keys state
  const [publicKeys, setPublicKeys] = useState<PublicKeyRecord[]>([]);
  const [hasLocalKeys, setHasLocalKeys] = useState<boolean>(false);
  const [loadingKeys, setLoadingKeys] = useState<boolean>(true);
  const [keyActionMsg, setKeyActionMsg] = useState<string | null>(null);

  const contractAddress =
    import.meta.env.VITE_AUDIT_ANCHOR_CONTRACT_ADDRESS ||
    '0x5FbDB2315678afecb367f032d93F642f64180aa3';
  const rpcUrl = import.meta.env.VITE_BLOCKCHAIN_RPC_URL || 'http://127.0.0.1:8545';
  const chainId = import.meta.env.VITE_CHAIN_ID || '31337';

  useEffect(() => {
    async function loadKeyInfo() {
      if (!isAuthenticated) {
        setLoadingKeys(false);
        return;
      }
      try {
        setLoadingKeys(true);
        const keys = await userApi.getMyKeys();
        setPublicKeys(keys);
        const local = await cryptoService.hasKeys();
        setHasLocalKeys(local);
      } catch (err) {
        console.warn('Failed to load keys in settings', err);
      } finally {
        setLoadingKeys(false);
      }
    }
    loadKeyInfo();
  }, [isAuthenticated]);

  const handleRegenerateKeys = async () => {
    try {
      setKeyActionMsg('Initializing new cryptographic keypair in browser IndexedDB...');
      await initializeCryptoKeys();
      const keys = await userApi.getMyKeys();
      setPublicKeys(keys);
      setHasLocalKeys(true);
      setKeyActionMsg('Successfully registered updated keypair with backend authority.');
      setTimeout(() => setKeyActionMsg(null), 4000);
    } catch (err: any) {
      setKeyActionMsg(`Error: ${err.message || 'Key initialization failed'}`);
    }
  };

  const handleLogout = async () => {
    await logout();
    onNavigate('login');
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
            className="ds-sidebar__item ds-sidebar__item--active"
            aria-current="page"
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
            <span>Connected API</span>
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
            onClick={handleLogout}
          >
            Sign Out
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
              <span className="ds-topbar__crumb--active">Settings</span>
            </nav>
          </div>

          <div className="ds-topbar__right">
            <div className="ds-topbar__session-pill">
              <span className="ds-sidebar__badge-dot" aria-hidden="true" />
              <span>{user ? user.email : 'Connecting...'}</span>
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
        <main className="ds-settings-content" id="main-content">
          {/* Header */}
          <div className="ds-settings-header">
            <div className="ds-settings-header__text">
              <h1 className="ds-settings-header__title">Security & System Settings</h1>
              <p className="ds-settings-header__subtitle">
                Review your cryptographic identity, backend connections, and client-side encryption state.
              </p>
            </div>
          </div>

          {keyActionMsg && (
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
              {keyActionMsg}
            </div>
          )}

          {/* Section 1: Account Information */}
          <section
            className="ds-settings-card"
            role="region"
            aria-labelledby="account-section-heading"
          >
            <div className="ds-settings-card__header">
              <div className="ds-settings-card__header-text">
                <h2 id="account-section-heading" className="ds-settings-card__title">
                  <UserIcon size={18} aria-hidden="true" />
                  Account & ABAC Identity
                </h2>
                <p className="ds-settings-card__desc">
                  Authenticated cryptographic session attributes used for Attribute-Based Access Control evaluation.
                </p>
              </div>
              <span
                className={`ds-settings-badge ${
                  isAuthenticated ? 'ds-settings-badge--active' : 'ds-settings-badge--neutral'
                }`}
              >
                <span className="ds-settings-badge-dot" aria-hidden="true" />
                {isAuthenticated ? 'Active Session' : 'Not Connected'}
              </span>
            </div>

            <div className="ds-settings-grid">
              <div className="ds-settings-field">
                <label htmlFor="settings-name" className="ds-settings-label">
                  Full Name
                </label>
                <input
                  id="settings-name"
                  type="text"
                  className="ds-settings-input"
                  value={user?.display_name || 'Loading user profile...'}
                  readOnly
                  disabled
                />
              </div>

              <div className="ds-settings-field">
                <label htmlFor="settings-email" className="ds-settings-label">
                  Email Address
                </label>
                <input
                  id="settings-email"
                  type="email"
                  className="ds-settings-input"
                  value={user?.email || 'Loading user email...'}
                  readOnly
                  disabled
                />
              </div>

              <div className="ds-settings-field">
                <label htmlFor="settings-dept" className="ds-settings-label">
                  Department
                </label>
                <input
                  id="settings-dept"
                  type="text"
                  className="ds-settings-input"
                  value={user?.department || 'Default'}
                  readOnly
                  disabled
                />
              </div>

              <div className="ds-settings-field">
                <label htmlFor="settings-clearance" className="ds-settings-label">
                  Security Clearance Level
                </label>
                <input
                  id="settings-clearance"
                  type="text"
                  className="ds-settings-input"
                  value={user?.security_clearance || 'STANDARD'}
                  readOnly
                  disabled
                />
              </div>
            </div>

            <div
              style={{
                marginTop: 'var(--space-2)',
                display: 'flex',
                gap: 'var(--space-2)',
                alignItems: 'center',
              }}
            >
              <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
                Assigned Roles:
              </span>
              {user?.roles?.map((r) => (
                <span
                  key={r}
                  className="ds-badge-permission ds-badge-permission--editor"
                  style={{ textTransform: 'uppercase', fontSize: '11px' }}
                >
                  {r}
                </span>
              )) || (
                <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>user</span>
              )}
            </div>
          </section>

          {/* Section 2: Cryptographic Identity & Public Keys */}
          <section
            className="ds-settings-card"
            role="region"
            aria-labelledby="crypto-section-heading"
          >
            <div className="ds-settings-card__header">
              <div className="ds-settings-card__header-text">
                <h2 id="crypto-section-heading" className="ds-settings-card__title">
                  <KeyIcon size={18} aria-hidden="true" />
                  Cryptographic Keys & WebCrypto Keyring
                </h2>
                <p className="ds-settings-card__desc">
                  Client-side RSA-OAEP-3072 encryption keys and ECDSA-P256 signature keys stored securely in IndexedDB.
                </p>
              </div>
              <button
                type="button"
                className="ds-btn ds-btn--secondary"
                onClick={handleRegenerateKeys}
                style={{ fontSize: '12px', padding: '4px 10px' }}
              >
                Re-sync Keypair
              </button>
            </div>

            <div className="ds-security-list">
              <div className="ds-security-item">
                <div className="ds-security-item__left">
                  <span className="ds-security-item__icon" aria-hidden="true">
                    <KeyIcon size={20} />
                  </span>
                  <div className="ds-security-item__content">
                    <span className="ds-security-item__title">
                      Local Browser Keypair Status
                    </span>
                    <p className="ds-security-item__desc">
                      {hasLocalKeys
                        ? 'IndexedDB private key storage initialized. Client-side envelope encryption and zero-knowledge decryption are fully armed.'
                        : 'No local private key found in current browser storage. Click "Re-sync Keypair" to initialize.'}
                    </p>
                  </div>
                </div>
                <div className="ds-security-item__right">
                  <span
                    className={`ds-settings-badge ${
                      hasLocalKeys ? 'ds-settings-badge--active' : 'ds-settings-badge--neutral'
                    }`}
                  >
                    <span className="ds-settings-badge-dot" aria-hidden="true" />
                    {hasLocalKeys ? 'Armed & Persistent' : 'Pending'}
                  </span>
                </div>
              </div>

              <div className="ds-security-item">
                <div className="ds-security-item__left">
                  <span className="ds-security-item__icon" aria-hidden="true">
                    <LockIcon size={20} />
                  </span>
                  <div className="ds-security-item__content">
                    <span className="ds-security-item__title">
                      Public Key Directory Registry ({publicKeys.length} Registered Keys)
                    </span>
                    <p className="ds-security-item__desc">
                      {loadingKeys ? (
                        'Fetching registered public keys...'
                      ) : publicKeys.length > 0 ? (
                        <span>
                          Active Key ID: <code>{publicKeys[0].id}</code> (
                          {publicKeys[0].key_purpose} / {publicKeys[0].algorithm})
                        </span>
                      ) : (
                        'No public keys currently registered on the server.'
                      )}
                    </p>
                  </div>
                </div>
                <div className="ds-security-item__right">
                  <span className="ds-settings-badge ds-settings-badge--active">
                    <span className="ds-settings-badge-dot" aria-hidden="true" />
                    Public Directory
                  </span>
                </div>
              </div>
            </div>
          </section>

          {/* Section 3: Blockchain Audit Anchoring */}
          <section
            className="ds-settings-card"
            role="region"
            aria-labelledby="blockchain-section-heading"
          >
            <div className="ds-settings-card__header">
              <div className="ds-settings-card__header-text">
                <h2 id="blockchain-section-heading" className="ds-settings-card__title">
                  <VerifiedIcon size={18} aria-hidden="true" />
                  Blockchain Audit Anchor
                </h2>
                <p className="ds-settings-card__desc">
                  On-chain immutability parameters anchored via smart contract <code>AuditAnchor.sol</code>.
                </p>
              </div>
              <span className="ds-settings-badge ds-settings-badge--active">
                <span className="ds-settings-badge-dot" aria-hidden="true" />
                Chain ID {chainId}
              </span>
            </div>

            <div className="ds-settings-grid">
              <div className="ds-settings-field">
                <label className="ds-settings-label">Smart Contract Address</label>
                <input
                  type="text"
                  className="ds-settings-input"
                  value={contractAddress}
                  readOnly
                  disabled
                />
              </div>

              <div className="ds-settings-field">
                <label className="ds-settings-label">EVM RPC Endpoint</label>
                <input
                  type="text"
                  className="ds-settings-input"
                  value={rpcUrl}
                  readOnly
                  disabled
                />
              </div>
            </div>
          </section>

          {/* Section 4: Interface & Local Preferences */}
          <section
            className="ds-settings-card"
            role="region"
            aria-labelledby="preferences-section-heading"
          >
            <div className="ds-settings-card__header">
              <div className="ds-settings-card__header-text">
                <h2 id="preferences-section-heading" className="ds-settings-card__title">
                  <SettingsIcon size={18} aria-hidden="true" />
                  Interface Preferences
                </h2>
                <p className="ds-settings-card__desc">
                  Customize client-side presentation and interaction preferences.
                </p>
              </div>
            </div>

            <div className="ds-preferences-list">
              <div className="ds-preference-item">
                <div className="ds-preference-item__content">
                  <span className="ds-preference-item__title">
                    Confirm Before Destructive Actions
                  </span>
                  <p className="ds-preference-item__desc">
                    Display an explicit confirmation modal before deleting files or removing shared access links.
                  </p>
                </div>
                <label className="ds-switch-label" htmlFor="pref-confirm-destructive">
                  <input
                    id="pref-confirm-destructive"
                    type="checkbox"
                    className="ds-switch-input"
                    checked={confirmDestructive}
                    onChange={(e) => setConfirmDestructive(e.target.checked)}
                    role="switch"
                  />
                  <span className="ds-switch-track">
                    <span className="ds-switch-thumb" />
                  </span>
                </label>
              </div>

              <div className="ds-preference-item">
                <div className="ds-preference-item__content">
                  <span className="ds-preference-item__title">Compact Table Density</span>
                  <p className="ds-preference-item__desc">
                    Reduce vertical padding in file lists and audit tables.
                  </p>
                </div>
                <label className="ds-switch-label" htmlFor="pref-compact-tables">
                  <input
                    id="pref-compact-tables"
                    type="checkbox"
                    className="ds-switch-input"
                    checked={compactTables}
                    onChange={(e) => setCompactTables(e.target.checked)}
                    role="switch"
                  />
                  <span className="ds-switch-track">
                    <span className="ds-switch-thumb" />
                  </span>
                </label>
              </div>

              <div className="ds-preference-item">
                <div className="ds-preference-item__content">
                  <span className="ds-preference-item__title">
                    Auto-Expand Cryptographic Metadata
                  </span>
                  <p className="ds-preference-item__desc">
                    Automatically expand cryptographic checksums, cipher parameters, and Merkle proofs.
                  </p>
                </div>
                <label className="ds-switch-label" htmlFor="pref-show-drawer">
                  <input
                    id="pref-show-drawer"
                    type="checkbox"
                    className="ds-switch-input"
                    checked={showEncryptionDrawer}
                    onChange={(e) => setShowEncryptionDrawer(e.target.checked)}
                    role="switch"
                  />
                  <span className="ds-switch-track">
                    <span className="ds-switch-thumb" />
                  </span>
                </label>
              </div>
            </div>
          </section>

          {/* Section 5: Session Termination */}
          <section className="ds-settings-card" role="region">
            <div className="ds-settings-card__header">
              <div className="ds-settings-card__header-text">
                <h2 className="ds-settings-card__title">
                  <LockIcon size={18} aria-hidden="true" />
                  Session Revocation
                </h2>
                <p className="ds-settings-card__desc">
                  Invalidate your access token, clear cached session cookies, and exit to the landing screen.
                </p>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'flex-end', paddingTop: 'var(--space-2)' }}>
              <button
                type="button"
                className="ds-btn ds-btn--secondary"
                onClick={handleLogout}
              >
                Sign Out of DropSafe
              </button>
            </div>
          </section>
        </main>
      </div>
    </div>
  );
};

export default SettingsPage;
