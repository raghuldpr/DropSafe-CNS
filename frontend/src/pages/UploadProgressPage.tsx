import React, { useState } from 'react';
import {
  UploadCloudIcon,
  DocumentIcon,
  CheckIcon,
  LockIcon,
  VerifiedIcon,
  ArrowLeftIcon,
} from '../components/Icons';
import { useAuth } from '../context/AuthContext';
import { documentApi } from '../services/api';
import {
  encryptFile,
  wrapDek,
  signDigest,
  getUserPrivateKey,
} from '../services/crypto';
import type { DocumentResponse } from '../types/api';
import './UploadProgressPage.css';

interface UploadProgressPageProps {
  onNavigate: (
    route:
      | 'landing'
      | 'login'
      | 'register'
      | 'upload'
      | 'upload-progress'
      | 'dashboard'
      | 'files'
      | 'audit-log'
  ) => void;
  selectedFiles: File[];
  onClearFiles?: () => void;
}

type PipelineStage = 'idle' | 'encrypting' | 'uploading' | 'finalizing' | 'completed' | 'error';

export const UploadProgressPage: React.FC<UploadProgressPageProps> = ({
  onNavigate,
  selectedFiles,
  onClearFiles,
}) => {
  const { user, keys, activeEncryptionKeyId, activeSigningKeyId } = useAuth();
  const [stage, setStage] = useState<PipelineStage>('idle');
  const [statusMessage, setStatusMessage] = useState<string>('Ready to encrypt and securely upload');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [completedDocs, setCompletedDocs] = useState<DocumentResponse[]>([]);

  // Helper to format bytes
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  const handleStartUpload = async () => {
    if (selectedFiles.length === 0 || !user) return;
    setErrorMessage(null);

    const activeEncKey = keys.find((k) => k.id === activeEncryptionKeyId) || keys.find((k) => k.key_purpose === 'encryption');
    if (!activeEncKey) {
      setErrorMessage('No active encryption key found for your account. Please visit Settings to register keys.');
      return;
    }

    try {
      const results: DocumentResponse[] = [];

      for (let i = 0; i < selectedFiles.length; i++) {
        const file = selectedFiles[i];

        // -----------------------------------------------------------
        // Stage 1 & 2: Local Client-Side AES-256-GCM Encryption
        // -----------------------------------------------------------
        setStage('encrypting');
        setStatusMessage(`Encrypting "${file.name}" with AES-256-GCM in browser memory...`);
        const encPkg = await encryptFile(file);

        // -----------------------------------------------------------
        // Stage 3: Initiate Upload Intent & Direct Storage PUT
        // -----------------------------------------------------------
        setStage('uploading');
        setStatusMessage(`Creating document entry for "${file.name}"...`);
        const doc = await documentApi.create(file.name, file.type || 'application/octet-stream');

        setStatusMessage(`Allocating object storage key for "${file.name}"...`);
        const versionIntent = await documentApi.createVersionIntent(
          doc.id,
          1,
          encPkg.ciphertextSizeBytes,
          encPkg.ciphertextSha256Hex,
          encPkg.manifest
        );

        setStatusMessage(`Requesting presigned upload URL...`);
        const uploadUrlInfo = await documentApi.getUploadUrl(doc.id, versionIntent.id);

        setStatusMessage(`Transmitting encrypted ciphertext to storage relay...`);
        await documentApi.uploadCiphertextToStorage(uploadUrlInfo.url, encPkg.ciphertext);

        // -----------------------------------------------------------
        // Stage 4: Wrap DEK Envelope & Sign Commitment
        // -----------------------------------------------------------
        setStage('finalizing');
        setStatusMessage(`Wrapping DEK envelope with your RSA-OAEP public key...`);
        const wrappedDekB64 = await wrapDek(encPkg.dek, activeEncKey.public_key_jwk);

        // Optional: Sign digest with client signing key if stored in IndexedDB
        let sigHex: string | undefined = undefined;
        let signingKeyId: string | undefined = undefined;

        if (activeSigningKeyId) {
          const sigPrivKey = await getUserPrivateKey(user.id, 'signing');
          if (sigPrivKey) {
            sigHex = await signDigest(encPkg.ciphertextSha256Hex, sigPrivKey);
            signingKeyId = activeSigningKeyId;
          }
        }

        setStatusMessage(`Finalizing version and recording audit event...`);
        const finalizedDoc = await documentApi.finalizeVersion(
          doc.id,
          versionIntent.id,
          wrappedDekB64,
          activeEncKey.id,
          sigHex,
          signingKeyId
        );

        results.push(finalizedDoc);
      }

      setCompletedDocs(results);
      setStage('completed');
      setStatusMessage('All files encrypted, stored, and audit-anchored successfully!');
    } catch (err: any) {
      console.error('[DropSafe Upload Error]:', err);
      setStage('error');
      setErrorMessage(err.message || 'Upload pipeline failed. Please retry.');
    }
  };

  return (
    <div className="ds-progress-page">
      {/* Cinematic Cloud Atmosphere */}
      <div className="dropsafe-cloud-scene">
        <div className="dropsafe-cloud-scene__image" aria-hidden="true" />
        <div className="dropsafe-cloud-scene__shade" aria-hidden="true" />
        <div className="dropsafe-cloud-scene__glow" aria-hidden="true" />
        <div className="dropsafe-cloud-scene__stars" aria-hidden="true" />

        <div
          className="dropsafe-cloud-content"
          style={{ minHeight: '100vh', display: 'flex', flexDirection: 'column' }}
        >
          {/* Navigation Bar */}
          <header className="ds-progress-nav" role="banner">
            <a
              href="#/"
              className="ds-progress-nav__brand"
              onClick={(e) => {
                e.preventDefault();
                onNavigate('dashboard');
              }}
              aria-label="DropSafe Home"
            >
              <img
                src="/assets/dropsafe-logo.png"
                alt="DropSafe"
                className="ds-progress-nav__logo"
              />
            </a>

            <div className="ds-progress-nav__right">
              <button
                type="button"
                className="ds-progress-nav__btn-back"
                onClick={() => {
                  onClearFiles?.();
                  onNavigate('upload');
                }}
                aria-label="Back to file selection"
              >
                <ArrowLeftIcon size={14} aria-hidden="true" />
                <span>Back to File Selection</span>
              </button>
            </div>
          </header>

          {/* Main Content */}
          <main className="ds-progress-main">
            <div className="ds-progress-container">
              {selectedFiles.length === 0 && stage !== 'completed' ? (
                /* Empty State */
                <div
                  className="ds-progress-card ds-progress-empty-card"
                  role="region"
                  aria-labelledby="empty-progress-heading"
                >
                  <div className="ds-progress-empty-icon" aria-hidden="true">
                    <DocumentIcon size={28} />
                  </div>
                  <h1 id="empty-progress-heading" className="ds-progress-title" style={{ fontSize: 'var(--text-xl)' }}>
                    No Files Selected
                  </h1>
                  <p className="ds-progress-subtitle">
                    You have not selected any files for upload yet. Choose files from
                    the upload screen to begin the preparation workflow.
                  </p>
                  <button
                    type="button"
                    className="ds-btn ds-btn--primary"
                    onClick={() => onNavigate('upload')}
                  >
                    Go to File Selection
                  </button>
                </div>
              ) : (
                /* Active Preparation Progress Interface */
                <>
                  <div className="ds-progress-header">
                    <h1 className="ds-progress-title">
                      {stage === 'completed'
                        ? 'Files Prepared & Secured'
                        : 'Secure Zero-Knowledge Upload'}
                    </h1>
                    <p className="ds-progress-subtitle">
                      {stage === 'completed'
                        ? 'Ciphertext committed to cloud storage with verified cryptographic envelopes.'
                        : 'Plaintext never leaves your browser. Files are encrypted client-side with AES-256-GCM.'}
                    </p>
                  </div>

                  <div className="ds-progress-card" role="region" aria-label="Upload preparation workflow">
                    {/* Summary Bar */}
                    <div className="ds-progress-summary-bar">
                      <div className="ds-progress-badge-group">
                        <span className="ds-progress-badge ds-progress-badge--primary">
                          {selectedFiles.length} {selectedFiles.length === 1 ? 'File' : 'Files'} Selected
                        </span>
                        <span className="ds-progress-badge ds-progress-badge--neutral">
                          {stage === 'completed' ? 'Encrypted & Committed' : 'Client-Side Sandbox'}
                        </span>
                      </div>
                      <span style={{ fontSize: 'var(--text-xs)', color: 'var(--color-text-muted)' }}>
                        {stage === 'completed'
                          ? 'Audit anchored in append-only ledger'
                          : 'Zero-Knowledge Envelope Protocol'}
                      </span>
                    </div>

                    {/* Selected Files List Box */}
                    <div className="ds-progress-files-box" aria-label="List of files to prepare">
                      {selectedFiles.map((f) => (
                        <div key={`${f.name}-${f.size}-${f.lastModified}`} className="ds-progress-file-item">
                          <div className="ds-progress-file-left">
                            <DocumentIcon size={16} className="ds-principle-icon" />
                            <span className="ds-progress-file-name" title={f.name}>
                              {f.name}
                            </span>
                          </div>
                          <span>{formatBytes(f.size)}</span>
                        </div>
                      ))}
                    </div>

                    {/* Error Box if any */}
                    {errorMessage && (
                      <div
                        style={{
                          margin: '16px 0',
                          padding: '12px 16px',
                          background: 'rgba(239, 68, 68, 0.1)',
                          border: '1px solid rgba(239, 68, 68, 0.3)',
                          borderRadius: '8px',
                          color: '#f87171',
                          fontSize: '13px',
                        }}
                      >
                        <strong>Upload Error:</strong> {errorMessage}
                      </div>
                    )}

                    {/* Workflow Stages */}
                    <section className="ds-workflow-section" aria-labelledby="workflow-stages-heading">
                      <h2 id="workflow-stages-heading" className="ds-workflow-title">
                        Upload Pipeline Stages
                      </h2>

                      <ol className="ds-workflow-steps">
                        {/* Stage 1: Files Selected */}
                        <li className="ds-workflow-step ds-workflow-step--done">
                          <div className="ds-workflow-step__icon" aria-hidden="true">
                            <CheckIcon size={18} />
                          </div>
                          <div className="ds-workflow-step__body">
                            <div className="ds-workflow-step__top">
                              <span className="ds-workflow-step__name">1. Files Selected</span>
                              <span className="ds-workflow-step__status ds-workflow-step__status--done">
                                Completed Locally
                              </span>
                            </div>
                            <p className="ds-workflow-step__desc">
                              Files validated in local browser session.
                            </p>
                          </div>
                        </li>

                        {/* Stage 2: Encryption */}
                        <li
                          className={`ds-workflow-step ${
                            stage === 'completed' || stage === 'uploading' || stage === 'finalizing'
                              ? 'ds-workflow-step--done'
                              : stage === 'encrypting'
                              ? 'ds-workflow-step--active'
                              : 'ds-workflow-step--pending'
                          }`}
                        >
                          <div className="ds-workflow-step__icon" aria-hidden="true">
                            <LockIcon size={18} />
                          </div>
                          <div className="ds-workflow-step__body">
                            <div className="ds-workflow-step__top">
                              <span className="ds-workflow-step__name">2. Client-Side Encryption</span>
                              <span
                                className={`ds-workflow-step__status ${
                                  stage === 'completed' || stage === 'uploading' || stage === 'finalizing'
                                    ? 'ds-workflow-step__status--done'
                                    : stage === 'encrypting'
                                    ? 'ds-workflow-step__status--done'
                                    : 'ds-workflow-step__status--waiting'
                                }`}
                              >
                                {stage === 'completed' || stage === 'uploading' || stage === 'finalizing'
                                  ? 'AES-256-GCM Encrypted'
                                  : stage === 'encrypting'
                                  ? 'Encrypting Now...'
                                  : 'Pending'}
                              </span>
                            </div>
                            <p className="ds-workflow-step__desc">
                              DEK generated and data encrypted locally with AES-256-GCM authenticated chunks.
                            </p>
                          </div>
                        </li>

                        {/* Stage 3: Cloud Upload */}
                        <li
                          className={`ds-workflow-step ${
                            stage === 'completed' || stage === 'finalizing'
                              ? 'ds-workflow-step--done'
                              : stage === 'uploading'
                              ? 'ds-workflow-step--active'
                              : 'ds-workflow-step--pending'
                          }`}
                        >
                          <div className="ds-workflow-step__icon" aria-hidden="true">
                            <UploadCloudIcon size={18} />
                          </div>
                          <div className="ds-workflow-step__body">
                            <div className="ds-workflow-step__top">
                              <span className="ds-workflow-step__name">3. Cloud Relay Upload</span>
                              <span
                                className={`ds-workflow-step__status ${
                                  stage === 'completed' || stage === 'finalizing'
                                    ? 'ds-workflow-step__status--done'
                                    : stage === 'uploading'
                                    ? 'ds-workflow-step__status--done'
                                    : 'ds-workflow-step__status--waiting'
                                }`}
                              >
                                {stage === 'completed' || stage === 'finalizing'
                                  ? 'Ciphertext Uploaded'
                                  : stage === 'uploading'
                                  ? 'Uploading Ciphertext...'
                                  : 'Pending'}
                              </span>
                            </div>
                            <p className="ds-workflow-step__desc">
                              Encrypted ciphertext stream transmitted to blind object storage via presigned PUT.
                            </p>
                          </div>
                        </li>

                        {/* Stage 4: Audit Record */}
                        <li
                          className={`ds-workflow-step ${
                            stage === 'completed'
                              ? 'ds-workflow-step--done'
                              : stage === 'finalizing'
                              ? 'ds-workflow-step--active'
                              : 'ds-workflow-step--pending'
                          }`}
                        >
                          <div className="ds-workflow-step__icon" aria-hidden="true">
                            <VerifiedIcon size={18} />
                          </div>
                          <div className="ds-workflow-step__body">
                            <div className="ds-workflow-step__top">
                              <span className="ds-workflow-step__name">4. Envelope Finalize &amp; Audit Anchor</span>
                              <span
                                className={`ds-workflow-step__status ${
                                  stage === 'completed'
                                    ? 'ds-workflow-step__status--done'
                                    : stage === 'finalizing'
                                    ? 'ds-workflow-step__status--done'
                                    : 'ds-workflow-step__status--waiting'
                                }`}
                              >
                                {stage === 'completed'
                                  ? 'Finalized & Anchored'
                                  : stage === 'finalizing'
                                  ? 'Finalizing...'
                                  : 'Pending'}
                              </span>
                            </div>
                            <p className="ds-workflow-step__desc">
                              DEK wrapped with owner RSA-OAEP public key; tamper-evident audit record logged.
                            </p>
                          </div>
                        </li>
                      </ol>
                    </section>

                    {/* Progress Status Banner */}
                    <div className="ds-progress-status-box" role="status">
                      <div className="ds-progress-status-header">
                        <span aria-hidden="true">•</span>
                        <span>{statusMessage}</span>
                      </div>
                      <p className="ds-progress-status-text">
                        DropSafe zero-knowledge protocol guarantees that encryption keys and raw document data
                        are strictly maintained on client endpoints.
                      </p>
                    </div>

                    {/* Success Actions */}
                    {stage === 'completed' ? (
                      <div>
                        {completedDocs.length > 0 && (
                          <div style={{ marginTop: '16px', padding: '12px', background: 'rgba(74, 222, 128, 0.05)', border: '1px solid rgba(74, 222, 128, 0.2)', borderRadius: '8px' }}>
                            <div style={{ fontSize: '12px', fontWeight: 600, color: '#4ade80', marginBottom: '6px' }}>
                              Successfully Encrypted &amp; Stored:
                            </div>
                            {completedDocs.map((doc) => (
                              <div key={doc.id} style={{ fontSize: '13px', color: '#e2e8f0', display: 'flex', justifyContent: 'space-between' }}>
                                <span>{doc.display_name}</span>
                                <span style={{ fontFamily: 'monospace', fontSize: '11px', color: '#94a3b8' }}>
                                  v{doc.current_version?.version_number} • {doc.current_version?.ciphertext_sha256_hex.substring(0, 16)}...
                                </span>
                              </div>
                            ))}
                          </div>
                        )}
                        <div style={{ marginTop: '20px', display: 'flex', gap: '12px', flexWrap: 'wrap' }}>
                        <button
                          type="button"
                          className="ds-btn ds-btn--primary"
                          onClick={() => {
                            onClearFiles?.();
                            onNavigate('files');
                          }}
                        >
                          View Files in Workspace
                        </button>
                        <button
                          type="button"
                          className="ds-btn ds-btn--secondary"
                          onClick={() => {
                            onClearFiles?.();
                            onNavigate('dashboard');
                          }}
                        >
                          Go to Dashboard
                        </button>
                        <button
                          type="button"
                          className="ds-btn ds-btn--ghost"
                          onClick={() => onNavigate('audit-log')}
                        >
                          Inspect Audit Trail
                        </button>
                      </div>
                    </div>
                  ) : (
                      /* Start Upload / Cancel Actions */
                      <div className="ds-progress-actions">
                        <button
                          type="button"
                          className="ds-btn ds-btn--primary"
                          disabled={stage !== 'idle' && stage !== 'error'}
                          onClick={handleStartUpload}
                        >
                          {stage === 'idle' || stage === 'error'
                            ? 'Encrypt & Securely Upload'
                            : 'Processing Pipeline...'}
                        </button>

                        <button
                          type="button"
                          className="ds-btn ds-btn--secondary"
                          disabled={stage !== 'idle' && stage !== 'error'}
                          onClick={() => {
                            onClearFiles?.();
                            onNavigate('upload');
                          }}
                        >
                          Back to File Selection
                        </button>
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};
