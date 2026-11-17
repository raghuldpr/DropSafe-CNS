// Data model for future backend file records

export type FileCategory =
  | 'all'
  | 'documents'
  | 'images'
  | 'videos'
  | 'audio'
  | 'other';

export interface FileRecord {
  id: string;
  name: string;
  mimeType: string;
  size: number;
  createdAt: string;
  policyId?: string;
}
