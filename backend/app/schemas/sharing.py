import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.document import DocumentResponse


class PolicyUpdateRequest(BaseModel):
    """Payload to attach or update an ABAC access policy AST on a document."""
    model_config = ConfigDict(extra="forbid")

    policy_ast: Dict[str, Any] = Field(..., description="JSON ABAC policy Abstract Syntax Tree")
    policy_schema_version: str = Field("v1", max_length=30)


class PolicyResponse(BaseModel):
    """Document ABAC access policy representation."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    policy_schema_version: str
    policy_ast: Dict[str, Any]
    status: str
    created_at: datetime
    activated_at: Optional[datetime] = None


class CreateGrantRequest(BaseModel):
    """Payload to grant a recipient access to an encrypted document with their wrapped DEK envelope."""
    model_config = ConfigDict(extra="forbid")

    grantee_user_id: uuid.UUID = Field(..., description="Recipient user UUID")
    permissions: List[Literal["read", "download"]] = Field(
        default=["read", "download"],
        description="Granted document actions",
    )
    expires_at: Optional[datetime] = Field(None, description="Optional ISO timestamp expiration")
    wrapped_dek: str = Field(..., description="Base64-encoded encrypted DEK wrapped for recipient's public key")
    recipient_encryption_key_id: uuid.UUID = Field(..., description="Recipient's registered public encryption key ID")

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("Permissions list cannot be empty")
        if "download" not in v:
            raise ValueError("Grant permissions must contain at least 'download'")
        return list(set(v))


class AccessGrantResponse(BaseModel):
    """Public representation of an authorization grant on a document."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    grantor_user_id: uuid.UUID
    grantee_user_id: Optional[uuid.UUID] = None
    grantee_email: Optional[str] = None
    grantee_display_name: Optional[str] = None
    grant_type: str
    permissions: List[str]
    status: str
    expires_at: Optional[datetime] = None
    created_at: datetime
    revoked_at: Optional[datetime] = None


class SharedDocumentResponse(BaseModel):
    """Item representation in recipient's 'Shared With Me' workspace."""
    model_config = ConfigDict(from_attributes=True)

    document: DocumentResponse
    grant: AccessGrantResponse
    policy: Optional[PolicyResponse] = None


class CreateShareLinkRequest(BaseModel):
    """Payload to create a protected anonymous share link."""
    model_config = ConfigDict(extra="forbid")

    wrapped_dek: str = Field(..., description="Base64-encoded DEK wrapped by client-side link key")
    permissions: List[Literal["read", "download"]] = Field(
        default=["read", "download"],
        description="Granted link actions",
    )
    expires_at: datetime = Field(..., description="Link expiration datetime (must be in future)")
    max_uses: Optional[int] = Field(None, gt=0, description="Optional maximum number of redemptions")

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, v: List[str]) -> List[str]:
        if not v:
            raise ValueError("Permissions list cannot be empty")
        return list(set(v))


class ShareLinkResponse(BaseModel):
    """Public representation of an anonymous share link (never returning raw token)."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    access_grant_id: uuid.UUID
    created_by: uuid.UUID
    status: str
    expires_at: datetime
    max_uses: Optional[int] = None
    use_count: int = 0
    created_at: datetime
    revoked_at: Optional[datetime] = None


class ShareLinkCreatedResponse(ShareLinkResponse):
    """Returned only once upon share link creation, containing the raw bearer token."""
    token: str = Field(..., description="Raw secret bearer token, returned only once upon creation")


class RedeemShareLinkRequest(BaseModel):
    """Payload to redeem a protected share link token."""
    model_config = ConfigDict(extra="forbid")

    token: str = Field(..., min_length=16, description="Raw URL-safe share token")


class RedeemShareLinkResponse(BaseModel):
    """Redemption package containing presigned download URL, wrapped DEK, and document metadata."""
    download_url: str
    expires_in: int
    object_key: str
    wrapped_dek: str
    manifest: Dict[str, Any]
    ciphertext_size_bytes: int
    ciphertext_sha256_hex: str
    document: DocumentResponse


class DocumentAccessOverviewResponse(BaseModel):
    """Access control overview for document owner/admin."""
    policy: Optional[PolicyResponse] = None
    grants: List[AccessGrantResponse] = []
    share_links: List[ShareLinkResponse] = []


class EvaluateAccessRequest(BaseModel):
    """Candidate user ID to evaluate ABAC policy and cryptographic key eligibility."""
    model_config = ConfigDict(extra="forbid")

    candidate_user_id: uuid.UUID


class EvaluateAccessResponse(BaseModel):
    """Result of candidate access evaluation."""
    eligible: bool
    reasons: List[str] = []
