import email_validator
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

# Permit '.local' top-level domain for internal / demo environments
if hasattr(email_validator, "SPECIAL_USE_DOMAIN_NAMES") and "local" in email_validator.SPECIAL_USE_DOMAIN_NAMES:
    try:
        email_validator.SPECIAL_USE_DOMAIN_NAMES.remove("local")
    except (KeyError, TypeError):
        pass

from app.schemas.user import UserProfileResponse


class RegisterRequest(BaseModel):
    """New user account registration payload."""
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    display_name: str = Field(..., min_length=1, max_length=100)

    @field_validator("display_name")
    @classmethod
    def validate_display_name(cls, v: str) -> str:
        stripped = v.strip()
        if not stripped:
            raise ValueError("Display name cannot be empty")
        return stripped

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class LoginRequest(BaseModel):
    """User login credential payload."""
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: str

    @field_validator("email")
    @classmethod
    def normalize_email(cls, v: str) -> str:
        return v.lower().strip()


class RefreshRequest(BaseModel):
    """Optional payload fallback for refresh token when cookies are not utilized."""
    model_config = ConfigDict(extra="forbid")

    refresh_token: Optional[str] = None


class TokenResponse(BaseModel):
    """Standardized authentication token and profile response."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserProfileResponse
