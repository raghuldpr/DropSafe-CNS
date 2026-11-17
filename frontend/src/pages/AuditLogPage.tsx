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
} from '../components/Icons';
import { AdminNavItem } from '../components/AdminNavItem';
import { useAuth } from '../context/AuthContext';
import { auditApi } from '../services/api';
import { verifyBatchOnChain, type OnChainVerificationResult } from '../services/blockchain';
import type { ApiAuditEventResponse, AuditBatchResponse, MerkleProofResponse } from '../types/api';
import './AuditLogPage.css';

interface AuditLogPageProps {
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

export const AuditLogPage: React.FC<AuditLogPageProps> = ({ onNavigate }) => {
  const { user, logout } = useAuth();
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  // Active Tab
  const [activeTab, setActiveTab] = useState<'events' | 'batches'>('events');

  // Ledger state
  const [events, setEvents] = useState<ApiAuditEventResponse[]>([]);
  const [batches, setBatches] = useState<AuditBatchResponse[]>([]);
  const [isLoading, setIsLoading] = useState(true);

  // Search & filter state
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedFilter, setSelectedFilter] = useState<string>('all');

  // Chain verification state
  const [chainValidating, setChainValidating] = useState(false);
  const [chainStatus, setChainStatus] = useState<{ valid: boolean; checked: number } | null>(null);

  // Proof & On-Chain verification modal state
  const [inspectEvent, setInspectEvent] = useState<ApiAuditEventResponse | null>(null);
  const [inspectBatch, setInspectBatch] = useState<AuditBatchResponse | null>(null);
  const [proofLoading, setProofLoading] = useState(false);
  const [proofData, setProofData] = useState<MerkleProofResponse | null>(null);
  const [onChainResult, setOnChainResult] = useState<OnChainVerificationResult | null>(null);

  const fetchAuditData = async () => {
    setIsLoading(true);
    try {
      const [evData, batchData] = await Promise.all([
        auditApi.listEvents(1, 50),
        auditApi.listBatches(1, 20),
      ]);
      setEvents(evData);
      setBatches(batchData);
    } catch (err) {
      console.warn('Failed to load audit data:', err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAuditData();
  }, []);

  const [sealing, setSealing] = useState(false);
  const handleSealBatch = async () => {
    setSealing(true);
    try {
      const batch = await auditApi.createBatch();
      if (!batch) alert('No new audit events to seal yet. Perform some actions first.');
      setActiveTab('batches');
      await fetchAuditData();
      // The background worker anchors on-chain within a few seconds; refresh to show it.
      setTimeout(fetchAuditData, 5000);
    } catch (err: any) {
      alert(`Failed to seal batch: ${err.message}`);
    } finally {
      setSealing(false);
    }
  };

  const handleVerifyChain = async () => {
    setChainValidating(true);
    try {
      const result = await auditApi.verifyChain();
      setChainStatus({ valid: result.chain_valid, checked: result.checked_events });
    } catch (err: any) {
      alert(`Hash chain verification failed: ${err.message}`);
    } finally {
      setChainValidating(false);
    }
  };

  const handleInspectProof = async (event: ApiAuditEventResponse) => {
    setInspectEvent(event);
    setProofData(null);
    setOnChainResult(null);

    if (!event.batch_id) return;
    setProofLoading(true);

    try {
      const batch = batches.find((b) => b.id === event.batch_id) || (await auditApi.getBatch(event.batch_id));
      setInspectBatch(batch);

      const proof = await auditApi.getEventProof(event.batch_id, event.id);
      setProofData(proof);

      // Perform direct on-chain verification
      const onChain = await verifyBatchOnChain(batch.batch_number, proof.merkle_root_hex);
      setOnChainResult(onChain);
    } catch (err: any) {
      console.warn('Proof fetch failed:', err);
    } finally {
      setProofLoading(false);
    }
  };

  const filteredEvents = useMemo(() => {
    return events.filter((ev) => {
      const matchesSearch =
        ev.event_type.toLowerCase().includes(searchQuery.trim().toLowerCase()) ||
        ev.event_hash_hex.toLowerCase().includes(searchQuery.trim().toLowerCase()) ||
        (ev.actor_user_id && ev.actor_user_id.toLowerCase().includes(searchQuery.trim().toLowerCase()));

      const matchesFilter = selectedFilter === 'all' ? true : ev.event_type.startsWith(selectedFilter);
      return matchesSearch && matchesFilter;
    });
  }, [events, searchQuery, selectedFilter]);

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
            className="ds-sidebar__item ds-sidebar__item--active"
            aria-current="page"
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

      {/* Main Content Frame */}
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
              <span className="ds-topbar__crumb--active">Audit Ledger</span>
            </div>
          </div>

          <div className="ds-topbar__right" style={{ display: 'flex', gap: '8px' }}>
            <button
              type="button"
              className="ds-btn ds-btn--secondary"
              style={{ fontSize: '12px', padding: '6px 12px' }}
              disabled={chainValidating}
              onClick={handleVerifyChain}
            >
              {chainValidating ? 'Verifying Hash Chain...' : 'Verify Hash Chain'}
            </button>
            <button
              type="button"
              className="ds-btn ds-btn--secondary"
              style={{ fontSize: '12px', padding: '6px 12px' }}
              disabled={sealing}
              onClick={handleSealBatch}
            >
              {sealing ? 'Sealing...' : 'Seal & Anchor Batch'}
            </button>
            <button
              type="button"
              className="ds-btn ds-btn--secondary"
              style={{ fontSize: '12px', padding: '6px 12px' }}
              onClick={fetchAuditData}
            >
              Refresh
            </button>
          </div>
        </header>

        {/* Content Body */}
        <main className="ds-dashboard-content" role="main">
          {/* Header */}
          <section className="ds-workspace-header" aria-labelledby="audit-heading">
            <h1 id="audit-heading" className="ds-workspace-title">
              Audit Ledger &amp; Blockchain Anchors
            </h1>
            <p className="ds-workspace-subtitle">
              Cryptographically verified, SHA-256 hash-chained event ledger anchored into the Ethereum blockchain.
            </p>
          </section>

          {/* Chain Integrity Status Banner */}
          {chainStatus && (
            <div
              style={{
                marginBottom: '16px',
                padding: '12px 16px',
                borderRadius: '8px',
                background: chainStatus.valid ? 'rgba(74, 222, 128, 0.1)' : 'rgba(239, 68, 68, 0.1)',
                border: `1px solid ${chainStatus.valid ? 'rgba(74, 222, 128, 0.3)' : 'rgba(239, 68, 68, 0.3)'}`,
                color: chainStatus.valid ? '#4ade80' : '#f87171',
                fontSize: '13px',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
              }}
            >
              <VerifiedIcon size={16} />
              <span>
                <strong>Hash Chain Audit:</strong> {chainStatus.valid ? 'Chain 100% Intact & Untampered' : 'Chain Tampering Detected!'} across {chainStatus.checked} verified events.
              </span>
            </div>
          )}

          {/* Navigation Tabs */}
          <div style={{ display: 'flex', gap: '8px', marginBottom: '16px' }}>
            <button
              type="button"
              className={`ds-category-pill ${activeTab === 'events' ? 'ds-category-pill--active' : ''}`}
              onClick={() => setActiveTab('events')}
            >
              Audit Events ({events.length})
            </button>
            <button
              type="button"
              className={`ds-category-pill ${activeTab === 'batches' ? 'ds-category-pill--active' : ''}`}
              onClick={() => setActiveTab('batches')}
            >
              Merkle Batches &amp; On-Chain Anchors ({batches.length})
            </button>
          </div>

          {activeTab === 'events' ? (
            <>
              {/* Filter Toolbar */}
              <section className="ds-audit-toolbar" aria-label="Search and filter audit events">
                <div className="ds-audit-search-wrapper">
                  <span className="ds-audit-search-icon" aria-hidden="true">
                    <SearchIcon size={16} />
                  </span>
                  <input
                    type="text"
                    className="ds-audit-search-input"
                    placeholder="Search by event type or hash..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                  />
                  {searchQuery && (
                    <button
                      type="button"
                      className="ds-audit-search-clear"
                      onClick={() => setSearchQuery('')}
                    >
                      <XCloseIcon size={14} />
                    </button>
                  )}
                </div>

                <div className="ds-audit-filters" role="radiogroup">
                  {[
                    { id: 'all', label: 'All Events' },
                    { id: 'auth', label: 'Auth' },
                    { id: 'document', label: 'Documents' },
                    { id: 'share', label: 'Sharing' },
                  ].map((f) => (
                    <button
                      key={f.id}
                      type="button"
                      className={`ds-audit-pill ${selectedFilter === f.id ? 'ds-audit-pill--active' : ''}`}
                      onClick={() => setSelectedFilter(f.id)}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
              </section>

              {/* Events Table */}
              {isLoading ? (
                <div style={{ textAlign: 'center', padding: '48px 0', color: 'var(--color-text-muted)' }}>
                  Loading append-only ledger events...
                </div>
              ) : filteredEvents.length === 0 ? (
                <div className="ds-audit-empty-card">
                  <VerifiedIcon size={26} />
                  <h2>No events recorded yet</h2>
                  <p>Actions performed across DropSafe will record cryptographic events here.</p>
                </div>
              ) : (
                <div className="ds-audit-table-container">
                  <table className="ds-audit-table">
                    <thead>
                      <tr>
                        <th>Seq #</th>
                        <th>Event Type</th>
                        <th>Event Hash (Digest)</th>
                        <th>Occurred At</th>
                        <th>Batch Status</th>
                        <th style={{ textAlign: 'right' }}>Merkle Verification</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredEvents.map((ev) => (
                        <tr key={ev.id}>
                          <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>#{ev.sequence_number}</td>
                          <td>
                            <span style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>
                              {ev.event_type}
                            </span>
                          </td>
                          <td style={{ fontFamily: 'monospace', fontSize: '11px', color: '#94a3b8' }}>
                            {ev.event_hash_hex.substring(0, 20)}...
                          </td>
                          <td>{new Date(ev.occurred_at).toLocaleString()}</td>
                          <td>
                            <span
                              style={{
                                fontSize: '11px',
                                padding: '2px 8px',
                                borderRadius: '12px',
                                background: ev.batch_id ? 'rgba(74, 222, 128, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                                color: ev.batch_id ? '#4ade80' : '#f59e0b',
                              }}
                            >
                              {ev.batch_id ? 'Batched' : 'Pending Batch'}
                            </span>
                          </td>
                          <td style={{ textAlign: 'right' }}>
                            {ev.batch_id ? (
                              <button
                                type="button"
                                className="ds-btn ds-btn--secondary"
                                style={{ fontSize: '11px', padding: '3px 8px' }}
                                onClick={() => handleInspectProof(ev)}
                              >
                                Verify Proof
                              </button>
                            ) : (
                              <span style={{ fontSize: '11px', color: 'var(--color-text-muted)' }}>Awaiting Batch</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </>
          ) : (
            /* Batches Tab */
            <div className="ds-audit-table-container">
              <table className="ds-audit-table">
                <thead>
                  <tr>
                    <th>Batch #</th>
                    <th>Merkle Root (Root Hash)</th>
                    <th>Sequence Range</th>
                    <th>Events</th>
                    <th>Status</th>
                    <th>Anchor Transaction</th>
                  </tr>
                </thead>
                <tbody>
                  {batches.map((b) => (
                    <tr key={b.id}>
                      <td style={{ fontFamily: 'monospace', fontWeight: 600 }}>Batch #{b.batch_number}</td>
                      <td style={{ fontFamily: 'monospace', fontSize: '12px', color: '#38bdf8' }}>
                        {b.merkle_root_hex.substring(0, 24)}...
                      </td>
                      <td>#{b.first_sequence_number} - #{b.last_sequence_number}</td>
                      <td>{b.event_count}</td>
                      <td>
                        <span
                          style={{
                            fontSize: '11px',
                            padding: '2px 8px',
                            borderRadius: '12px',
                            background: b.status === 'anchored' ? 'rgba(74, 222, 128, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                            color: b.status === 'anchored' ? '#4ade80' : '#f59e0b',
                          }}
                        >
                          {b.status}
                        </span>
                      </td>
                      <td style={{ fontFamily: 'monospace', fontSize: '11px', color: '#94a3b8' }}>
                        {b.anchors.length > 0 && b.anchors[0].transaction_hash
                          ? `${b.anchors[0].transaction_hash.substring(0, 18)}...`
                          : 'Mock Anchor / Queued'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>

      {/* Merkle Proof Inspection & On-Chain Verification Modal */}
      {inspectEvent && (
        <div
          className="ds-modal-backdrop"
          onClick={() => setInspectEvent(null)}
          role="dialog"
          aria-modal="true"
        >
          <div
            className="ds-modal-content"
            style={{ maxWidth: '640px' }}
            onClick={(e) => e.stopPropagation()}
          >
            <div className="ds-modal-header">
              <h3 className="ds-modal-title">Merkle Inclusion Proof Verification</h3>
              <button
                type="button"
                className="ds-modal-close"
                onClick={() => setInspectEvent(null)}
              >
                ✕
              </button>
            </div>

            <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '12px' }}>
              <div>
                <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>Target Event &amp; Batch:</span>
                <div style={{ fontWeight: 600, color: '#fff', fontSize: '14px' }}>
                  #{inspectEvent.sequence_number} — {inspectEvent.event_type} {inspectBatch ? `(Batch #${inspectBatch.batch_number})` : ''}
                </div>
              </div>

              <div>
                <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>Leaf Hash (0x00 || Event Hash):</span>
                <div style={{ fontFamily: 'monospace', fontSize: '11px', color: '#93c5fd', wordBreak: 'break-all' }}>
                  {proofData ? proofData.leaf_hash_hex : 'Computing...'}
                </div>
              </div>

              <div>
                <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>Batch Merkle Root:</span>
                <div style={{ fontFamily: 'monospace', fontSize: '11px', color: '#38bdf8', wordBreak: 'break-all' }}>
                  {proofData ? proofData.merkle_root_hex : 'Computing...'}
                </div>
              </div>

              {/* On-Chain Status */}
              <div style={{ padding: '12px', borderRadius: '8px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
                <div style={{ fontSize: '12px', fontWeight: 600, color: '#e2e8f0', marginBottom: '4px' }}>
                  Blockchain Anchor State:
                </div>
                {proofLoading ? (
                  <div style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>Querying Ethereum node...</div>
                ) : onChainResult?.verified ? (
                  <div style={{ color: '#4ade80', fontSize: '13px' }}>
                    ✔ Root matches Ethereum Smart Contract state (Batch #{onChainResult.batchNumber})
                  </div>
                ) : (
                  <div style={{ fontSize: '12px', color: '#cbd5e1' }}>
                    {onChainResult?.error || 'Simulated anchor (Mock testnet mode enabled)'}
                  </div>
                )}
              </div>

              {/* Merkle Sibling Hashes */}
              {proofData && (
                <div>
                  <span style={{ fontSize: '12px', color: 'var(--color-text-muted)' }}>
                    Merkle Proof Path ({proofData.proof.length} sibling steps):
                  </span>
                  <div style={{ maxHeight: '120px', overflowY: 'auto', background: 'rgba(0,0,0,0.3)', padding: '8px', borderRadius: '6px', fontSize: '10px', fontFamily: 'monospace' }}>
                    {proofData.proof.map((p, idx) => (
                      <div key={idx} style={{ color: '#94a3b8' }}>
                        Step {idx + 1} [{p.position}]: {p.hash_hex}
                      </div>
                    ))}
                  </div>
                </div>
              )}

              <div style={{ marginTop: '16px', display: 'flex', justifyContent: 'flex-end' }}>
                <button
                  type="button"
                  className="ds-btn ds-btn--secondary"
                  onClick={() => setInspectEvent(null)}
                >
                  Close
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
