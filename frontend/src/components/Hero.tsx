import React from 'react';
import { ArrowRightIcon, CheckIcon } from './Icons';
import './Hero.css';

interface HeroProps {
  onGetStarted: () => void;
  onExploreSecurity: () => void;
}

export const Hero: React.FC<HeroProps> = ({ onGetStarted, onExploreSecurity }) => {
  return (
    <section id="hero" className="ds-hero" aria-labelledby="hero-heading">
      <div className="ds-container">
        <div className="ds-hero__content">
          <div className="ds-hero__badge">
            <span className="ds-hero__badge-indicator" aria-hidden="true" />
            <span>Cryptographic File Security</span>
          </div>

          <h1 id="hero-heading" className="ds-hero__headline">
            <span className="ds-hero__headline-accent">Your Files.</span>{' '}
            <span className="ds-hero__headline-accent">Your Control.</span>
          </h1>

          <p className="ds-hero__description">
            Store, share, and manage your files with client-side encryption and
            access controls designed around you.
          </p>

          <div className="ds-hero__actions">
            <button
              type="button"
              className="ds-btn ds-hero__btn-primary"
              onClick={onGetStarted}
            >
              <span>Get Started</span>
              <ArrowRightIcon size={16} aria-hidden="true" />
            </button>
            <button
              type="button"
              className="ds-btn ds-hero__btn-secondary"
              onClick={onExploreSecurity}
            >
              <span>Explore Security</span>
            </button>
          </div>

          <div className="ds-hero__trust-points">
            <div className="ds-hero__trust-item">
              <CheckIcon size={16} className="ds-hero__trust-icon" aria-hidden="true" />
              <span>Keys never leave your browser</span>
            </div>
            <div className="ds-hero__trust-item">
              <CheckIcon size={16} className="ds-hero__trust-icon" aria-hidden="true" />
              <span>Attribute-based access control</span>
            </div>
            <div className="ds-hero__trust-item">
              <CheckIcon size={16} className="ds-hero__trust-icon" aria-hidden="true" />
              <span>Verifiable audit trail</span>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
};
