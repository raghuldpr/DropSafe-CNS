import React, { useState, useEffect } from 'react';
import { LandingPage } from './pages/LandingPage';
import { SignInPage } from './pages/SignInPage';
import { RegisterPage } from './pages/RegisterPage';
import { UploadPage } from './pages/UploadPage';
import { UploadProgressPage } from './pages/UploadProgressPage';
import { DashboardPage } from './pages/DashboardPage';
import { MyFilesPage } from './pages/MyFilesPage';
import { FileDetailsPage } from './pages/FileDetailsPage';
import { ShareFilePage } from './pages/ShareFilePage';
import { SharedWithMePage } from './pages/SharedWithMePage';
import { SharedByMePage } from './pages/SharedByMePage';
import { AccessPoliciesPage } from './pages/AccessPoliciesPage';
import { AccessDeniedPage } from './pages/AccessDeniedPage';
import { AuditLogPage } from './pages/AuditLogPage';
import { SettingsPage } from './pages/SettingsPage';
import { AdminPage } from './pages/AdminPage';

export type AppRoute =
  | 'landing'
  | 'login'
  | 'register'
  | 'upload'
  | 'upload-progress'
  | 'dashboard'
  | 'files'
  | 'file-details'
  | 'share'
  | 'shared-with-me'
  | 'shared-by-me'
  | 'policies'
  | 'access-denied'
  | 'audit-log'
  | 'settings'
  | 'admin'
  | 'app';

export const App: React.FC = () => {
  const [currentRoute, setCurrentRoute] = useState<AppRoute>('landing');
  // Shared in-memory file selection state between upload screens
  const [selectedFiles, setSelectedFiles] = useState<File[]>([]);

  // Hash-based routing to support navigation without full page reloads
  useEffect(() => {
    if ('scrollRestoration' in window.history) {
      window.history.scrollRestoration = 'manual';
    }

    const handleHashChange = () => {
      const hash = window.location.hash.toLowerCase();
      if (hash === '' || hash === '#' || hash === '#/') setCurrentRoute('landing');
      else if (hash === '#/login') setCurrentRoute('login');
      else if (hash === '#/register') setCurrentRoute('register');
      else if (hash === '#/upload') setCurrentRoute('upload');
      else if (hash === '#/upload-progress') setCurrentRoute('upload-progress');
      else if (hash === '#/files') setCurrentRoute('files');
      else if (hash.startsWith('#/file-details')) setCurrentRoute('file-details');
      else if (hash.startsWith('#/share')) setCurrentRoute('share');
      else if (hash.startsWith('#/shared-with-me')) setCurrentRoute('shared-with-me');
      else if (hash.startsWith('#/shared-by-me')) setCurrentRoute('shared-by-me');
      else if (hash.startsWith('#/policies')) setCurrentRoute('policies');
      else if (hash.startsWith('#/access-denied')) setCurrentRoute('access-denied');
      else if (hash.startsWith('#/audit-log')) setCurrentRoute('audit-log');
      else if (hash.startsWith('#/settings')) setCurrentRoute('settings');
      else if (hash.startsWith('#/admin')) setCurrentRoute('admin');
      else if (hash === '#/dashboard' || hash === '#/app') setCurrentRoute('dashboard');
      else setCurrentRoute('landing');

      window.scrollTo(0, 0);
    };

    window.addEventListener('hashchange', handleHashChange);
    handleHashChange();
    return () => window.removeEventListener('hashchange', handleHashChange);
  }, []);

  const navigateTo = (route: AppRoute) => {
    const targetHash = route === 'landing' ? '' : `#/${route}`;
    const currentHash = window.location.hash;
    const isAlreadyAtTarget =
      route === 'landing'
        ? currentHash === '' || currentHash === '#' || currentHash === '#/'
        : currentHash.toLowerCase() === targetHash.toLowerCase();

    if (isAlreadyAtTarget) {
      setCurrentRoute(route);
      window.scrollTo(0, 0);
    } else {
      window.location.hash = targetHash;
    }
  };

  // Route: Sign In Page
  if (currentRoute === 'login') {
    return <SignInPage onNavigate={navigateTo} />;
  }

  // Route: Create Account / Register Page
  if (currentRoute === 'register') {
    return <RegisterPage onNavigate={navigateTo} />;
  }

  // Route: Initial Upload Screen
  if (currentRoute === 'upload') {
    return (
      <UploadPage
        onNavigate={navigateTo}
        selectedFiles={selectedFiles}
        setSelectedFiles={setSelectedFiles}
      />
    );
  }

  // Route: Upload Progress & Completion UI
  if (currentRoute === 'upload-progress') {
    return (
      <UploadProgressPage
        onNavigate={navigateTo}
        selectedFiles={selectedFiles}
        onClearFiles={() => setSelectedFiles([])}
      />
    );
  }

  // Route: Main Application Dashboard Workspace
  if (currentRoute === 'dashboard' || currentRoute === 'app') {
    return <DashboardPage onNavigate={navigateTo} />;
  }

  // Route: My Files Screen
  if (currentRoute === 'files') {
    return <MyFilesPage onNavigate={navigateTo} />;
  }

  // Route: File Details Screen
  if (currentRoute === 'file-details') {
    return (
      <FileDetailsPage
        onNavigate={navigateTo}
        selectedFiles={selectedFiles}
      />
    );
  }

  // Route: Share File Screen
  if (currentRoute === 'share') {
    return (
      <ShareFilePage
        onNavigate={navigateTo}
        selectedFiles={selectedFiles}
      />
    );
  }

  // Route: Shared with Me Screen
  if (currentRoute === 'shared-with-me') {
    return <SharedWithMePage onNavigate={navigateTo} />;
  }

  // Route: Shared by Me Screen
  if (currentRoute === 'shared-by-me') {
    return (
      <SharedByMePage
        onNavigate={navigateTo}
        selectedFiles={selectedFiles}
      />
    );
  }

  // Route: Access Policies Screen
  if (currentRoute === 'policies') {
    return <AccessPoliciesPage onNavigate={navigateTo} />;
  }

  // Route: Access Denied Screen
  if (currentRoute === 'access-denied') {
    return <AccessDeniedPage onNavigate={navigateTo} />;
  }

  // Route: Audit Log Screen
  if (currentRoute === 'audit-log') {
    return <AuditLogPage onNavigate={navigateTo} />;
  }

  // Route: Settings Screen
  if (currentRoute === 'settings') {
    return <SettingsPage onNavigate={navigateTo} />;
  }

  // Route: Admin Console (backend enforces the admin role)
  if (currentRoute === 'admin') {
    return <AdminPage onNavigate={navigateTo} />;
  }

  // Default: Landing Page
  return <LandingPage onNavigate={navigateTo} />;
};

export default App;
