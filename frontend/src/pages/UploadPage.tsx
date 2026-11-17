import React, { useState, useRef } from 'react';
import {
  UploadCloudIcon,
  DocumentIcon,
  XCloseIcon,
  ArrowLeftIcon,
  FolderIcon,
} from '../components/Icons';
import './UploadPage.css';

interface UploadPageProps {
  onNavigate: (
    route:
      | 'landing'
      | 'login'
      | 'register'
      | 'upload'
      | 'upload-progress'
      | 'dashboard'
      | 'files'
  ) => void;
  selectedFiles?: File[];
  setSelectedFiles?: React.Dispatch<React.SetStateAction<File[]>>;
}

export const UploadPage: React.FC<UploadPageProps> = ({
  onNavigate,
  selectedFiles: propFiles,
  setSelectedFiles: setPropFiles,
}) => {
  // Use shared props state if provided, otherwise local state
  const [localFiles, setLocalFiles] = useState<File[]>([]);
  const selectedFiles = propFiles !== undefined ? propFiles : localFiles;
  const setSelectedFiles = setPropFiles !== undefined ? setPropFiles : setLocalFiles;

  const [isDragging, setIsDragging] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Format bytes into human-readable string
  const formatBytes = (bytes: number): string => {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
  };

  // Helper to get uppercase file extension
  const getFileExtension = (filename: string): string => {
    const ext = filename.split('.').pop();
    return ext && ext !== filename ? ext.toUpperCase() : 'FILE';
  };

  // Deduplicate and append new files
  const handleFilesAdded = (files: FileList | File[]) => {
    const fileArray = Array.from(files);
    setSelectedFiles((prev) => {
      const existingKeys = new Set(
        prev.map((f) => `${f.name}-${f.size}-${f.lastModified}`)
      );
      const newUniqueFiles = fileArray.filter(
        (f) => !existingKeys.has(`${f.name}-${f.size}-${f.lastModified}`)
      );
      return [...prev, ...newUniqueFiles];
    });
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      handleFilesAdded(e.target.files);
    }
    // Reset file input value so selecting the same file again triggers change event
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  // Drag and drop event handlers
  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
      handleFilesAdded(e.dataTransfer.files);
    }
  };

  const handleRemoveFile = (indexToRemove: number) => {
    setSelectedFiles((prev) => prev.filter((_, idx) => idx !== indexToRemove));
  };

  const handleClearAll = () => {
    setSelectedFiles([]);
  };

  return (
    <div className="ds-upload-page">
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
          <header className="ds-upload-nav" role="banner">
            <a
              href="#/"
              className="ds-upload-nav__brand"
              onClick={(e) => {
                e.preventDefault();
                onNavigate('landing');
              }}
              aria-label="DropSafe Home"
            >
              <img
                src="/assets/dropsafe-logo.png"
                alt="DropSafe"
                className="ds-upload-nav__logo"
              />
            </a>

            <div className="ds-upload-nav__right">
              <button
                type="button"
                className="ds-upload-nav__back"
                onClick={() => onNavigate('files')}
                aria-label="Go to My Files"
              >
                <FolderIcon size={14} aria-hidden="true" />
                <span>My Files</span>
              </button>
              <button
                type="button"
                className="ds-upload-nav__back"
                onClick={() => onNavigate('landing')}
                aria-label="Return to landing page"
              >
                <ArrowLeftIcon size={14} aria-hidden="true" />
                <span>Home</span>
              </button>
            </div>
          </header>

          {/* Main Content */}
          <main className="ds-upload-main">
            <div className="ds-upload-container">
              {/* Page Introduction */}
              <div className="ds-upload-header">
                <h1 className="ds-upload-title">Secure Your Files</h1>
                <p className="ds-upload-subtitle">
                  Select the files you want to prepare for secure sharing.
                </p>
              </div>

              {/* Central Upload Drop Zone */}
              <section
                className={`ds-dropzone ${isDragging ? 'ds-dropzone--active' : ''}`}
                onDragOver={handleDragOver}
                onDragEnter={handleDragEnter}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                aria-label="File upload dropzone"
              >
                <div className="ds-dropzone__icon-wrapper" aria-hidden="true">
                  <UploadCloudIcon size={32} />
                </div>

                <h2 className="ds-dropzone__heading">
                  Drag and drop your files here
                </h2>
                <p className="ds-dropzone__supporting">
                  or choose files from your device
                </p>

                <button
                  type="button"
                  className="ds-dropzone__choose-btn"
                  onClick={() => fileInputRef.current?.click()}
                >
                  Choose Files
                </button>

                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  className="ds-visually-hidden"
                  onChange={handleInputChange}
                  aria-label="Select files to prepare for sharing"
                />

                <p className="ds-dropzone__guidance">
                  Select the files you want to prepare for sharing.
                </p>
              </section>

              {/* Selected Files Section (Appears only when files are selected) */}
              {selectedFiles.length > 0 && (
                <section
                  className="ds-selected-files-panel"
                  aria-labelledby="selected-files-heading"
                >
                  <div className="ds-selected-files-header">
                    <div className="ds-selected-files-title-wrap">
                      <h2
                        id="selected-files-heading"
                        className="ds-selected-files-title"
                      >
                        Selected Files
                      </h2>
                      <span className="ds-selected-files-badge">
                        {selectedFiles.length}
                      </span>
                    </div>

                    {selectedFiles.length > 1 && (
                      <button
                        type="button"
                        className="ds-selected-files-clear"
                        onClick={handleClearAll}
                        aria-label="Clear all selected files"
                      >
                        Clear All
                      </button>
                    )}
                  </div>

                  {/* File rows */}
                  <ul className="ds-selected-files-list" role="list">
                    {selectedFiles.map((file, idx) => (
                      <li key={`${file.name}-${file.size}-${file.lastModified}`} className="ds-file-row">
                        <div className="ds-file-row__left">
                          <span className="ds-file-row__icon" aria-hidden="true">
                            <DocumentIcon size={20} />
                          </span>
                          <div className="ds-file-row__meta">
                            <span className="ds-file-row__name" title={file.name}>
                              {file.name}
                            </span>
                            <div className="ds-file-row__details">
                              <span>{formatBytes(file.size)}</span>
                              <span className="ds-file-row__ext">
                                {getFileExtension(file.name)}
                              </span>
                            </div>
                          </div>
                        </div>

                        <button
                          type="button"
                          className="ds-file-row__remove-btn"
                          onClick={() => handleRemoveFile(idx)}
                          aria-label={`Remove ${file.name}`}
                          title={`Remove ${file.name}`}
                        >
                          <XCloseIcon size={16} aria-hidden="true" />
                        </button>
                      </li>
                    ))}
                  </ul>

                  {/* Primary Next Action */}
                  <div className="ds-upload-action-bar">
                    <button
                      type="button"
                      className="ds-btn ds-btn--continue"
                      onClick={() => onNavigate('upload-progress')}
                    >
                      Continue
                    </button>
                  </div>
                </section>
              )}
            </div>
          </main>
        </div>
      </div>
    </div>
  );
};
