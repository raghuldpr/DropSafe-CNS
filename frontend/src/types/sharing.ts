// Data model for future backend shared file records

export type ShareAccessLevel = 'all' | 'viewer' | 'editor' | 'download';

export interface SharedFileRecord {
  id: string;
  fileName: string;
  fileSize?: number;
  mimeType?: string;
  direction: 'incoming' | 'outgoing';
  sharedBy?: string; // e.g. email or name of the user who shared the file
  recipient?: string; // e.g. email of the user receiving access
  accessLevel: 'viewer' | 'editor' | 'download';
  sharedAt: string; // ISO date string
  expiresAt?: string | null; // ISO date string or null
}
