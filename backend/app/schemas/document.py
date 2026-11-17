import uuid
from datetime import datetime
from typing import Any, Dict, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreateDocumentRequest(BaseModel):
    """Payload to create a new encrypted document root."""
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(..., min_length=1, max_length=255)
    media_type: Optional[str] = Field(None, max_length=150)


class CreateVersionRequest(BaseModel):
    """Payload to initiate an upload intent for a new document version."""
    model_config = ConfigDict(extra="forbid")

    key_version: int = Field(..., gt=0, description="Cryptographic key version")
    ciphertext_size_bytes: int = Field(..., ge=0, description="Total byte size of encrypted ciphertext")
    ciphertext_sha256_hex: str = Field(..., min_length=64, max_length=64, description="SHA-256 hash of ciphertext")
    manifest: Dict[str, Any] = Field(..., description="Encrypted chunk nonces and metadata")
    commitment_version: str = Field("v1", max_length=30)

    @field_validator("ciphertext_sha256_hex")
    @classmethod
    def validate_hex(cls, v: str) -> str:
        clean = v.strip().lower()
        if len(clean) != 64:
            raise ValueError("ciphertext_sha256_hex must be exactly 64 hexadecimal characters")
        try:
            bytes.fromhex(clean)
        except ValueError:
            raise ValueError("ciphertext_sha256_hex must be valid hex")
        return clean


class DocumentUpdateRequest(BaseModel):
    """Payload to update document metadata."""
    model_config = ConfigDict(extra="forbid")

    display_name: Optional[str] = Field(None, min_length=1, max_length=255)
    media_type: Optional[str] = Field(None, max_length=150)


class RecipientEnvelopeItem(BaseModel):
    """Wrapped DEK envelope for an authorized recipient during version finalization."""
    model_config = ConfigDict(extra="forbid")

    recipient_user_id: uuid.UUID
    recipient_encryption_key_id: uuid.UUID
    wrapped_dek: str = Field(..., description="Base64-encoded DEK wrapped for recipient")
    wrapping_algorithm: str = Field("RSA-OAEP-3072", max_length=40)


class FinalizeVersionRequest(BaseModel):
    """Payload to verify storage and finalize a version with the owner's key envelope and optional signature."""
    model_config = ConfigDict(extra="forbid")

    wrapped_dek: str = Field(..., description="Base64-encoded DEK wrapped for document owner")
    recipient_encryption_key_id: uuid.UUID = Field(..., description="Owner's active encryption key ID")
    signature_hex: Optional[str] = Field(None, description="Optional ECDSA-P256 signature hex over ciphertext hash")
    signature_algorithm: Optional[Literal["ECDSA-P256"]] = Field(None, description="Cryptographic signature algorithm")
    signing_key_id: Optional[uuid.UUID] = Field(None, description="Owner's signing key ID")
    recipient_envelopes: Optional[list[RecipientEnvelopeItem]] = Field(
        None, description="Optional list of re-wrapped DEKs for existing eligible recipients"
    )


class DocumentVersionResponse(BaseModel):
    """Public representation of an immutable document version."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    document_id: uuid.UUID
    version_number: int
    key_version: int
    object_key: str
    ciphertext_size_bytes: int
    ciphertext_sha256_hex: str
    manifest: Dict[str, Any]
    status: str
    signature_hex: Optional[str] = None
    signature_algorithm: Optional[str] = None
    created_at: datetime


class DocumentResponse(BaseModel):
    """Public document representation including owner and current version metadata."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    owner_id: uuid.UUID
    display_name: str
    media_type: Optional[str] = None
    status: str
    current_version: Optional[DocumentVersionResponse] = None
    created_at: datetime
    updated_at: datetime


class PresignedUrlResponse(BaseModel):
    """Presigned storage URL response for client direct upload."""
    url: str
    expires_in: int
    object_key: str


class DownloadUrlResponse(BaseModel):
    """Authorized download package including presigned GET URL and caller's wrapped DEK envelope."""
    download_url: str
    expires_in: int
    object_key: str
    wrapped_dek: str
    wrapping_algorithm: str
    recipient_encryption_key_id: uuid.UUID
    manifest: Dict[str, Any]
    ciphertext_size_bytes: int
    ciphertext_sha256_hex: str
