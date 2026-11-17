import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  DashboardIcon,
  FolderIcon,
  ShareIcon,
  ShieldIcon,
  VerifiedIcon,
  SettingsIcon,
} from '../components/Icons';
import { useAuth } from '../context/AuthContext';
import { adminApi } from '../services/api';
import type { AdminUserSummary, AttributeDefinitionResponse } from '../types/api';
import './AdminPage.css';

interface AdminPageProps {
  onNavigate: (route: any) => void;
}

const formatValue = (v: any): string => {
  if (Array.isArray(v)) return v.join(', ');
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  return String(v ?? '');
};

export const AdminPage: React.FC<AdminPageProps> = ({ onNavigate }) => {
  const { user, logout } = useAuth();
  const isAdmin = !!user?.roles?.includes('admin');
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);

  const [users, setUsers] = useState<AdminUserSummary[]>([]);
  const [defs, setDefs] = useState<AttributeDefinitionResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const [attrId, setAttrId] = useState('');
  const [attrValue, setAttrValue] = useState('');

  const [newName, setNewName] = useState('');
  const [newType, setNewType] = useState('string');
  const [newDesc, setNewDesc] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [u, d] = await Promise.all([adminApi.listUsers(), adminApi.listDefinitions()]);
      setUsers(u);
      setDefs(d);
    } catch (e: any) {
      setError(e.message || 'Failed to load admin data');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (isAdmin) load();
  }, [isAdmin, load]);

  // UX guard only; the backend enforces the admin role on every call.
  useEffect(() => {
    if (user && !isAdmin) window.location.hash = '#/access-denied';
  }, [user, isAdmin]);

  const flash = (msg: string) => {
    setNotice(`${msg} Change recorded in the Audit Ledger.`);
    setTimeout(() => setNotice(null), 5000);
  };

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return users.filter(
      (u) => !q || u.email.toLowerCase().includes(q) || u.display_name.toLowerCase().includes(q)
    );
  }, [users, search]);

  const selected = users.find((u) => u.id === selectedId) || null;
  const selectedDef = defs.find((d) => d.id === attrId) || null;
  const allowed: any[] | null =
    selectedDef && Array.isArray(selectedDef.allowed_values) ? selectedDef.allowed_values : null;

  const selectUser = (id: string) => {
    setSelectedId(id);
    setAttrId('');
    setAttrValue('');
  };

  const pickAttr = (id: string) => {
    setAttrId(id);
    const d = defs.find((x) => x.id === id);
    const existing = selected?.attributes.find((a) => a.attribute_definition_id === id);
    setAttrValue(existing ? formatValue(existing.value) : d?.value_type === 'boolean' ? 'true' : '');
  };

  const run = async (fn: () => Promise<unknown>, okMsg: string) => {
    setError(null);
    try {
      await fn();
      await load();
      flash(okMsg);
    } catch (e: any) {
      setError(e.message || 'Action failed');
    }
  };

  const parseValue = (): unknown => {
    switch (selectedDef?.value_type) {
      case 'integer':
        return parseInt(attrValue, 10);
      case 'boolean':
        return attrValue === 'true';
      case 'string_set':
        return attrValue
          .split(',')
          .map((s) => s.trim())
          .filter(Boolean);
      default:
        return attrValue.trim();
    }
  };

  const saveAttr = () => {
    if (!selected || !selectedDef) return;
    const value = parseValue();
    if (typeof value === 'number' && Number.isNaN(value)) {
      setError('Please enter a valid number.');
      return;
    }
    run(
      () => adminApi.setAttribute(selected.id, selectedDef.id, value),
      `Set ${selectedDef.name} for ${selected.email}.`
    );
  };

  const removeAttr = (attributeDefId: string, name: string) => {
    if (!selected) return;
    if (!confirm(`Remove "${name}" from ${selected.email}?`)) return;
    run(() => adminApi.removeAttribute(selected.id, attributeDefId), `Removed ${name}.`);
  };

  const toggleAdmin = () => {
    if (!selected) return;
    const has = selected.roles.includes('admin');
    const roles = has ? selected.roles.filter((r) => r !== 'admin') : [...selected.roles, 'admin'];
    run(() => adminApi.setRoles(selected.id, roles), `${has ? 'Removed' : 'Granted'} admin role.`);
  };

  const toggleStatus = () => {
    if (!selected) return;
    const next = selected.status === 'active' ? 'disabled' : 'active';
    if (next === 'disabled' && !confirm(`Disable account ${selected.email}?`)) return;
    run(() => adminApi.setStatus(selected.id, next), `Account ${next}.`);
  };

  const createDef = (e: React.FormEvent) => {
    e.preventDefault();
    run(async () => {
      await adminApi.createDefinition({
        name: newName,
        value_type: newType,
        description: newDesc || undefined,
      });
      setNewName('');
      setNewDesc('');
    }, `Created attribute "${newName}".`);
  };

  const handleLogout = async () => {
    await logout();
    onNavigate('login');
  };

  const navItem = (route: string, label: string, icon: React.ReactNode, active = false) => (
    <button
      type="button"
      className={`ds-sidebar__item ${active ? 'ds-sidebar__item--active' : ''}`}
      onClick={() => onNavigate(route)}
      aria-current={active ? 'page' : undefined}
    >
      <span className="ds-sidebar__icon" aria-hidden="true">
        {icon}
      </span>
      <span>{label}</span>
    </button>
  );

  return (
    <div className="ds-dashboard-shell">
      <div
        className={`ds-sidebar-backdrop ${mobileSidebarOpen ? 'ds-sidebar-backdrop--visible' : ''}`}
        onClick={() => setMobileSidebarOpen(false)}
        aria-hidden="true"
      />
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
            <img src="/assets/dropsafe-logo.png" alt="DropSafe" className="ds-sidebar__logo" />
          </a>
        </div>
        <nav className="ds-sidebar__nav">
          <span className="ds-sidebar__section-label">Workspace</span>
          {navItem('dashboard', 'Dashboard', <DashboardIcon size={18} />)}
          {navItem('files', 'My Files', <FolderIcon size={18} />)}
          {navItem('shared-with-me', 'Shared with Me', <ShareIcon size={18} />)}
          {navItem('policies', 'Access Policies', <ShieldIcon size={18} />)}
          {navItem('audit-log', 'Audit Log', <VerifiedIcon size={18} />)}
          <span className="ds-sidebar__section-label" style={{ marginTop: 'var(--space-3)' }}>
            System
          </span>
          {navItem('admin', 'Admin Console', <ShieldIcon size={18} />, true)}
          {navItem('settings', 'Settings', <SettingsIcon size={18} />)}
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

      <div className="ds-main-area">
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
              <span className="ds-topbar__crumb--active">Admin Console</span>
            </nav>
          </div>
          <div className="ds-topbar__right">
            <div className="ds-topbar__session-pill">
              <span className="ds-sidebar__badge-dot" aria-hidden="true" />
              <span>{user ? user.email : 'Connecting...'}</span>
            </div>
          </div>
        </header>

        <main className="ds-admin" id="main-content">
          <div className="ds-admin__head">
            <h1>Admin Console</h1>
            <p>
              Manage the trusted attributes (department, clearance, projects) that drive ABAC decisions.
              Every change re-signs the user's credential and is written to the audit ledger.
            </p>
          </div>

          {notice && (
            <div className="ds-admin__msg ds-admin__msg--ok" role="status">
              {notice}
            </div>
          )}
          {error && (
            <div className="ds-admin__msg ds-admin__msg--err" role="alert">
              {error}
            </div>
          )}

          <div className="ds-admin__grid">
            <section className="ds-admin__card" aria-labelledby="users-h">
              <div className="ds-admin__card-head">
                <h2 id="users-h">Users ({filtered.length})</h2>
                <input
                  type="search"
                  className="ds-admin__input"
                  placeholder="Search email or name"
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  aria-label="Search users"
                />
              </div>
              {loading ? (
                <p className="ds-admin__muted">Loading users…</p>
              ) : filtered.length === 0 ? (
                <p className="ds-admin__muted">No users match.</p>
              ) : (
                <div className="ds-admin__table-wrap">
                  <table className="ds-admin__table">
                    <thead>
                      <tr>
                        <th>User</th>
                        <th>Roles</th>
                        <th>Attributes</th>
                        <th>Status</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filtered.map((u) => (
                        <tr
                          key={u.id}
                          className={u.id === selectedId ? 'is-selected' : ''}
                          tabIndex={0}
                          onClick={() => selectUser(u.id)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') selectUser(u.id);
                          }}
                        >
                          <td>
                            <strong>{u.display_name}</strong>
                            <div className="ds-admin__muted">{u.email}</div>
                          </td>
                          <td>
                            {u.roles.map((r) => (
                              <span key={r} className="ds-admin__badge">
                                {r}
                              </span>
                            ))}
                          </td>
                          <td>
                            {u.attributes.length === 0 ? (
                              <span className="ds-admin__muted">none</span>
                            ) : (
                              u.attributes.map((a) => (
                                <span key={a.id} className="ds-admin__chip">
                                  {a.attribute_name}: {formatValue(a.value)}
                                </span>
                              ))
                            )}
                          </td>
                          <td>{u.status}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </section>

            <section className="ds-admin__card" aria-labelledby="edit-h">
              <h2 id="edit-h">{selected ? `Edit ${selected.display_name}` : 'Edit user'}</h2>
              {!selected ? (
                <p className="ds-admin__muted">
                  Select a user from the table to manage their attributes and role.
                </p>
              ) : (
                <>
                  <div className="ds-admin__row">
                    <button type="button" className="ds-btn ds-btn--secondary" onClick={toggleAdmin}>
                      {selected.roles.includes('admin') ? 'Remove admin role' : 'Grant admin role'}
                    </button>
                    <button type="button" className="ds-btn ds-btn--secondary" onClick={toggleStatus}>
                      {selected.status === 'active' ? 'Disable account' : 'Enable account'}
                    </button>
                  </div>

                  <h3>Assigned attributes</h3>
                  {selected.attributes.length === 0 && (
                    <p className="ds-admin__muted">No attributes assigned.</p>
                  )}
                  <ul className="ds-admin__list">
                    {selected.attributes.map((a) => (
                      <li key={a.id}>
                        <span>
                          <strong>{a.attribute_name}</strong> = {formatValue(a.value)}
                        </span>
                        <button
                          type="button"
                          className="ds-admin__link"
                          onClick={() => removeAttr(a.attribute_definition_id, a.attribute_name)}
                        >
                          Remove
                        </button>
                      </li>
                    ))}
                  </ul>

                  <h3>Assign / update attribute</h3>
                  <label className="ds-admin__label" htmlFor="attr-select">
                    Attribute
                  </label>
                  <select
                    id="attr-select"
                    className="ds-admin__input"
                    value={attrId}
                    onChange={(e) => pickAttr(e.target.value)}
                  >
                    <option value="">Select…</option>
                    {defs
                      .filter((d) => d.is_active)
                      .map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.name} ({d.value_type})
                        </option>
                      ))}
                  </select>

                  {selectedDef && (
                    <>
                      <label className="ds-admin__label" htmlFor="attr-value">
                        Value{selectedDef.value_type === 'string_set' ? ' (comma separated)' : ''}
                      </label>
                      {selectedDef.value_type === 'boolean' ? (
                        <select
                          id="attr-value"
                          className="ds-admin__input"
                          value={attrValue}
                          onChange={(e) => setAttrValue(e.target.value)}
                        >
                          <option value="true">true</option>
                          <option value="false">false</option>
                        </select>
                      ) : allowed && selectedDef.value_type !== 'string_set' ? (
                        <select
                          id="attr-value"
                          className="ds-admin__input"
                          value={attrValue}
                          onChange={(e) => setAttrValue(e.target.value)}
                        >
                          <option value="">Select…</option>
                          {allowed.map((v) => (
                            <option key={String(v)} value={String(v)}>
                              {String(v)}
                            </option>
                          ))}
                        </select>
                      ) : (
                        <input
                          id="attr-value"
                          className="ds-admin__input"
                          type={selectedDef.value_type === 'integer' ? 'number' : 'text'}
                          value={attrValue}
                          onChange={(e) => setAttrValue(e.target.value)}
                        />
                      )}
                      {selectedDef.description && (
                        <p className="ds-admin__muted">{selectedDef.description}</p>
                      )}
                      <button
                        type="button"
                        className="ds-btn ds-btn--primary"
                        onClick={saveAttr}
                        disabled={!attrValue}
                      >
                        Save attribute
                      </button>
                    </>
                  )}
                </>
              )}
            </section>
          </div>

          <section className="ds-admin__card" aria-labelledby="defs-h">
            <h2 id="defs-h">Attribute definitions</h2>
            <div className="ds-admin__table-wrap">
              <table className="ds-admin__table">
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Description</th>
                    <th>Active</th>
                  </tr>
                </thead>
                <tbody>
                  {defs.map((d) => (
                    <tr key={d.id} style={{ cursor: 'default' }}>
                      <td>
                        <code>{d.name}</code>
                      </td>
                      <td>{d.value_type}</td>
                      <td>{d.description || '—'}</td>
                      <td>{d.is_active ? 'yes' : 'no'}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <form className="ds-admin__row ds-admin__form" onSubmit={createDef}>
              <input
                className="ds-admin__input"
                placeholder="new_attribute_name"
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                required
                aria-label="Attribute name"
              />
              <select
                className="ds-admin__input"
                value={newType}
                onChange={(e) => setNewType(e.target.value)}
                aria-label="Value type"
              >
                <option value="string">string</option>
                <option value="integer">integer</option>
                <option value="boolean">boolean</option>
                <option value="string_set">string_set</option>
              </select>
              <input
                className="ds-admin__input"
                placeholder="Description (optional)"
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                aria-label="Description"
              />
              <button type="submit" className="ds-btn ds-btn--secondary">
                Add definition
              </button>
            </form>
          </section>
        </main>
      </div>
    </div>
  );
};
