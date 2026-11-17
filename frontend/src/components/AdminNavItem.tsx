import React from 'react';
import { ShieldIcon } from './Icons';
import { useAuth } from '../context/AuthContext';

/** Sidebar entry shown only to users holding the "admin" role (UX only; backend enforces). */
export const AdminNavItem: React.FC<{ onNavigate: (route: any) => void; active?: boolean }> = ({
  onNavigate,
  active,
}) => {
  const { user } = useAuth();
  if (!user?.roles?.includes('admin')) return null;
  return (
    <button
      type="button"
      className={`ds-sidebar__item ${active ? 'ds-sidebar__item--active' : ''}`}
      onClick={() => onNavigate('admin')}
      aria-current={active ? 'page' : undefined}
    >
      <span className="ds-sidebar__icon" aria-hidden="true">
        <ShieldIcon size={18} />
      </span>
      <span>Admin Console</span>
    </button>
  );
};
