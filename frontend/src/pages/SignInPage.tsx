import React, { useState } from 'react';
import { ArrowLeftIcon, EyeIcon, EyeOffIcon } from '../components/Icons';
import { useAuth } from '../context/AuthContext';
import './SignInPage.css';

interface SignInPageProps {
  onNavigate: (route: 'landing' | 'login' | 'register' | 'dashboard') => void;
}

export const SignInPage: React.FC<SignInPageProps> = ({ onNavigate }) => {
  const { login } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string }>({});
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [forgotPasswordNotice, setForgotPasswordNotice] = useState(false);

  const validateForm = (): boolean => {
    const newErrors: { email?: string; password?: string } = {};

    if (!email.trim()) {
      newErrors.email = 'Email address is required.';
    } else {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email.trim())) {
        newErrors.email = 'Please enter a valid email address.';
      }
    }

    if (!password) {
      newErrors.password = 'Password is required.';
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);

    if (!validateForm()) {
      return;
    }

    setIsLoading(true);

    try {
      await login(email.trim(), password);
      setIsLoading(false);
      onNavigate('dashboard');
    } catch (err: any) {
      setIsLoading(false);
      setErrorMessage(err.message || 'Authentication failed. Please check your credentials.');
    }
  };

  // One-click demo login: fills the form and signs in immediately.
  const handleQuickFill = async (demoEmail: string, demoPass: string) => {
    setEmail(demoEmail);
    setPassword(demoPass);
    setErrors({});
    setErrorMessage(null);
    setIsLoading(true);
    try {
      await login(demoEmail, demoPass);
      setIsLoading(false);
      onNavigate('dashboard');
    } catch (err: any) {
      setIsLoading(false);
      setErrorMessage(err.message || 'Authentication failed. Please check your credentials.');
    }
  };

  return (
    <div className="ds-auth-page">
      {/* Background Cloud Atmosphere */}
      <div className="dropsafe-cloud-scene">
        <div className="dropsafe-cloud-scene__image" aria-hidden="true" />
        <div className="dropsafe-cloud-scene__shade" aria-hidden="true" />
        <div className="dropsafe-cloud-scene__glow" aria-hidden="true" />
        <div className="dropsafe-cloud-scene__stars" aria-hidden="true" />

        <div className="dropsafe-cloud-content" style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}>
          {/* Header Bar */}
          <header className="ds-auth-nav" role="banner">
            <a
              href="#/"
              className="ds-auth-nav__brand"
              onClick={(e) => {
                e.preventDefault();
                onNavigate('landing');
              }}
              aria-label="DropSafe Home"
            >
              <img
                src="/assets/dropsafe-logo.png"
                alt="DropSafe"
                className="ds-auth-nav__logo"
              />
            </a>

            <button
              type="button"
              className="ds-auth-nav__back"
              onClick={() => onNavigate('landing')}
              aria-label="Back to landing page"
            >
              <ArrowLeftIcon size={16} aria-hidden="true" />
              <span>Back to Home</span>
            </button>
          </header>

          {/* Centered Auth Card */}
          <main className="ds-auth-main">
            <div className="ds-auth-card" role="region" aria-labelledby="signin-heading">
              <div className="ds-auth-card__header">
                <h1 id="signin-heading" className="ds-auth-card__title">
                  Welcome Back
                </h1>
                <p className="ds-auth-card__subtitle">
                  Sign in to your DropSafe account.
                </p>
              </div>

              <form className="ds-auth-form" onSubmit={handleSubmit} noValidate>
                {/* Email Field */}
                <div className="ds-form-group">
                  <label htmlFor="signin-email" className="ds-form-label">
                    Email address
                  </label>
                  <div className="ds-input-wrapper">
                    <input
                      id="signin-email"
                      type="email"
                      className={`ds-input ${errors.email ? 'ds-input--error' : ''}`}
                      placeholder="name@example.com"
                      value={email}
                      onChange={(e) => {
                        setEmail(e.target.value);
                        if (errors.email) setErrors((prev) => ({ ...prev, email: undefined }));
                      }}
                      autoComplete="email"
                      autoFocus
                      disabled={isLoading}
                      aria-invalid={Boolean(errors.email)}
                      aria-describedby={errors.email ? 'email-error' : undefined}
                    />
                  </div>
                  {errors.email && (
                    <span id="email-error" className="ds-form-error" role="alert">
                      {errors.email}
                    </span>
                  )}
                </div>

                {/* Password Field */}
                <div className="ds-form-group">
                  <div className="ds-form-label-row">
                    <label htmlFor="signin-password" className="ds-form-label">
                      Password
                    </label>
                    <button
                      type="button"
                      className="ds-form-forgot-link"
                      onClick={() => setForgotPasswordNotice(!forgotPasswordNotice)}
                    >
                      Forgot Password?
                    </button>
                  </div>
                  <div className="ds-input-wrapper">
                    <input
                      id="signin-password"
                      type={showPassword ? 'text' : 'password'}
                      className={`ds-input ds-input--password ${
                        errors.password ? 'ds-input--error' : ''
                      }`}
                      placeholder="Enter your password"
                      value={password}
                      onChange={(e) => {
                        setPassword(e.target.value);
                        if (errors.password) setErrors((prev) => ({ ...prev, password: undefined }));
                      }}
                      autoComplete="current-password"
                      disabled={isLoading}
                      aria-invalid={Boolean(errors.password)}
                      aria-describedby={errors.password ? 'password-error' : undefined}
                    />
                    <button
                      type="button"
                      className="ds-input-toggle"
                      onClick={() => setShowPassword(!showPassword)}
                      aria-label={showPassword ? 'Hide password' : 'Show password'}
                      tabIndex={0}
                    >
                      {showPassword ? <EyeOffIcon size={18} /> : <EyeIcon size={18} />}
                    </button>
                  </div>
                  {errors.password && (
                    <span id="password-error" className="ds-form-error" role="alert">
                      {errors.password}
                    </span>
                  )}
                </div>

                {/* Forgot Password Notice */}
                {forgotPasswordNotice && (
                  <div className="ds-auth-info-banner" role="status">
                    Password recovery workflow will be available in an upcoming milestone once the backend authentication service is connected.
                  </div>
                )}

                {/* Primary Sign In Button */}
                <button
                  type="submit"
                  className="ds-btn ds-btn--submit"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
                      <span className="ds-btn-spinner" aria-hidden="true" />
                      <span>Signing in...</span>
                    </span>
                  ) : (
                    'Sign In'
                  )}
                </button>
              </form>

              {/* Error Notice */}
              {errorMessage && (
                <div className="ds-auth-notice" style={{ borderColor: 'var(--color-danger, #ef4444)', marginTop: '16px' }} role="alert">
                  <span className="ds-auth-notice__title" style={{ color: 'var(--color-danger, #ef4444)' }}>Sign In Failed</span>
                  <p>{errorMessage}</p>
                </div>
              )}

              {/* Demo Account Quick-Fill Shortcuts */}
              <div style={{ marginTop: '20px', padding: '12px', background: 'rgba(255, 255, 255, 0.03)', borderRadius: '8px', border: '1px solid rgba(255, 255, 255, 0.08)' }}>
                <div style={{ fontSize: '11px', textTransform: 'uppercase', letterSpacing: '0.05em', color: 'var(--color-text-secondary, #94a3b8)', marginBottom: '8px' }}>
                  Quick Demo Accounts (one-click sign in)
                </div>
                <div style={{ display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
                  <button
                    type="button"
                    style={{ fontSize: '12px', padding: '4px 8px', borderRadius: '4px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', cursor: 'pointer' }}
                    onClick={() => handleQuickFill('alice@dropsafe.local', 'AlicePass123!')}
                  >
                    Alice (Owner)
                  </button>
                  <button
                    type="button"
                    style={{ fontSize: '12px', padding: '4px 8px', borderRadius: '4px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', cursor: 'pointer' }}
                    onClick={() => handleQuickFill('bob@dropsafe.local', 'BobPass123!')}
                  >
                    Bob (Finance)
                  </button>
                  <button
                    type="button"
                    style={{ fontSize: '12px', padding: '4px 8px', borderRadius: '4px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', cursor: 'pointer' }}
                    onClick={() => handleQuickFill('charlie@dropsafe.local', 'CharliePass123!')}
                  >
                    Charlie (Contractor)
                  </button>
                  <button
                    type="button"
                    style={{ fontSize: '12px', padding: '4px 8px', borderRadius: '4px', background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', color: '#fff', cursor: 'pointer' }}
                    onClick={() => handleQuickFill('admin@dropsafe.local', 'AdminPass123!')}
                  >
                    Admin
                  </button>
                </div>
              </div>

              {/* Card Footer */}
              <div className="ds-auth-card__footer">
                <span>Don&apos;t have an account?</span>
                <button
                  type="button"
                  className="ds-auth-link"
                  onClick={() => onNavigate('register')}
                >
                  Create Account
                </button>
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};
