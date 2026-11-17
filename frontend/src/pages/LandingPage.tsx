import React, { useState } from 'react';
import { Navbar } from '../components/Navbar';
import { Hero } from '../components/Hero';
import { Principles } from '../components/Principles';
import { SecuritySection } from '../components/SecuritySection';
import { Footer } from '../components/Footer';
import { NoticeModal } from '../components/NoticeModal';

interface LandingPageProps {
  onNavigate?: (route: 'landing' | 'login' | 'register') => void;
}

export const LandingPage: React.FC<LandingPageProps> = ({ onNavigate }) => {
  const [modalAction, setModalAction] = useState<string | null>(null);

  const handleActionClick = (actionName: string) => {
    if (actionName === 'Sign In' && onNavigate) {
      onNavigate('login');
      return;
    }
    if (actionName === 'Get Started' && onNavigate) {
      onNavigate('register');
      return;
    }
    setModalAction(actionName);
  };

  const handleExploreSecurity = () => {
    const securityElem = document.getElementById('security');
    if (securityElem) {
      securityElem.scrollIntoView({ behavior: 'smooth' });
    }
  };

  return (
    <div className="ds-landing-page">
      {/* Cinematic Cloud Hero Scene */}
      <div className="dropsafe-cloud-scene">
        <div className="dropsafe-cloud-scene__image" aria-hidden="true" />
        <div className="dropsafe-cloud-scene__shade" aria-hidden="true" />
        <div className="dropsafe-cloud-scene__glow" aria-hidden="true" />
        <div className="dropsafe-cloud-scene__stars" aria-hidden="true" />

        <div className="dropsafe-cloud-content">
          <Navbar onActionClick={handleActionClick} />
          <Hero
            onGetStarted={() => handleActionClick('Get Started')}
            onExploreSecurity={handleExploreSecurity}
          />
        </div>
      </div>

      {/* Core Principles Section */}
      <Principles />

      {/* Security Architecture & Verifiable Flow Section */}
      <SecuritySection />

      {/* Footer */}
      <Footer onActionClick={handleActionClick} />

      {/* Milestone status dialog for informational actions */}
      <NoticeModal
        actionName={modalAction}
        onClose={() => setModalAction(null)}
      />
    </div>
  );
};
