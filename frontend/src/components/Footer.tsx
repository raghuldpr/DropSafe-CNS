import React from 'react';
import './Footer.css';

interface FooterProps {
  onActionClick: (actionName: string) => void;
}

const CURRENT_YEAR = new Date().getFullYear();

export const Footer: React.FC<FooterProps> = ({ onActionClick }) => {
  return (
    <footer className="ds-footer" role="contentinfo">
      <div className="ds-container">
        <div className="ds-footer__top">
          <div className="ds-footer__brand-col">
            <img
              src="/assets/dropsafe-logo.png"
              alt="DropSafe"
              className="ds-footer__logo"
            />
            <p className="ds-footer__tagline">
              Your Files. Your Control.
              <br />
              Secure cloud file-sharing engineered with client-side encryption.
            </p>
          </div>

          <div className="ds-footer__nav-cols">
            <div>
              <h4 className="ds-footer__col-title">Product</h4>
              <ul className="ds-footer__links">
                <li>
                  <a href="#principles" className="ds-footer__link">
                    Features
                  </a>
                </li>
                <li>
                  <a href="#security" className="ds-footer__link">
                    Security Architecture
                  </a>
                </li>
                <li>
                  <button
                    type="button"
                    className="ds-footer__link"
                    onClick={() => onActionClick('Documentation')}
                  >
                    Documentation
                  </button>
                </li>
              </ul>
            </div>

            <div>
              <h4 className="ds-footer__col-title">Security &amp; Legal</h4>
              <ul className="ds-footer__links">
                <li>
                  <button
                    type="button"
                    className="ds-footer__link"
                    onClick={() => onActionClick('Privacy Policy')}
                  >
                    Privacy
                  </button>
                </li>
                <li>
                  <button
                    type="button"
                    className="ds-footer__link"
                    onClick={() => onActionClick('Security Policy')}
                  >
                    Security Model
                  </button>
                </li>
                <li>
                  <button
                    type="button"
                    className="ds-footer__link"
                    onClick={() => onActionClick('Terms of Service')}
                  >
                    Terms
                  </button>
                </li>
              </ul>
            </div>
          </div>
        </div>

        <div className="ds-footer__bottom">
          <p>&copy; {CURRENT_YEAR} DropSafe. Cryptography Capstone Project.</p>
          <div className="ds-footer__badge">
            <span className="ds-footer__badge-dot" aria-hidden="true" />
            <span>Frontend Preview v0.1</span>
          </div>
        </div>
      </div>
    </footer>
  );
};
