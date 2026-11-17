import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.issuer_crypto import get_issuer_public_jwk
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.user import User
from app.schemas.attribute import (
    IssuerPublicKeyResponse,
    UserAttributesWithCredentialResponse,
)
from app.schemas.user import (
    RegisterKeyRequest,
    UpdateProfileRequest,
    UserKeyDirectoryResponse,
    UserKeyResponse,
    UserProfileResponse,
)
from app.services import attribute_service, user_service

router = APIRouter(prefix="/users", tags=["Users & Public Keys"])


@router.get(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current User Profile",
    description="Retrieves caller's profile attributes, roles, and cryptographic key registration status.",
)
async def get_my_profile(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    return await user_service.get_user_profile(db, current_user)


@router.patch(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Current User Profile",
    description="Updates caller's display name. Extra parameters like roles or account status are strictly rejected.",
)
async def update_my_profile(
    payload: UpdateProfileRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserProfileResponse:
    return await user_service.update_user_profile(db, current_user, payload)


@router.get(
    "/me/keys",
    response_model=List[UserKeyResponse],
    status_code=status.HTTP_200_OK,
    summary="List Caller's Public Keys",
    description="Lists all public cryptographic keys (both active and retired) registered by the caller.",
)
async def list_my_keys(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[UserKeyResponse]:
    return await user_service.list_user_keys(db, current_user.id)


@router.post(
    "/me/keys",
    response_model=UserKeyResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register Cryptographic Public Key",
    description="Registers an RSA-OAEP-3072 encryption key or ECDSA-P256 signing key in JWK format. Prior active keys for the purpose are automatically retired.",
    dependencies=[Depends(rate_limit(max_requests=20, window_seconds=60, scope="users:keys"))],
)
async def register_key(
    payload: RegisterKeyRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserKeyResponse:
    return await user_service.register_user_key(db, current_user.id, payload)


@router.post(
    "/me/keys/{key_id}/retire",
    response_model=UserKeyResponse,
    status_code=status.HTTP_200_OK,
    summary="Retire Public Key",
    description="Retires an active public key owned by caller. Returns 404 if caller is not the owner (IDOR protection).",
)
async def retire_key(
    key_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserKeyResponse:
    return await user_service.retire_user_key(db, current_user.id, key_id)


@router.get(
    "/me/attributes",
    response_model=UserAttributesWithCredentialResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Current User Attributes & Credential",
    description="Retrieves current caller's assigned attributes and the latest active cryptographically signed credential.",
)
async def get_my_attributes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserAttributesWithCredentialResponse:
    attrs, cred = await attribute_service.get_user_attributes_and_credential(db, current_user.id)
    return UserAttributesWithCredentialResponse(
        attributes=attrs,
        latest_credential=cred,
    )


@router.get(
    "/issuer-public-key",
    response_model=IssuerPublicKeyResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Attribute Authority Issuer Public Key",
    description="Retrieves the public JWK and Key ID of the Attribute Authority for offline verification of signed attribute credentials.",
)
async def get_issuer_public_key() -> IssuerPublicKeyResponse:
    return IssuerPublicKeyResponse(
        issuer_key_id=settings.ATTRIBUTE_ISSUER_KEY_ID,
        public_jwk=get_issuer_public_jwk(),
    )


@router.get(
    "/lookup",
    response_model=UserKeyDirectoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Lookup Recipient Public Keys by Email",
    description="Recipient directory lookup by email address for encrypting files and envelopes in the Share modal.",
)
async def lookup_recipient_by_email(
    email: str = Query(..., description="Recipient email address"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserKeyDirectoryResponse:
    return await user_service.get_user_key_directory(db, email=email)


@router.get(
    "/{user_id}/public-keys",
    response_model=UserKeyDirectoryResponse,
    status_code=status.HTTP_200_OK,
    summary="Lookup Recipient Public Keys by User ID",
    description="Recipient directory lookup by User UUID returning active public encryption and signing keys.",
)
async def get_recipient_public_keys(
    user_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> UserKeyDirectoryResponse:
    return await user_service.get_user_key_directory(db, user_id=user_id)
