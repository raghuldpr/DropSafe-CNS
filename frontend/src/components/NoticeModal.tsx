import React, { useEffect } from 'react';
import { LockIcon } from './Icons';
import './NoticeModal.css';

interface NoticeModalProps {
  actionName?: string | null;
  featureName?: string | null;
  isOpen?: boolean;
  onClose: () => void;
}

export const NoticeModal: React.FC<NoticeModalProps> = ({
  actionName,
  featureName,
  isOpen = true,
  onClose,
}) => {
  const displayTitle = featureName || actionName;

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  if (!isOpen || !displayTitle) return null;

  return (
    <div
      className="ds-modal-backdrop"
      onClick={onClose}
      role="dialog"
      aria-modal="true"
      aria-labelledby="modal-title"
    >
      <div className="ds-modal" onClick={(e) => e.stopPropagation()}>
        <button
          type="button"
          className="ds-modal__close"
          onClick={onClose}
          aria-label="Close dialog"
        >
          <svg
            width="20"
            height="20"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <line x1="18" y1="6" x2="6" y2="18" />
            <line x1="6" y1="6" x2="18" y2="18" />
          </svg>
        </button>

        <div className="ds-modal__icon">
          <LockIcon size={22} />
        </div>

        <span className="ds-modal__badge">Current Milestone: Landing Page</span>

        <h3 id="modal-title" className="ds-modal__title">
          {displayTitle}
        </h3>

        <p className="ds-modal__text">
          DropSafe is currently in its initial frontend development phase. The public landing
          page screen is fully operational. Authentication and file management workspaces
          will be connected in upcoming milestones as the backend API contracts are established.
        </p>

        <div className="ds-modal__actions">
          <button
            type="button"
            className="ds-btn ds-btn--primary"
            onClick={onClose}
          >
            Return to Landing Page
          </button>
        </div>
      </div>
    </div>
  );
};
