import React, { useState } from 'react';
import { ArrowLeftIcon, EyeIcon, EyeOffIcon } from '../components/Icons';
import { useAuth } from '../context/AuthContext';
import './RegisterPage.css';

interface RegisterPageProps {
  onNavigate: (route: 'landing' | 'login' | 'register' | 'dashboard') => void;
}

export const RegisterPage: React.FC<RegisterPageProps> = ({ onNavigate }) => {
  const { register } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');

  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const [errors, setErrors] = useState<{
    fullName?: string;
    email?: string;
    password?: string;
    confirmPassword?: string;
  }>({});

  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const validateForm = (): boolean => {
    const newErrors: {
      fullName?: string;
      email?: string;
      password?: string;
      confirmPassword?: string;
    } = {};

    // 1. Full Name validation (trimmed)
    if (!fullName.trim()) {
      newErrors.fullName = 'Full name is required.';
    }

    // 2. Email Address validation
    if (!email.trim()) {
      newErrors.email = 'Email address is required.';
    } else {
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email.trim())) {
        newErrors.email = 'Please enter a valid email address.';
      }
    }

    // 3. Password validation (at least 8 characters)
    if (!password) {
      newErrors.password = 'Password is required.';
    } else if (password.length < 8) {
      newErrors.password = 'Password must be at least 8 characters long.';
    }

    // 4. Confirm Password validation (must match)
    if (!confirmPassword) {
      newErrors.confirmPassword = 'Please confirm your password.';
    } else if (confirmPassword !== password) {
      newErrors.confirmPassword = 'Passwords do not match.';
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
      await register(email.trim(), password, fullName.trim());
      setIsLoading(false);
      onNavigate('dashboard');
    } catch (err: any) {
      setIsLoading(false);
      setErrorMessage(err.message || 'Registration failed. Please try again.');
    }
  };

  return (
    <div className="ds-register-page">
      {/* Background Cloud Atmosphere */}
      <div className="dropsafe-cloud-scene">
        <div className="dropsafe-cloud-scene__image" aria-hidden="true" />
        <div className="dropsafe-cloud-scene__shade" aria-hidden="true" />
        <div className="dropsafe-cloud-scene__glow" aria-hidden="true" />
        <div className="dropsafe-cloud-scene__stars" aria-hidden="true" />

        <div
          className="dropsafe-cloud-content"
          style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}
        >
          {/* Header Bar */}
          <header className="ds-register-nav" role="banner">
            <a
              href="#/"
              className="ds-register-nav__brand"
              onClick={(e) => {
                e.preventDefault();
                onNavigate('landing');
              }}
              aria-label="DropSafe Home"
            >
              <img
                src="/assets/dropsafe-logo.png"
                alt="DropSafe"
                className="ds-register-nav__logo"
              />
            </a>

            <div className="ds-register-nav__right">
              <span className="ds-register-nav__text">Already have an account?</span>
              <button
                type="button"
                className="ds-register-nav__signin-btn"
                onClick={() => onNavigate('login')}
              >
                Sign In
              </button>
            </div>
          </header>

          {/* Centered Registration Card */}
          <main className="ds-register-main">
            <div
              className="ds-register-card"
              role="region"
              aria-labelledby="register-heading"
            >
              <div className="ds-register-card__header">
                <h1 id="register-heading" className="ds-register-card__title">
                  Create Your Account
                </h1>
                <p className="ds-register-card__subtitle">
                  Get started with secure, controlled file sharing.
                </p>
              </div>

              <form className="ds-register-form" onSubmit={handleSubmit} noValidate>
                {/* Full Name Field */}
                <div className="ds-form-group">
                  <label htmlFor="register-name" className="ds-form-label">
                    Full Name
                  </label>
                  <div className="ds-input-wrapper">
                    <input
                      id="register-name"
                      type="text"
                      className={`ds-input ${errors.fullName ? 'ds-input--error' : ''}`}
                      placeholder="e.g. Alex Morgan"
                      value={fullName}
                      onChange={(e) => {
                        setFullName(e.target.value);
                        if (errors.fullName) {
                          setErrors((prev) => ({ ...prev, fullName: undefined }));
                        }
                      }}
                      autoComplete="name"
                      autoFocus
                      disabled={isLoading}
                      aria-invalid={Boolean(errors.fullName)}
                      aria-describedby={errors.fullName ? 'name-error' : undefined}
                    />
                  </div>
                  {errors.fullName && (
                    <span id="name-error" className="ds-form-error" role="alert">
                      {errors.fullName}
                    </span>
                  )}
                </div>

                {/* Email Address Field */}
                <div className="ds-form-group">
                  <label htmlFor="register-email" className="ds-form-label">
                    Email Address
                  </label>
                  <div className="ds-input-wrapper">
                    <input
                      id="register-email"
                      type="email"
                      className={`ds-input ${errors.email ? 'ds-input--error' : ''}`}
                      placeholder="name@example.com"
                      value={email}
                      onChange={(e) => {
                        setEmail(e.target.value);
                        if (errors.email) {
                          setErrors((prev) => ({ ...prev, email: undefined }));
                        }
                      }}
                      autoComplete="email"
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
                  <label htmlFor="register-password" className="ds-form-label">
                    Password
                  </label>
                  <div className="ds-input-wrapper">
                    <input
                      id="register-password"
                      type={showPassword ? 'text' : 'password'}
                      className={`ds-input ds-input--with-toggle ${
                        errors.password ? 'ds-input--error' : ''
                      }`}
                      placeholder="At least 8 characters"
                      value={password}
                      onChange={(e) => {
                        setPassword(e.target.value);
                        if (errors.password) {
                          setErrors((prev) => ({ ...prev, password: undefined }));
                        }
                      }}
                      autoComplete="new-password"
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

                {/* Confirm Password Field */}
                <div className="ds-form-group">
                  <label htmlFor="register-confirm-password" className="ds-form-label">
                    Confirm Password
                  </label>
                  <div className="ds-input-wrapper">
                    <input
                      id="register-confirm-password"
                      type={showConfirmPassword ? 'text' : 'password'}
                      className={`ds-input ds-input--with-toggle ${
                        errors.confirmPassword ? 'ds-input--error' : ''
                      }`}
                      placeholder="Re-enter your password"
                      value={confirmPassword}
                      onChange={(e) => {
                        setConfirmPassword(e.target.value);
                        if (errors.confirmPassword) {
                          setErrors((prev) => ({ ...prev, confirmPassword: undefined }));
                        }
                      }}
                      autoComplete="new-password"
                      disabled={isLoading}
                      aria-invalid={Boolean(errors.confirmPassword)}
                      aria-describedby={
                        errors.confirmPassword ? 'confirm-password-error' : undefined
                      }
                    />
                    <button
                      type="button"
                      className="ds-input-toggle"
                      onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                      aria-label={
                        showConfirmPassword
                          ? 'Hide confirmed password'
                          : 'Show confirmed password'
                      }
                      tabIndex={0}
                    >
                      {showConfirmPassword ? <EyeOffIcon size={18} /> : <EyeIcon size={18} />}
                    </button>
                  </div>
                  {errors.confirmPassword && (
                    <span
                      id="confirm-password-error"
                      className="ds-form-error"
                      role="alert"
                    >
                      {errors.confirmPassword}
                    </span>
                  )}
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  className="ds-btn ds-btn--submit"
                  disabled={isLoading}
                >
                  {isLoading ? (
                    <span
                      style={{
                        display: 'inline-flex',
                        alignItems: 'center',
                        gap: '8px',
                        justifyContent: 'center',
                      }}
                    >
                      <span className="ds-btn-spinner" aria-hidden="true" />
                      <span>Creating Account...</span>
                    </span>
                  ) : (
                    'Create Account'
                  )}
                </button>

                {/* Consent Note */}
                <p className="ds-register-consent">
                  By creating an account, you agree to use DropSafe responsibly.
                </p>
              </form>

              {/* Error Notice */}
              {errorMessage && (
                <div className="ds-register-notice" style={{ borderColor: 'var(--color-danger, #ef4444)' }} role="alert">
                  <span className="ds-register-notice__title" style={{ color: 'var(--color-danger, #ef4444)' }}>Registration Failed</span>
                  <p>{errorMessage}</p>
                </div>
              )}

              {/* Card Footer with Back to Home Link */}
              <div className="ds-register-card__footer">
                <button
                  type="button"
                  className="ds-register-home-link"
                  onClick={() => onNavigate('landing')}
                  aria-label="Back to landing page"
                >
                  <ArrowLeftIcon size={14} aria-hidden="true" />
                  <span>Back to Home</span>
                </button>
              </div>
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};
