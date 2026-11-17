// Data models for future blockchain-backed audit event logging

export type AuditEventCategory =
  | 'upload'
  | 'access'
  | 'share'
  | 'permission'
  | 'denied'
  | 'download';

export type AuditEventFilter = 'all' | AuditEventCategory;

export type AuditEventResult = 'success' | 'denied' | 'warning';

export interface AuditEventRecord {
  id: string;
  category: AuditEventCategory;
  resourceName: string;
  actor: string;
  timestamp: string; // ISO timestamp
  result: AuditEventResult;
  details?: string;
  blockchainAnchorStatus?: 'pending' | 'anchored' | 'unavailable';
}
