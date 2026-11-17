import base64
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field, field_validator


class CreateAttributeDefinitionRequest(BaseModel):
    """Admin payload to create a new ABAC attribute definition."""
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=2, max_length=64)
    value_type: Literal["string", "boolean", "integer", "string_set"]
    allowed_values: Optional[Union[List[Any], Dict[str, Any]]] = None
    description: Optional[str] = Field(None, max_length=500)

    @field_validator("name")
    @classmethod
    def validate_name_snake_case(cls, v: str) -> str:
        clean = v.strip().lower()
        if not re.match(r"^[a-z][a-z0-9_]{1,63}$", clean):
            raise ValueError(
                "Attribute name must be lowercase snake_case (e.g., 'clearance_level', 'department', 'projects')"
            )
        return clean


class UpdateAttributeDefinitionRequest(BaseModel):
    """Admin payload to update an existing attribute definition."""
    model_config = ConfigDict(extra="forbid")

    allowed_values: Optional[Union[List[Any], Dict[str, Any]]] = None
    description: Optional[str] = Field(None, max_length=500)
    is_active: Optional[bool] = None


class AttributeDefinitionResponse(BaseModel):
    """Attribute definition catalog item representation."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    value_type: str
    allowed_values: Optional[Any] = None
    description: Optional[str] = None
    is_active: bool
    created_by: uuid.UUID
    created_at: datetime
    updated_at: datetime


class AssignUserAttributeRequest(BaseModel):
    """Admin payload to assign or update an attribute on a user."""
    model_config = ConfigDict(extra="forbid")

    value: Any
    valid_until: Optional[datetime] = None


class UserAttributeResponse(BaseModel):
    """User attribute assignment response."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    attribute_definition_id: uuid.UUID
    attribute_name: str
    value_type: str
    value: Any
    assigned_by: uuid.UUID
    source: str
    valid_from: datetime
    valid_until: Optional[datetime] = None
    created_at: datetime


class CredentialSignatureResponse(BaseModel):
    """Signed attribute credential response with cryptographic signature."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: uuid.UUID
    credential_version: int
    payload: Dict[str, Any]
    payload_hash_hex: str
    signature_b64: str
    issuer_key_id: str
    status: str
    issued_at: datetime
    expires_at: Optional[datetime] = None


class AdminUserSummaryResponse(BaseModel):
    """Full administrative summary of a user, their roles, attributes, and credential."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: str
    display_name: str
    status: str
    roles: List[str]
    attributes: List[UserAttributeResponse]
    latest_credential: Optional[CredentialSignatureResponse] = None
    created_at: datetime


class UpdateUserRoleRequest(BaseModel):
    """Admin payload to modify user role assignments."""
    model_config = ConfigDict(extra="forbid")

    roles: List[Literal["user", "admin", "auditor"]]

    @field_validator("roles")
    @classmethod
    def validate_roles(cls, v: List[str]) -> List[str]:
        if "user" not in v:
            raise ValueError("All accounts must retain at least the base 'user' role")
        return list(set(v))


class UpdateUserRolesResponse(BaseModel):
    """Response after updating user roles."""
    user_id: uuid.UUID
    roles: List[str]


class UserAttributesWithCredentialResponse(BaseModel):
    """User attributes and latest cryptographically signed credential response."""
    attributes: List[UserAttributeResponse]
    latest_credential: Optional[CredentialSignatureResponse] = None


class IssuerPublicKeyResponse(BaseModel):
    """Attribute Authority public key metadata for client verification."""
    issuer_key_id: str
    public_jwk: Dict[str, Any]


class UpdateUserStatusRequest(BaseModel):
    """Admin payload to update a user's account status."""
    model_config = ConfigDict(extra="forbid")

    status: Literal["active", "disabled"]
