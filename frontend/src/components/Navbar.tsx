import React, { useState } from 'react';
import './Navbar.css';

interface NavbarProps {
  onActionClick: (actionName: string) => void;
}

export const Navbar: React.FC<NavbarProps> = ({ onActionClick }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  const toggleMobileMenu = () => {
    setMobileMenuOpen(!mobileMenuOpen);
  };

  const handleLinkClick = (e: React.MouseEvent<HTMLAnchorElement>, targetId: string) => {
    e.preventDefault();
    setMobileMenuOpen(false);
    const element = document.getElementById(targetId);
    if (element) {
      element.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <header className="ds-navbar" role="banner">
      <div className="ds-container ds-navbar__inner">
        <a
          href="#/"
          className="ds-navbar__brand"
          aria-label="DropSafe Home"
          onClick={(e) => {
            e.preventDefault();
            window.scrollTo({ top: 0, behavior: 'smooth' });
          }}
        >
          <img
            src="/assets/dropsafe-logo.png"
            alt="DropSafe"
            className="ds-navbar__logo"
          />
        </a>

        {/* Desktop Navigation */}
        <nav className="ds-navbar__nav" aria-label="Main Navigation">
          <ul className="ds-navbar__links">
            <li>
              <a
                href="#principles"
                className="ds-navbar__link"
                onClick={(e) => handleLinkClick(e, 'principles')}
              >
                Features
              </a>
            </li>
            <li>
              <a
                href="#security"
                className="ds-navbar__link"
                onClick={(e) => handleLinkClick(e, 'security')}
              >
                Security
              </a>
            </li>
            <li>
              <button
                type="button"
                className="ds-navbar__link"
                onClick={() => onActionClick('Documentation')}
              >
                Documentation
              </button>
            </li>
          </ul>
        </nav>

        {/* Desktop Actions */}
        <div className="ds-navbar__actions">
          <button
            type="button"
            className="ds-btn ds-btn--ghost"
            onClick={() => onActionClick('Sign In')}
          >
            Sign In
          </button>
          <button
            type="button"
            className="ds-btn ds-btn--primary"
            onClick={() => onActionClick('Get Started')}
          >
            Get Started
          </button>

          {/* Mobile Menu Button */}
          <button
            type="button"
            className="ds-navbar__toggle"
            onClick={toggleMobileMenu}
            aria-expanded={mobileMenuOpen}
            aria-label="Toggle navigation menu"
          >
            <svg
              width="24"
              height="24"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              {mobileMenuOpen ? (
                <>
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </>
              ) : (
                <>
                  <line x1="3" y1="12" x2="21" y2="12" />
                  <line x1="3" y1="6" x2="21" y2="6" />
                  <line x1="3" y1="18" x2="21" y2="18" />
                </>
              )}
            </svg>
          </button>
        </div>
      </div>

      {/* Mobile Menu Dropdown */}
      {mobileMenuOpen && (
        <div className="ds-navbar__menu-mobile">
          <a
            href="#principles"
            className="ds-navbar__link"
            onClick={(e) => handleLinkClick(e, 'principles')}
          >
            Features
          </a>
          <a
            href="#security"
            className="ds-navbar__link"
            onClick={(e) => handleLinkClick(e, 'security')}
          >
            Security
          </a>
          <button
            type="button"
            className="ds-navbar__link"
            style={{ textAlign: 'left', width: '100%' }}
            onClick={() => {
              setMobileMenuOpen(false);
              onActionClick('Documentation');
            }}
          >
            Documentation
          </button>
          <div className="ds-navbar__mobile-actions">
            <button
              type="button"
              className="ds-btn ds-btn--secondary"
              onClick={() => {
                setMobileMenuOpen(false);
                onActionClick('Sign In');
              }}
            >
              Sign In
            </button>
            <button
              type="button"
              className="ds-btn ds-btn--primary"
              onClick={() => {
                setMobileMenuOpen(false);
                onActionClick('Get Started');
              }}
            >
              Get Started
            </button>
          </div>
        </div>
      )}
    </header>
  );
};
