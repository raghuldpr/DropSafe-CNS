import React from 'react';
import { LockIcon, KeyIcon, ShieldIcon, VerifiedIcon } from './Icons';
import './SecuritySection.css';

export const SecuritySection: React.FC = () => {
  return (
    <section id="security" className="ds-security" aria-labelledby="security-heading">
      <div className="ds-container">
        <div className="ds-security__inner">
          <div className="ds-security__content">
            <span className="ds-security__eyebrow">Cryptographic Integrity</span>
            <h2 id="security-heading" className="ds-security__title">
              Designed for Total Control Over Your Data
            </h2>
            <p className="ds-security__intro">
              DropSafe fundamentally alters the file sharing trust boundary. Rather than
              relying on storage servers to guard plaintext files, files are secured
              at rest, in transit, and during delegation.
            </p>

            <ul className="ds-security__list">
              <li className="ds-security__item">
                <span className="ds-security__item-num">1</span>
                <div className="ds-security__item-text">
                  <h4>Client-Side Key Generation</h4>
                  <p>
                    Encryption keys are derived locally on your device. The cloud backend
                    never receives your raw encryption keys or unencrypted file bytes.
                  </p>
                </div>
              </li>

              <li className="ds-security__item">
                <span className="ds-security__item-num">2</span>
                <div className="ds-security__item-text">
                  <h4>Fine-Grained Policy Access</h4>
                  <p>
                    Attribute-Based Access Control policies evaluate role, time, or recipient
                    attributes before access grants are issued.
                  </p>
                </div>
              </li>

              <li className="ds-security__item">
                <span className="ds-security__item-num">3</span>
                <div className="ds-security__item-text">
                  <h4>Verifiable Event Commitments</h4>
                  <p>
                    Key file events and policy changes produce auditable cryptographic records,
                    preventing hidden tampering or retroactive log altering.
                  </p>
                </div>
              </li>
            </ul>
          </div>

          <div className="ds-security__panel" aria-label="Cryptographic Flow Summary">
            <div className="ds-security__panel-header">
              <div className="ds-security__panel-title">
                <ShieldIcon size={18} className="ds-principle-icon" />
                <span>Security Pipeline</span>
              </div>
              <span className="ds-security__panel-badge">Client-Side Verified</span>
            </div>

            <div className="ds-flow-step">
              <div className="ds-flow-step__icon">
                <LockIcon size={20} />
              </div>
              <div className="ds-flow-step__info">
                <span className="ds-flow-step__name">1. Local Encryption</span>
                <span className="ds-flow-step__sub">Browser encrypts file before upload</span>
              </div>
            </div>

            <div className="ds-flow-connector" />

            <div className="ds-flow-step">
              <div className="ds-flow-step__icon">
                <KeyIcon size={20} />
              </div>
              <div className="ds-flow-step__info">
                <span className="ds-flow-step__name">2. Key Derivation &amp; Envelope</span>
                <span className="ds-flow-step__sub">Recipients authorized via public-key exchange</span>
              </div>
            </div>

            <div className="ds-flow-connector" />

            <div className="ds-flow-step">
              <div className="ds-flow-step__icon">
                <ShieldIcon size={20} />
              </div>
              <div className="ds-flow-step__info">
                <span className="ds-flow-step__name">3. Blind Storage Relaying</span>
                <span className="ds-flow-step__sub">Host stores ciphertext; unable to read content</span>
              </div>
            </div>

            <div className="ds-flow-connector" />

            <div className="ds-flow-step">
              <div className="ds-flow-step__icon">
                <VerifiedIcon size={20} />
              </div>
              <div className="ds-flow-step__info">
                <span className="ds-flow-step__name">4. Audited Decryption</span>
                <span className="ds-flow-step__sub">Access verified and recorded in audit log</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
