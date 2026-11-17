import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, field_validator


class UserProfileResponse(BaseModel):
    """Public and self profile representation of a DropSafe user."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    status: str
    roles: List[str]
    has_active_encryption_key: bool = False
    has_active_signing_key: bool = False
    created_at: datetime


class UpdateProfileRequest(BaseModel):
    """User profile modification payload. Strictly forbids role or status tampering."""
    model_config = ConfigDict(extra="forbid")

    display_name: str = Field(..., min_length=1, max_length=100)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Display name cannot be blank")
        return stripped


class RegisterKeyRequest(BaseModel):
    """Public key registration payload for encryption or signing keys."""
    model_config = ConfigDict(extra="forbid")

    key_purpose: Literal["encryption", "signing"]
    algorithm: Literal["RSA-OAEP-3072", "ECDSA-P256"]
    public_key_jwk: Dict[str, Any]


class UserKeyResponse(BaseModel):
    """Cryptographic public key metadata response."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    key_purpose: str
    algorithm: str
    public_key_jwk: Dict[str, Any]
    public_key_fingerprint_hex: str
    key_version: int
    status: str
    created_at: datetime
    retired_at: Optional[datetime] = None


class UserKeyDirectoryResponse(BaseModel):
    """Recipient lookup directory entry with active cryptographic keys and credential status."""
    model_config = ConfigDict(from_attributes=True)

    user_id: uuid.UUID
    email: str
    display_name: str
    active_keys: List[UserKeyResponse]
    latest_credential: Optional[Dict[str, Any]] = None
