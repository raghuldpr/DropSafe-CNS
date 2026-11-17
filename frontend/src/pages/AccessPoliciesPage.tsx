import { AdminNavItem } from '../components/AdminNavItem';
import React, { useState, useEffect } from 'react';
import {
  DashboardIcon,
  FolderIcon,
  ShareIcon,
  ShieldIcon,
  VerifiedIcon,
  SettingsIcon,
  PlusIcon,
  TrashIcon,
  XCloseIcon,
  DocumentIcon,
} from '../components/Icons';
import { documentApi } from '../services/api';
import type { DocumentItem, PolicyResponse } from '../types/api';
import type { PolicyIntent, PermittedAction, PolicyCondition } from '../types/policies';
import './AccessPoliciesPage.css';

interface AccessPoliciesPageProps {
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

interface DocumentPolicyRecord {
  document: DocumentItem;
  policy: PolicyResponse | null;
}

export const AccessPoliciesPage: React.FC<AccessPoliciesPageProps> = ({ onNavigate }) => {
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [ownedDocs, setOwnedDocs] = useState<DocumentItem[]>([]);
  const [policiesList, setPoliciesList] = useState<DocumentPolicyRecord[]>([]);
  const [loading, setLoading] = useState<boolean>(true);

  // Modal states
  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false);
  const [selectedDocId, setSelectedDocId] = useState<string>('');
  const [policyName, setPolicyName] = useState('');
  const [nameError, setNameError] = useState<string | null>(null);
  const [description, setDescription] = useState('');
  const [intent, setIntent] = useState<PolicyIntent>('allow');
  const [permittedAction, setPermittedAction] = useState<PermittedAction>('view');
  const [requireApprovedNetwork, setRequireApprovedNetwork] = useState(false);
  const [statusMessage, setStatusMessage] = useState<string | null>(null);

  const [subjectConditions, setSubjectConditions] = useState<PolicyCondition[]>([
    { id: 'subj-1', attribute: 'department', operator: 'equals', value: 'Engineering' },
  ]);

  const [resourceConditions, setResourceConditions] = useState<PolicyCondition[]>([
    { id: 'res-1', attribute: 'file_type', operator: 'equals', value: 'application/pdf' },
  ]);

  const loadData = async () => {
    try {
      setLoading(true);
      const docs = await documentApi.list('owned');
      setOwnedDocs(docs);

      if (docs.length > 0 && !selectedDocId) {
        // check url query param
        const hash = window.location.hash;
        const qIndex = hash.indexOf('?');
        if (qIndex !== -1) {
          const params = new URLSearchParams(hash.substring(qIndex + 1));
          const pId = params.get('id');
          if (pId && docs.some((d) => d.id === pId)) {
            setSelectedDocId(pId);
          } else {
            setSelectedDocId(docs[0].id);
          }
        } else {
          setSelectedDocId(docs[0].id);
        }
      }

      const records: DocumentPolicyRecord[] = [];
      for (const d of docs) {
        try {
          const p = await documentApi.getPolicy(d.id);
          records.push({ document: d, policy: p });
        } catch {
          records.push({ document: d, policy: null });
        }
      }
      setPoliciesList(records);
    } catch (err: any) {
      console.error('Failed to load policies:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  // Close modals on Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (isCreateModalOpen) setIsCreateModalOpen(false);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isCreateModalOpen]);

  const handleAddSubjectCondition = () => {
    setSubjectConditions((prev) => [
      ...prev,
      {
        id: `subj-${Date.now()}`,
        attribute: 'department',
        operator: 'equals',
        value: '',
      },
    ]);
  };

  const handleRemoveSubjectCondition = (id: string) => {
    if (subjectConditions.length <= 1) return;
    setSubjectConditions((prev) => prev.filter((c) => c.id !== id));
  };

  const handleUpdateSubjectCondition = (
    id: string,
    field: keyof PolicyCondition,
    val: string
  ) => {
    setSubjectConditions((prev) =>
      prev.map((c) => (c.id === id ? { ...c, [field]: val } : c))
    );
  };

  const handleAddResourceCondition = () => {
    setResourceConditions((prev) => [
      ...prev,
      {
        id: `res-${Date.now()}`,
        attribute: 'file_type',
        operator: 'equals',
        value: '',
      },
    ]);
  };

  const handleRemoveResourceCondition = (id: string) => {
    if (resourceConditions.length <= 1) return;
    setResourceConditions((prev) => prev.filter((c) => c.id !== id));
  };

  const handleUpdateResourceCondition = (
    id: string,
    field: keyof PolicyCondition,
    val: string
  ) => {
    setResourceConditions((prev) =>
      prev.map((c) => (c.id === id ? { ...c, [field]: val } : c))
    );
  };

  const handleOpenCreateModal = (docId?: string) => {
    if (docId) setSelectedDocId(docId);
    setPolicyName('Department Access Rule');
    setDescription('');
    setNameError(null);
    setIsCreateModalOpen(true);
  };

  const handleSavePolicy = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedDocId) {
      setNameError('Please select a target document.');
      return;
    }
    const trimmed = policyName.trim();
    if (!trimmed) {
      setNameError('Please enter a policy name.');
      return;
    }

    try {
      const ast = {
        name: trimmed,
        intent,
        permitted_actions: [permittedAction],
        subject_rules: subjectConditions.map((c) => ({
          attribute: c.attribute,
          operator: c.operator,
          value: c.value,
        })),
        resource_rules: resourceConditions.map((c) => ({
          attribute: c.attribute,
          operator: c.operator,
          value: c.value,
        })),
        environment_rules: {
          require_approved_network: requireApprovedNetwork,
        },
      };

      await documentApi.setPolicy(selectedDocId, {
        policy_ast: ast,
        description,
      });

      setStatusMessage('ABAC Policy AST attached and saved successfully!');
      setIsCreateModalOpen(false);
      await loadData();
      setTimeout(() => setStatusMessage(null), 3000);
    } catch (err: any) {
      console.error('Failed to save policy:', err);
      setNameError(err.message || 'Failed to save policy');
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
            className="ds-sidebar__item ds-sidebar__item--active"
            aria-current="page"
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
            <span>ABAC Policy Engine</span>
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
              <span className="ds-topbar__crumb--active">Access Policies</span>
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
        <main className="ds-policies-content" id="main-content">
          <div className="ds-policies-header">
            <div className="ds-policies-header__text">
              <h1 className="ds-policies-header__title">Attribute-Based Access Policies</h1>
              <p className="ds-policies-header__subtitle">
                Define fine-grained ABAC rules evaluating user departments, security clearance, and resource sensitivity.
              </p>
            </div>

            <button
              type="button"
              className="ds-btn ds-btn--primary"
              onClick={() => handleOpenCreateModal()}
              disabled={ownedDocs.length === 0}
            >
              <PlusIcon size={16} aria-hidden="true" />
              <span>Configure Policy</span>
            </button>
          </div>

          {statusMessage && (
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
              {statusMessage}
            </div>
          )}

          {/* Policies Table */}
          {loading ? (
            <div style={{ padding: 'var(--space-6)', textAlign: 'center', color: 'var(--color-text-muted)' }}>
              Loading document ABAC policies...
            </div>
          ) : policiesList.length === 0 ? (
            <section className="ds-policies-empty-card" role="region">
              <div className="ds-policies-empty-icon" aria-hidden="true">
                <ShieldIcon size={28} />
              </div>
              <h3 className="ds-policies-empty-title">No documents available</h3>
              <p className="ds-policies-empty-desc">
                Upload a file to your workspace to configure Attribute-Based Access Control policies.
              </p>
              <button
                type="button"
                className="ds-btn ds-btn--primary"
                onClick={() => onNavigate('upload')}
                style={{ marginTop: 'var(--space-2)' }}
              >
                Upload File
              </button>
            </section>
          ) : (
            <div className="ds-shared-table-container">
              <table className="ds-shared-table">
                <thead>
                  <tr>
                    <th>Target Document</th>
                    <th>Policy Status</th>
                    <th>Intent</th>
                    <th>Permitted Actions</th>
                    <th>Rule Conditions</th>
                    <th style={{ textAlign: 'right' }}>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {policiesList.map((rec) => {
                    const ast = rec.policy?.policy_ast;
                    const intentVal = ast?.intent || 'allow';
                    const actionsVal = ast?.permitted_actions?.join(', ') || 'view';
                    const rulesCount =
                      (ast?.subject_rules?.length || 0) + (ast?.resource_rules?.length || 0);

                    return (
                      <tr key={rec.document.id}>
                        <td style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                          <DocumentIcon size={18} style={{ color: 'var(--color-accent)' }} />
                          <span style={{ fontWeight: 500, color: 'var(--color-text-primary)' }}>
                            {rec.document.display_name}
                          </span>
                        </td>
                        <td>
                          {rec.policy ? (
                            <span className="ds-badge-permission ds-badge-permission--editor">
                              Active (v{rec.policy.version_number})
                            </span>
                          ) : (
                            <span className="ds-badge-permission ds-badge-permission--viewer">
                              Default (Owner Only)
                            </span>
                          )}
                        </td>
                        <td>
                          <span
                            className={`ds-badge-permission ${
                              intentVal === 'allow'
                                ? 'ds-badge-permission--editor'
                                : 'ds-badge-permission--viewer'
                            }`}
                          >
                            {intentVal.toUpperCase()}
                          </span>
                        </td>
                        <td style={{ textTransform: 'capitalize' }}>{actionsVal}</td>
                        <td>{rulesCount > 0 ? `${rulesCount} Condition(s)` : 'Unrestricted'}</td>
                        <td style={{ textAlign: 'right' }}>
                          <button
                            type="button"
                            className="ds-btn ds-btn--secondary"
                            onClick={() => handleOpenCreateModal(rec.document.id)}
                            style={{ padding: '4px 10px', fontSize: '12px' }}
                          >
                            {rec.policy ? 'Edit Policy' : 'Set Policy'}
                          </button>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </main>
      </div>

      {/* Modal Dialog */}
      {isCreateModalOpen && (
        <div
          className="ds-modal-backdrop"
          onClick={() => setIsCreateModalOpen(false)}
          role="dialog"
          aria-modal="true"
        >
          <div className="ds-policy-modal" onClick={(e) => e.stopPropagation()}>
            <header className="ds-policy-modal__header">
              <div className="ds-policy-modal__title-group">
                <h3 className="ds-policy-modal__title">Configure ABAC Policy</h3>
                <span className="ds-policy-modal__subtitle">
                  Define attribute evaluation rules enforced during DEK wrapping and recipient access.
                </span>
              </div>

              <button
                type="button"
                className="ds-policy-modal__close-btn"
                onClick={() => setIsCreateModalOpen(false)}
                aria-label="Close dialog"
              >
                <XCloseIcon size={18} />
              </button>
            </header>

            <form onSubmit={handleSavePolicy} noValidate>
              <div className="ds-policy-modal__body">
                {/* Target File */}
                <div className="ds-policy-form-section">
                  <label className="ds-share-label">Target Document</label>
                  <select
                    className="ds-condition-select"
                    style={{ width: '100%', marginTop: '4px' }}
                    value={selectedDocId}
                    onChange={(e) => setSelectedDocId(e.target.value)}
                  >
                    {ownedDocs.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.display_name} ({d.id.slice(0, 8)}...)
                      </option>
                    ))}
                  </select>
                </div>

                {/* Policy Name */}
                <div className="ds-policy-form-section">
                  <label htmlFor="policy-name-input" className="ds-share-label">
                    Policy Name
                  </label>
                  <input
                    id="policy-name-input"
                    type="text"
                    className={`ds-share-input ${nameError ? 'ds-share-input--error' : ''}`}
                    placeholder="e.g. Engineering Confidential Access"
                    value={policyName}
                    onChange={(e) => {
                      setPolicyName(e.target.value);
                      if (nameError) setNameError(null);
                    }}
                  />
                  {nameError && (
                    <span className="ds-share-error-msg" role="alert">
                      {nameError}
                    </span>
                  )}

                  <label
                    htmlFor="policy-desc-input"
                    className="ds-share-label"
                    style={{ marginTop: 'var(--space-2)' }}
                  >
                    Description
                  </label>
                  <textarea
                    id="policy-desc-input"
                    rows={2}
                    className="ds-share-textarea"
                    placeholder="Rationale for this access constraint..."
                    value={description}
                    onChange={(e) => setDescription(e.target.value)}
                  />

                  {/* Intent Selection */}
                  <div style={{ marginTop: 'var(--space-2)' }}>
                    <span className="ds-share-label">Policy Intent</span>
                    <div className="ds-policy-intent-group" role="radiogroup">
                      <label
                        className={`ds-policy-intent-card ${
                          intent === 'allow' ? 'ds-policy-intent-card--active-allow' : ''
                        }`}
                      >
                        <input
                          type="radio"
                          name="policy-intent"
                          value="allow"
                          checked={intent === 'allow'}
                          onChange={() => setIntent('allow')}
                          className="ds-access-radio"
                        />
                        <span>Allow Access</span>
                      </label>

                      <label
                        className={`ds-policy-intent-card ${
                          intent === 'deny' ? 'ds-policy-intent-card--active-deny' : ''
                        }`}
                      >
                        <input
                          type="radio"
                          name="policy-intent"
                          value="deny"
                          checked={intent === 'deny'}
                          onChange={() => setIntent('deny')}
                          className="ds-access-radio"
                        />
                        <span>Deny Access</span>
                      </label>
                    </div>
                  </div>
                </div>

                {/* Subject Conditions */}
                <div className="ds-policy-form-section">
                  <div className="ds-policy-section-heading">
                    <span>Subject Attribute Rules</span>
                    <button
                      type="button"
                      className="ds-condition-add-btn"
                      onClick={handleAddSubjectCondition}
                    >
                      <PlusIcon size={12} aria-hidden="true" />
                      <span>Add Rule</span>
                    </button>
                  </div>

                  <div className="ds-condition-rows">
                    {subjectConditions.map((cond) => (
                      <div key={cond.id} className="ds-condition-row">
                        <select
                          className="ds-condition-select"
                          value={cond.attribute}
                          onChange={(e) =>
                            handleUpdateSubjectCondition(cond.id, 'attribute', e.target.value)
                          }
                        >
                          <option value="department">Department</option>
                          <option value="role">Role</option>
                          <option value="security_clearance">Clearance</option>
                          <option value="email_domain">Email Domain</option>
                        </select>

                        <select
                          className="ds-condition-select"
                          value={cond.operator}
                          onChange={(e) =>
                            handleUpdateSubjectCondition(cond.id, 'operator', e.target.value)
                          }
                        >
                          <option value="equals">Equals</option>
                          <option value="not_equals">Does not equal</option>
                          <option value="in">In List</option>
                        </select>

                        <input
                          type="text"
                          className="ds-condition-input"
                          placeholder="Value (e.g. Engineering)"
                          value={cond.value}
                          onChange={(e) =>
                            handleUpdateSubjectCondition(cond.id, 'value', e.target.value)
                          }
                        />

                        <button
                          type="button"
                          className="ds-condition-remove-btn"
                          disabled={subjectConditions.length <= 1}
                          onClick={() => handleRemoveSubjectCondition(cond.id)}
                        >
                          <TrashIcon size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Resource Conditions */}
                <div className="ds-policy-form-section">
                  <div className="ds-policy-section-heading">
                    <span>Resource Attribute Rules</span>
                    <button
                      type="button"
                      className="ds-condition-add-btn"
                      onClick={handleAddResourceCondition}
                    >
                      <PlusIcon size={12} aria-hidden="true" />
                      <span>Add Rule</span>
                    </button>
                  </div>

                  <div className="ds-condition-rows">
                    {resourceConditions.map((cond) => (
                      <div key={cond.id} className="ds-condition-row">
                        <select
                          className="ds-condition-select"
                          value={cond.attribute}
                          onChange={(e) =>
                            handleUpdateResourceCondition(cond.id, 'attribute', e.target.value)
                          }
                        >
                          <option value="classification_level">Classification</option>
                          <option value="file_type">File Type</option>
                          <option value="file_extension">Extension</option>
                        </select>

                        <select
                          className="ds-condition-select"
                          value={cond.operator}
                          onChange={(e) =>
                            handleUpdateResourceCondition(cond.id, 'operator', e.target.value)
                          }
                        >
                          <option value="equals">Equals</option>
                          <option value="not_equals">Does not equal</option>
                        </select>

                        <input
                          type="text"
                          className="ds-condition-input"
                          placeholder="Value..."
                          value={cond.value}
                          onChange={(e) =>
                            handleUpdateResourceCondition(cond.id, 'value', e.target.value)
                          }
                        />

                        <button
                          type="button"
                          className="ds-condition-remove-btn"
                          disabled={resourceConditions.length <= 1}
                          onClick={() => handleRemoveResourceCondition(cond.id)}
                        >
                          <TrashIcon size={14} />
                        </button>
                      </div>
                    ))}
                  </div>
                </div>

                {/* Permitted Action */}
                <div className="ds-policy-form-section">
                  <span className="ds-policy-section-heading">Permitted Action</span>
                  <div className="ds-action-cards-grid" role="radiogroup">
                    {(['view', 'download', 'edit', 'share'] as const).map((act) => (
                      <label
                        key={act}
                        className={`ds-action-card ${
                          permittedAction === act ? 'ds-action-card--active' : ''
                        }`}
                      >
                        <input
                          type="radio"
                          name="permitted-action"
                          value={act}
                          checked={permittedAction === act}
                          onChange={() => setPermittedAction(act)}
                          className="ds-access-radio"
                        />
                        <span style={{ textTransform: 'capitalize' }}>{act}</span>
                      </label>
                    ))}
                  </div>
                </div>

                {/* Environmental Conditions */}
                <div className="ds-policy-form-section">
                  <span className="ds-policy-section-heading">Environmental Checks</span>
                  <label className="ds-expiry-toggle-row" style={{ marginTop: 'var(--space-2)' }}>
                    <input
                      type="checkbox"
                      checked={requireApprovedNetwork}
                      onChange={(e) => setRequireApprovedNetwork(e.target.checked)}
                      className="ds-expiry-checkbox"
                    />
                    <span className="ds-expiry-toggle-label">
                      Require caller connection from approved corporate network
                    </span>
                  </label>
                </div>
              </div>

              <footer className="ds-policy-modal__footer">
                <button
                  type="button"
                  className="ds-btn ds-btn--secondary"
                  onClick={() => setIsCreateModalOpen(false)}
                >
                  Cancel
                </button>
                <button type="submit" className="ds-btn ds-btn--primary">
                  Save & Enforce Policy
                </button>
              </footer>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};

export default AccessPoliciesPage;
