// DropSafe Centralized API Client Service
import type {
  TokenResponse,
  UserProfileResponse,
  UserKeyResponse,
  UserKeyDirectoryResponse,
  DocumentResponse,
  DocumentVersionResponse,
  PresignedUrlResponse,
  DownloadUrlResponse,
  PolicyResponse,
  AccessGrantResponse,
  SharedDocumentResponse,
  WorkspaceOverviewResponse,
  ApiAuditEventResponse,
  AuditBatchResponse,
  MerkleProofResponse,
  VerifyProofResponse,
  VerifyChainResponse,
  EvaluateAccessResponse,
  DocumentAccessOverviewResponse,
  AttributeDefinitionResponse,
  AdminUserSummary,
} from '../types/api';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api/v1';

class ApiError extends Error {
  status: number;
  code?: string;
  details?: any;

  constructor(message: string, status: number, code?: string, details?: any) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

// Token storage in memory + localStorage
let accessToken: string | null = localStorage.getItem('dropsafe_access_token');
let isRefreshing = false;
let refreshSubscribers: ((token: string) => void)[] = [];

export function setAccessToken(token: string | null) {
  accessToken = token;
  if (token) {
    localStorage.setItem('dropsafe_access_token', token);
  } else {
    localStorage.removeItem('dropsafe_access_token');
  }
}

export function getAccessToken(): string | null {
  return accessToken;
}

function onRefreshed(token: string) {
  refreshSubscribers.forEach((cb) => cb(token));
  refreshSubscribers = [];
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
  retry = true
): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers = new Headers(options.headers || {});

  if (!headers.has('Content-Type') && !(options.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json');
  }

  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  const response = await fetch(url, {
    ...options,
    headers,
    credentials: 'include',
  });

  if (response.status === 401 && retry && !endpoint.includes('/auth/')) {
    if (!isRefreshing) {
      isRefreshing = true;
      try {
        const refreshRes = await fetch(`${API_BASE}/auth/refresh`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          credentials: 'include',
        });

        if (refreshRes.ok) {
          const tokenData: TokenResponse = await refreshRes.json();
          setAccessToken(tokenData.access_token);
          isRefreshing = false;
          onRefreshed(tokenData.access_token);
          return request<T>(endpoint, options, false);
        } else {
          setAccessToken(null);
          isRefreshing = false;
          window.location.hash = '#/login';
          throw new ApiError('Session expired. Please log in again.', 401, 'SESSION_EXPIRED');
        }
      } catch (err) {
        setAccessToken(null);
        isRefreshing = false;
        window.location.hash = '#/login';
        throw err;
      }
    } else {
      return new Promise<T>((resolve, reject) => {
        refreshSubscribers.push((newToken: string) => {
          headers.set('Authorization', `Bearer ${newToken}`);
          fetch(url, { ...options, headers, credentials: 'include' })
            .then(async (res) => {
              if (!res.ok) {
                const errData = await res.json().catch(() => ({}));
                reject(new ApiError(errData.error?.message || res.statusText, res.status));
              } else {
                resolve((await res.json()) as T);
              }
            })
            .catch(reject);
        });
      });
    }
  }

  if (!response.ok) {
    let errBody: any = {};
    try {
      errBody = await response.json();
    } catch {
      // not JSON
    }
    const message =
      errBody.error?.message || errBody.message || errBody.detail || response.statusText || 'An error occurred';
    const code = errBody.error?.code || errBody.code;
    throw new ApiError(message, response.status, code, errBody);
  }

  if (response.status === 204) {
    return {} as T;
  }

  return response.json();
}

// ----------------------------------------------------------------------
// Auth Service
// ----------------------------------------------------------------------
export const authApi = {
  login: async (email: string, password: string): Promise<TokenResponse> => {
    const res = await request<TokenResponse>('/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    setAccessToken(res.access_token);
    return res;
  },

  register: async (email: string, password: string, displayName?: string): Promise<TokenResponse> => {
    const res = await request<TokenResponse>('/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, display_name: displayName }),
    });
    setAccessToken(res.access_token);
    return res;
  },

  refresh: async (): Promise<TokenResponse> => {
    const res = await request<TokenResponse>('/auth/refresh', {
      method: 'POST',
    });
    setAccessToken(res.access_token);
    return res;
  },

  logout: async (): Promise<{ message: string }> => {
    try {
      return await request<{ message: string }>('/auth/logout', { method: 'POST' });
    } finally {
      setAccessToken(null);
    }
  },
};

// ----------------------------------------------------------------------
// Users & Cryptographic Keys
// ----------------------------------------------------------------------
export const userApi = {
  getProfile: (): Promise<UserProfileResponse> => {
    return request<UserProfileResponse>('/users/me');
  },

  updateProfile: (displayName: string): Promise<UserProfileResponse> => {
    return request<UserProfileResponse>('/users/me', {
      method: 'PATCH',
      body: JSON.stringify({ display_name: displayName }),
    });
  },

  getMyKeys: (): Promise<UserKeyResponse[]> => {
    return request<UserKeyResponse[]>('/users/me/keys');
  },

  registerKey: (
    keyPurpose: 'encryption' | 'signing',
    algorithm: string,
    publicKeyJwk: JsonWebKey
  ): Promise<UserKeyResponse> => {
    return request<UserKeyResponse>('/users/me/keys', {
      method: 'POST',
      body: JSON.stringify({
        key_purpose: keyPurpose,
        algorithm,
        public_key_jwk: publicKeyJwk,
      }),
    });
  },

  lookupByEmail: (email: string): Promise<UserKeyDirectoryResponse> => {
    return request<UserKeyDirectoryResponse>(`/users/lookup?email=${encodeURIComponent(email)}`);
  },

  lookupById: (userId: string): Promise<UserKeyDirectoryResponse> => {
    return request<UserKeyDirectoryResponse>(`/users/${userId}/public-keys`);
  },

  getIssuerPublicKey: (): Promise<{ issuer_key_id: string; public_jwk: JsonWebKey }> => {
    return request<{ issuer_key_id: string; public_jwk: JsonWebKey }>('/users/issuer-public-key');
  },
};

// ----------------------------------------------------------------------
// Workspace Overview
// ----------------------------------------------------------------------
export const workspaceApi = {
  getOverview: (): Promise<WorkspaceOverviewResponse> => {
    return request<WorkspaceOverviewResponse>('/workspace/overview');
  },
};

// ----------------------------------------------------------------------
// Documents & Storage
// ----------------------------------------------------------------------
export const documentApi = {
  list: (filter: 'all' | 'owned' | 'shared' = 'all', page = 1, pageSize = 50): Promise<DocumentResponse[]> => {
    return request<DocumentResponse[]>(`/documents?filter=${filter}&page=${page}&page_size=${pageSize}`);
  },

  get: (documentId: string): Promise<DocumentResponse> => {
    return request<DocumentResponse>(`/documents/${documentId}`);
  },

  create: (displayName: string, mediaType?: string): Promise<DocumentResponse> => {
    return request<DocumentResponse>('/documents', {
      method: 'POST',
      body: JSON.stringify({ display_name: displayName, media_type: mediaType }),
    });
  },

  createVersionIntent: (
    documentId: string,
    keyVersion: number,
    ciphertextSizeBytes: number,
    ciphertextSha256Hex: string,
    manifest: Record<string, any>
  ): Promise<DocumentVersionResponse> => {
    return request<DocumentVersionResponse>(`/documents/${documentId}/versions`, {
      method: 'POST',
      body: JSON.stringify({
        key_version: keyVersion,
        ciphertext_size_bytes: ciphertextSizeBytes,
        ciphertext_sha256_hex: ciphertextSha256Hex,
        manifest,
      }),
    });
  },

  getUploadUrl: (documentId: string, versionId: string): Promise<PresignedUrlResponse> => {
    return request<PresignedUrlResponse>(`/documents/${documentId}/versions/${versionId}/upload-url`, {
      method: 'POST',
    });
  },

  uploadCiphertextToStorage: async (
    presignedUrl: string,
    ciphertext: ArrayBuffer | Blob
  ): Promise<void> => {
    const res = await fetch(presignedUrl, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/octet-stream',
      },
      body: ciphertext,
    });
    if (!res.ok) {
      throw new ApiError(`Failed to upload to object storage: ${res.statusText}`, res.status);
    }
  },

  finalizeVersion: (
    documentId: string,
    versionId: string,
    wrappedDek: string,
    recipientEncryptionKeyId: string,
    signatureHex?: string,
    signingKeyId?: string,
    recipientEnvelopes?: Array<{
      recipient_user_id: string;
      recipient_encryption_key_id: string;
      wrapped_dek: string;
      wrapping_algorithm: string;
    }>
  ): Promise<DocumentResponse> => {
    return request<DocumentResponse>(`/documents/${documentId}/versions/${versionId}/finalize`, {
      method: 'POST',
      body: JSON.stringify({
        wrapped_dek: wrappedDek,
        recipient_encryption_key_id: recipientEncryptionKeyId,
        signature_hex: signatureHex,
        signature_algorithm: signatureHex ? 'ECDSA-P256' : undefined,
        signing_key_id: signingKeyId,
        recipient_envelopes: recipientEnvelopes,
      }),
    });
  },

  getDownloadUrl: async (documentId: string, versionId?: string): Promise<DownloadUrlResponse> => {
    let verId = versionId;
    if (!verId) {
      const doc = await documentApi.get(documentId);
      if (!doc.current_version?.id) {
        throw new ApiError('Document has no active versions', 404);
      }
      verId = doc.current_version.id;
    }
    return request<DownloadUrlResponse>(`/documents/${documentId}/versions/${verId}/download-url`);
  },

  getPolicy: (documentId: string): Promise<PolicyResponse | null> => {
    return sharingApi.getPolicy(documentId);
  },

  setPolicy: (
    documentId: string,
    payload: { policy_ast: Record<string, any>; description?: string } | Record<string, any>
  ): Promise<PolicyResponse> => {
    const ast = 'policy_ast' in payload ? payload.policy_ast : payload;
    return sharingApi.setPolicy(documentId, ast);
  },

  fetchCiphertextFromStorage: async (downloadUrl: string): Promise<ArrayBuffer> => {
    const res = await fetch(downloadUrl);
    if (!res.ok) {
      throw new ApiError(`Failed to download ciphertext from storage: ${res.statusText}`, res.status);
    }
    return res.arrayBuffer();
  },

  delete: (documentId: string): Promise<void> => {
    return request<void>(`/documents/${documentId}`, { method: 'DELETE' });
  },

  update: (documentId: string, displayName: string): Promise<DocumentResponse> => {
    return request<DocumentResponse>(`/documents/${documentId}`, {
      method: 'PATCH',
      body: JSON.stringify({ display_name: displayName }),
    });
  },
};

// ----------------------------------------------------------------------
// Sharing & ABAC
// ----------------------------------------------------------------------
export const sharingApi = {
  getPolicy: (documentId: string): Promise<PolicyResponse | null> => {
    return request<PolicyResponse | null>(`/documents/${documentId}/policy`);
  },

  setPolicy: (documentId: string, policyAst: Record<string, any>): Promise<PolicyResponse> => {
    return request<PolicyResponse>(`/documents/${documentId}/policy`, {
      method: 'PUT',
      body: JSON.stringify({ policy_ast: policyAst }),
    });
  },

  getDocumentAccess: (documentId: string): Promise<DocumentAccessOverviewResponse> => {
    return request<DocumentAccessOverviewResponse>(`/documents/${documentId}/access`);
  },

  listGrants: (documentId: string): Promise<AccessGrantResponse[]> => {
    return request<AccessGrantResponse[]>(`/documents/${documentId}/grants`);
  },

  createGrant: (
    documentId: string,
    granteeUserId: string,
    wrappedDek: string,
    recipientEncryptionKeyId: string,
    permissions: string[] = ['read', 'download'],
    expiresAt?: string
  ): Promise<AccessGrantResponse> => {
    return request<AccessGrantResponse>(`/documents/${documentId}/grants`, {
      method: 'POST',
      body: JSON.stringify({
        grantee_user_id: granteeUserId,
        permissions,
        wrapped_dek: wrappedDek,
        recipient_encryption_key_id: recipientEncryptionKeyId,
        expires_at: expiresAt,
      }),
    });
  },

  revokeGrant: (documentId: string, grantId: string): Promise<void> => {
    return request<void>(`/documents/${documentId}/grants/${grantId}`, { method: 'DELETE' });
  },

  listSharedWithMe: (): Promise<SharedDocumentResponse[]> => {
    return request<SharedDocumentResponse[]>('/shared-with-me');
  },

  evaluateAccess: (documentId: string, candidateUserId: string): Promise<EvaluateAccessResponse> => {
    return request<EvaluateAccessResponse>(`/documents/${documentId}/access/evaluate`, {
      method: 'POST',
      body: JSON.stringify({ candidate_user_id: candidateUserId }),
    });
  },
};

// ----------------------------------------------------------------------
// Audit & Blockchain Verification
// ----------------------------------------------------------------------
export const auditApi = {
  listEvents: (page = 1, pageSize = 50, documentId?: string): Promise<ApiAuditEventResponse[]> => {
    const docQuery = documentId ? `&document_id=${documentId}` : '';
    return request<ApiAuditEventResponse[]>(`/audit-events?page=${page}&page_size=${pageSize}${docQuery}`);
  },

  getEvent: (eventId: string): Promise<ApiAuditEventResponse> => {
    return request<ApiAuditEventResponse>(`/audit-events/${eventId}`);
  },

  listBatches: (page = 1, pageSize = 50): Promise<AuditBatchResponse[]> => {
    return request<AuditBatchResponse[]>(`/audit-batches?page=${page}&page_size=${pageSize}`);
  },

  createBatch: (): Promise<AuditBatchResponse | null> => {
    return request<AuditBatchResponse | null>('/audit-batches', { method: 'POST' });
  },

  getBatch: (batchId: string): Promise<AuditBatchResponse> => {
    return request<AuditBatchResponse>(`/audit-batches/${batchId}`);
  },

  getEventProof: (batchId: string, eventId: string): Promise<MerkleProofResponse> => {
    return request<MerkleProofResponse>(`/audit-batches/${batchId}/proofs/${eventId}`);
  },

  verifyProof: (leafHashHex: string, merkleRootHex: string, proof: any): Promise<VerifyProofResponse> => {
    return request<VerifyProofResponse>('/audit/verify', {
      method: 'POST',
      body: JSON.stringify({
        leaf_hash_hex: leafHashHex,
        merkle_root_hex: merkleRootHex,
        proof,
      }),
    });
  },

  verifyChain: (): Promise<VerifyChainResponse> => {
    return request<VerifyChainResponse>('/audit/verify-chain');
  },
};

// ----------------------------------------------------------------------
// Admin (requires "admin" role; enforced by the backend)
// ----------------------------------------------------------------------
export const adminApi = {
  listUsers: (q?: string): Promise<AdminUserSummary[]> =>
    request<AdminUserSummary[]>(`/admin/users${q ? `?q=${encodeURIComponent(q)}` : ''}`),

  listDefinitions: (): Promise<AttributeDefinitionResponse[]> =>
    request<AttributeDefinitionResponse[]>('/admin/attribute-definitions'),

  createDefinition: (body: {
    name: string;
    value_type: string;
    description?: string;
  }): Promise<AttributeDefinitionResponse> =>
    request<AttributeDefinitionResponse>('/admin/attribute-definitions', {
      method: 'POST',
      body: JSON.stringify(body),
    }),

  setAttribute: (userId: string, attributeId: string, value: unknown) =>
    request<unknown>(`/admin/users/${userId}/attributes/${attributeId}`, {
      method: 'PUT',
      body: JSON.stringify({ value }),
    }),

  removeAttribute: (userId: string, attributeId: string) =>
    request<unknown>(`/admin/users/${userId}/attributes/${attributeId}`, { method: 'DELETE' }),

  setRoles: (userId: string, roles: string[]) =>
    request<{ user_id: string; roles: string[] }>(`/admin/users/${userId}/roles`, {
      method: 'PUT',
      body: JSON.stringify({ roles }),
    }),

  setStatus: (userId: string, status: 'active' | 'disabled') =>
    request<AdminUserSummary>(`/admin/users/${userId}/status`, {
      method: 'PATCH',
      body: JSON.stringify({ status }),
    }),
};
