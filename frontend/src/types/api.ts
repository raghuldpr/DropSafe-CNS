// DropSafe Backend API Types and Interfaces

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

export interface UserRoleResponse {
  id: string;
  role: string;
  assigned_at: string;
}

export interface UserProfileResponse {
  id: string;
  email: string;
  display_name: string;
  account_status: string;
  created_at: string;
  updated_at: string;
  roles: string[];
  active_key_count: number;
  department?: string | null;
  security_clearance?: string | null;
}

export type PublicKeyRecord = UserKeyResponse;

export interface UserKeyResponse {
  id: string;
  key_purpose: 'encryption' | 'signing';
  algorithm: string;
  public_key_jwk: JsonWebKey;
  key_fingerprint: string;
  status: string;
  created_at: string;
  retired_at?: string | null;
}

export interface UserKeyDirectoryResponse {
  user_id: string;
  email: string;
  display_name: string;
  active_keys: UserKeyResponse[];
}

export interface DocumentVersionResponse {
  id: string;
  document_id: string;
  version_number: number;
  key_version: number;
  object_key: string;
  ciphertext_size_bytes: number;
  ciphertext_sha256_hex: string;
  manifest: Record<string, any>;
  status: string;
  signature_hex?: string | null;
  signature_algorithm?: string | null;
  created_at: string;
}

export interface DocumentResponse {
  id: string;
  owner_id: string;
  display_name: string;
  media_type?: string | null;
  status: string;
  current_version?: DocumentVersionResponse | null;
  created_at: string;
  updated_at: string;
}

export interface PresignedUrlResponse {
  url: string;
  expires_in: number;
  object_key: string;
}

export interface DownloadUrlResponse {
  download_url: string;
  expires_in: number;
  object_key: string;
  wrapped_dek: string;
  wrapping_algorithm: string;
  recipient_encryption_key_id: string;
  manifest: Record<string, any>;
  ciphertext_size_bytes: number;
  ciphertext_sha256_hex: string;
}

export interface PolicyResponse {
  id: string;
  document_id: string;
  version_number: number;
  policy_schema_version: string;
  policy_ast: Record<string, any>;
  status: string;
  created_at: string;
}

export interface AccessGrantResponse {
  id: string;
  document_id: string;
  grantor_user_id: string;
  grantee_user_id?: string | null;
  grantee_email?: string | null;
  grantee_display_name?: string | null;
  grant_type: string;
  permissions: string[];
  status: string;
  expires_at?: string | null;
  created_at: string;
  revoked_at?: string | null;
}

export type DocumentItem = DocumentResponse;

export interface DocumentAccessOverviewResponse {
  policy?: PolicyResponse | null;
  grants: AccessGrantResponse[];
  share_links?: any[];
}

export type DocumentAccessOverview = DocumentAccessOverviewResponse;

export interface SharedDocumentResponse {
  document: DocumentResponse;
  grant: AccessGrantResponse;
  policy?: PolicyResponse | null;
}

export interface WorkspaceOverviewResponse {
  owned_documents_count: number;
  shared_with_me_count: number;
  active_grants_issued_count: number;
  has_active_encryption_key: boolean;
  has_active_signing_key: boolean;
  recent_documents: DocumentResponse[];
  recent_audit_events: ApiAuditEventResponse[];
}

export interface ApiAuditEventResponse {
  id: string;
  sequence_number: number;
  event_type: string;
  outcome: string;
  actor_user_id?: string | null;
  document_id?: string | null;
  occurred_at: string;
  event_hash_hex: string;
  previous_event_hash_hex?: string | null;
  batch_id?: string | null;
  metadata_payload?: Record<string, any>;
}

export interface BlockchainAnchorResponse {
  id: string;
  chain_id: number;
  network_name: string;
  contract_address: string;
  transaction_hash?: string | null;
  block_number?: number | null;
  status: string;
  confirmed_at?: string | null;
}

export interface AuditBatchResponse {
  id: string;
  batch_number: number;
  first_sequence_number: number;
  last_sequence_number: number;
  event_count: number;
  merkle_root_hex: string;
  status: string;
  created_at: string;
  anchored_at?: string | null;
  anchors: BlockchainAnchorResponse[];
}

export interface MerkleProofResponse {
  batch_id: string;
  event_id: string;
  event_sequence_number: number;
  leaf_hash_hex: string;
  merkle_root_hex: string;
  proof: Array<{ position: 'left' | 'right'; hash_hex: string }>;
}

export interface VerifyProofResponse {
  is_valid: boolean;
  matched_batch_id?: string | null;
  anchor_status?: string | null;
}

export interface VerifyChainResponse {
  chain_valid: boolean;
  checked_events: number;
  first_broken_sequence?: number | null;
}

export interface EvaluateAccessResponse {
  eligible: boolean;
  reasons: string[];
}


// ----------------------------------------------------------------------
// Admin
// ----------------------------------------------------------------------
export interface AttributeDefinitionResponse {
  id: string;
  name: string;
  value_type: 'string' | 'boolean' | 'integer' | 'string_set' | string;
  allowed_values?: any;
  description?: string | null;
  is_active: boolean;
}

export interface AdminUserAttribute {
  id: string;
  user_id: string;
  attribute_definition_id: string;
  attribute_name: string;
  value_type: string;
  value: any;
  source: string;
  valid_until?: string | null;
}

export interface AdminUserSummary {
  id: string;
  email: string;
  display_name: string;
  status: string;
  roles: string[];
  attributes: AdminUserAttribute[];
  latest_credential?: { credential_version: number; status: string } | null;
  created_at: string;
}
