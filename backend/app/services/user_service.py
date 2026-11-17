import uuid
from datetime import datetime, timezone
from typing import List, Optional
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.service import record_audit_event
from app.core.exceptions import NotFoundException
from app.core.security import validate_and_fingerprint_public_jwk
from app.models.attribute import AttributeCredentialSignature
from app.models.user import User, UserKey
from app.schemas.user import (
    RegisterKeyRequest,
    UpdateProfileRequest,
    UserKeyDirectoryResponse,
    UserKeyResponse,
    UserProfileResponse,
)
from app.services.auth_service import _build_user_profile, _check_user_active_keys


def _format_user_key_response(key: UserKey) -> UserKeyResponse:
    """Format UserKey database model into UserKeyResponse."""
    return UserKeyResponse(
        id=key.id,
        user_id=key.user_id,
        key_purpose=key.key_purpose,
        algorithm=key.algorithm,
        public_key_jwk=key.public_key_jwk,
        public_key_fingerprint_hex=key.public_key_fingerprint.hex(),
        key_version=key.key_version,
        status=key.status,
        created_at=key.created_at,
        retired_at=key.retired_at,
    )


async def get_user_profile(
    db: AsyncSession,
    user: User,
) -> UserProfileResponse:
    """Return user profile with cryptographic key registration flags."""
    has_enc, has_sig = await _check_user_active_keys(db, user.id)
    return _build_user_profile(user, has_enc, has_sig)


async def update_user_profile(
    db: AsyncSession,
    user: User,
    payload: UpdateProfileRequest,
) -> UserProfileResponse:
    """Update profile attributes. Strictly prevents role or status tampering."""
    user.display_name = payload.display_name
    await db.flush()

    await record_audit_event(
        db=db,
        event_type="user.profile.updated",
        outcome="success",
        actor_user_id=user.id,
        metadata={"display_name": user.display_name},
    )

    has_enc, has_sig = await _check_user_active_keys(db, user.id)
    return _build_user_profile(user, has_enc, has_sig)


async def register_user_key(
    db: AsyncSession,
    user_id: uuid.UUID,
    payload: RegisterKeyRequest,
) -> UserKeyResponse:
    """Register public cryptographic key, auto-increment version, and retire previous active key for purpose."""
    # 1. Validate JWK structure, reject private fields, and compute 32-byte fingerprint
    fingerprint = validate_and_fingerprint_public_jwk(
        key_purpose=payload.key_purpose,
        algorithm=payload.algorithm,
        jwk_dict=payload.public_key_jwk,
    )

    # 2. Determine next key version for this user and purpose
    ver_stmt = select(func.coalesce(func.max(UserKey.key_version), 0)).where(
        UserKey.user_id == user_id,
        UserKey.key_purpose == payload.key_purpose,
    )
    current_max_ver = (await db.execute(ver_stmt)).scalar_one()
    next_version = current_max_ver + 1

    # 3. Retire previous active key for this purpose
    now = datetime.now(timezone.utc)
    retire_stmt = (
        update(UserKey)
        .where(
            UserKey.user_id == user_id,
            UserKey.key_purpose == payload.key_purpose,
            UserKey.status == "active",
        )
        .values(status="retired", retired_at=now)
    )
    await db.execute(retire_stmt)

    # 4. Insert new active key
    new_key = UserKey(
        user_id=user_id,
        key_purpose=payload.key_purpose,
        algorithm=payload.algorithm,
        public_key_jwk=payload.public_key_jwk,
        public_key_fingerprint=fingerprint,
        key_version=next_version,
        status="active",
    )
    db.add(new_key)
    await db.flush()

    # 5. Re-issue signed credential binding reflecting new active keys
    from app.services.attribute_service import issue_user_credential_signature
    await issue_user_credential_signature(db, user_id)

    # 6. Record audit log
    await record_audit_event(
        db=db,
        event_type="user.key.registered",
        outcome="success",
        actor_user_id=user_id,
        metadata={
            "key_id": str(new_key.id),
            "key_purpose": new_key.key_purpose,
            "algorithm": new_key.algorithm,
            "key_version": new_key.key_version,
            "fingerprint": fingerprint.hex(),
        },
    )

    return _format_user_key_response(new_key)


async def retire_user_key(
    db: AsyncSession,
    user_id: uuid.UUID,
    key_id: uuid.UUID,
) -> UserKeyResponse:
    """Manually retire an active public key owned by caller. Enforces IDOR protection."""
    stmt = select(UserKey).where(UserKey.id == key_id, UserKey.user_id == user_id)
    key = (await db.execute(stmt)).scalar_one_or_none()

    if not key:
        raise NotFoundException(
            message="Cryptographic key not found or access denied",
            code="KEY_NOT_FOUND",
        )

    if key.status == "active":
        key.status = "retired"
        key.retired_at = datetime.now(timezone.utc)
        await db.flush()

        from app.services.attribute_service import issue_user_credential_signature
        await issue_user_credential_signature(db, user_id)

        await record_audit_event(
            db=db,
            event_type="user.key.retired",
            outcome="success",
            actor_user_id=user_id,
            metadata={
                "key_id": str(key.id),
                "key_purpose": key.key_purpose,
                "key_version": key.key_version,
            },
        )

    return _format_user_key_response(key)


async def list_user_keys(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> List[UserKeyResponse]:
    """List all keys (active and retired) owned by the specified user."""
    stmt = (
        select(UserKey)
        .where(UserKey.user_id == user_id)
        .order_by(UserKey.key_purpose.asc(), UserKey.key_version.desc())
    )
    res = await db.execute(stmt)
    keys = res.scalars().all()
    return [_format_user_key_response(k) for k in keys]


async def get_user_key_directory(
    db: AsyncSession,
    user_id: Optional[uuid.UUID] = None,
    email: Optional[str] = None,
) -> UserKeyDirectoryResponse:
    """Public recipient directory lookup returning active cryptographic keys and credentials."""
    if not user_id and not email:
        raise NotFoundException("Must provide user_id or email for directory lookup")

    user_stmt = select(User)
    if user_id:
        user_stmt = user_stmt.where(User.id == user_id)
    elif email:
        user_stmt = user_stmt.where(User.email == email.lower().strip())

    user = (await db.execute(user_stmt)).scalar_one_or_none()
    if not user or user.status != "active":
        raise NotFoundException(
            message="Recipient user not found or inactive",
            code="RECIPIENT_NOT_FOUND",
        )

    # Fetch active keys
    keys_stmt = (
        select(UserKey)
        .where(UserKey.user_id == user.id, UserKey.status == "active")
        .order_by(UserKey.key_purpose.asc())
    )
    keys = (await db.execute(keys_stmt)).scalars().all()
    active_keys = [_format_user_key_response(k) for k in keys]

    # Check for latest active credential signature if any
    cred_stmt = (
        select(AttributeCredentialSignature)
        .where(
            AttributeCredentialSignature.user_id == user.id,
            AttributeCredentialSignature.status == "active",
        )
        .order_by(AttributeCredentialSignature.credential_version.desc())
        .limit(1)
    )
    cred = (await db.execute(cred_stmt)).scalar_one_or_none()
    latest_credential_summary = None
    if cred:
        latest_credential_summary = {
            "credential_version": cred.credential_version,
            "issuer_key_id": cred.issuer_key_id,
            "issued_at": cred.issued_at.isoformat(),
            "expires_at": cred.expires_at.isoformat() if cred.expires_at else None,
            "payload_summary": cred.payload,
        }

    return UserKeyDirectoryResponse(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        active_keys=active_keys,
        latest_credential=latest_credential_summary,
    )
