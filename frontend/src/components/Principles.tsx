import React from 'react';
import { LockIcon, ShieldIcon, VerifiedIcon } from './Icons';
import './Principles.css';

interface PrincipleItem {
  id: string;
  icon: React.ReactNode;
  title: string;
  tagline: string;
  detail: string;
  bullet: string;
}

const PRINCIPLES: PrincipleItem[] = [
  {
    id: 'client-encryption',
    icon: <LockIcon size={24} aria-hidden="true" />,
    title: 'Client-Side Encryption',
    tagline: 'Files are encrypted in the browser before upload.',
    detail:
      'Encryption keys are generated and held exclusively on your client device. Plaintext never leaves your browser, ensuring no intermediate server or cloud provider can inspect your data.',
    bullet: 'Browser-executed AES-256-GCM',
  },
  {
    id: 'controlled-sharing',
    icon: <ShieldIcon size={24} aria-hidden="true" />,
    title: 'Controlled File Sharing',
    tagline: 'Define who can access your shared files.',
    detail:
      'Configure granular access permissions based on recipient identities and attributes. Maintain governance over distributed files with instant revocation capabilities.',
    bullet: 'Attribute-Based Access Control (ABAC)',
  },
  {
    id: 'auditable-activity',
    icon: <VerifiedIcon size={24} aria-hidden="true" />,
    title: 'Auditable Activity',
    tagline: 'Review recorded file and access events.',
    detail:
      'Inspect verifiable event logs tracking file uploads, shared links, and access attempts. Historical commitments prevent retroactive tampering.',
    bullet: 'Cryptographically committed audit trail',
  },
];

export const Principles: React.FC = () => {
  return (
    <section id="principles" className="ds-principles" aria-labelledby="principles-heading">
      <div className="ds-container">
        <div className="ds-principles__header">
          <span className="ds-principles__eyebrow">Core Architecture</span>
          <h2 id="principles-heading" className="ds-principles__title">
            Built Around Three Core Principles
          </h2>
          <p className="ds-principles__subtitle">
            Engineered to replace blind trust in remote storage providers with
            provable client-side cryptographic guarantees.
          </p>
        </div>

        <div className="ds-grid ds-principles__grid" role="list">
          {PRINCIPLES.map((principle) => (
            <article
              key={principle.id}
              className="ds-principle-card"
              role="listitem"
            >
              <div className="ds-principle-card__icon-wrapper">
                {principle.icon}
              </div>
              <h3 className="ds-principle-card__heading">{principle.title}</h3>
              <p
                style={{
                  color: 'var(--color-text-primary)',
                  fontWeight: 500,
                  fontSize: 'var(--text-sm)',
                  marginBottom: 'var(--space-2)',
                }}
              >
                {principle.tagline}
              </p>
              <p className="ds-principle-card__description">{principle.detail}</p>
              <div className="ds-principle-card__footer">
                <span>{principle.bullet}</span>
              </div>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
};
