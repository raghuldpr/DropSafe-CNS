import uuid
from typing import Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.audit.service import record_audit_event
from app.core.config import settings
from app.core.exceptions import (
    AuthenticationException,
    ConflictException,
    ForbiddenException,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User, UserKey, UserRole
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse
from app.schemas.user import UserProfileResponse


async def _check_user_active_keys(db: AsyncSession, user_id: uuid.UUID) -> Tuple[bool, bool]:
    """Check if the user has active encryption and signing keys registered."""
    stmt = (
        select(UserKey.key_purpose)
        .where(UserKey.user_id == user_id, UserKey.status == "active")
    )
    res = await db.execute(stmt)
    purposes = set(res.scalars().all())
    return ("encryption" in purposes, "signing" in purposes)


def _build_user_profile(
    user: User,
    has_encryption_key: bool = False,
    has_signing_key: bool = False,
) -> UserProfileResponse:
    """Construct UserProfileResponse from User model."""
    roles = [r.role for r in user.roles] if user.roles else []
    return UserProfileResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        status=user.status,
        roles=roles,
        has_active_encryption_key=has_encryption_key,
        has_active_signing_key=has_signing_key,
        created_at=user.created_at,
    )


async def register_user(
    db: AsyncSession,
    payload: RegisterRequest,
) -> Tuple[User, TokenResponse]:
    """Register a new user account with default 'user' role and initial audit logging."""
    # 1. Anti-collision check for email
    existing_stmt = select(User).where(User.email == payload.email)
    existing_user = (await db.execute(existing_stmt)).scalar_one_or_none()

    if existing_user:
        await record_audit_event(
            db=db,
            event_type="auth.register",
            outcome="denied",
            metadata={"email": payload.email, "reason": "email_already_exists"},
        )
        raise ConflictException(
            message="An account with this email address already exists",
            code="EMAIL_ALREADY_EXISTS",
        )

    # 2. Hash password with Argon2id
    pwd_hash = hash_password(payload.password)

    # 3. Create User record
    user = User(
        email=payload.email,
        display_name=payload.display_name,
        password_hash=pwd_hash,
        status="active",
    )
    db.add(user)
    await db.flush()

    # 4. Strictly assign default 'user' role
    role = UserRole(
        user_id=user.id,
        role="user",
        assigned_by=None,
    )
    db.add(role)
    await db.flush()

    # 5. Record append-only audit event
    await record_audit_event(
        db=db,
        event_type="auth.register",
        outcome="success",
        actor_user_id=user.id,
        metadata={"email": user.email, "assigned_role": "user"},
    )

    # 6. Generate initial access & refresh tokens
    roles_list = ["user"]
    access_token = create_access_token(user.id, roles_list)
    refresh_token = create_refresh_token(user.id)

    # Reload user with roles populated
    stmt = select(User).options(selectinload(User.roles)).where(User.id == user.id)
    refreshed_user = (await db.execute(stmt)).scalar_one()

    token_response = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_build_user_profile(refreshed_user, False, False),
    )
    return refreshed_user, token_response


async def authenticate_user(
    db: AsyncSession,
    payload: LoginRequest,
) -> Tuple[User, TokenResponse]:
    """Authenticate credentials and issue JWT session tokens with generic anti-enumeration error on failure."""
    stmt = (
        select(User)
        .options(selectinload(User.roles))
        .where(User.email == payload.email)
    )
    user = (await db.execute(stmt)).scalar_one_or_none()

    # Anti-enumeration: if user doesn't exist, return generic 401
    if not user:
        await record_audit_event(
            db=db,
            event_type="auth.login.failed",
            outcome="denied",
            metadata={"email": payload.email, "reason": "user_not_found"},
        )
        raise AuthenticationException(
            message="Invalid email or password",
            code="INVALID_CREDENTIALS",
        )

    # If user exists but is disabled/pending, return 403
    if user.status != "active":
        await record_audit_event(
            db=db,
            event_type="auth.login.failed",
            outcome="denied",
            actor_user_id=user.id,
            metadata={"email": payload.email, "status": user.status},
        )
        raise ForbiddenException(
            message=f"Account is {user.status}. Please contact an administrator.",
            code="ACCOUNT_INACTIVE",
        )

    # Verify password with Argon2id
    is_valid = verify_password(payload.password, user.password_hash)
    if not is_valid:
        await record_audit_event(
            db=db,
            event_type="auth.login.failed",
            outcome="denied",
            actor_user_id=user.id,
            metadata={"email": payload.email, "reason": "invalid_password"},
        )
        raise AuthenticationException(
            message="Invalid email or password",
            code="INVALID_CREDENTIALS",
        )

    # Record successful login
    await record_audit_event(
        db=db,
        event_type="auth.login.success",
        outcome="success",
        actor_user_id=user.id,
        metadata={"email": user.email},
    )

    roles = [r.role for r in user.roles]
    access_token = create_access_token(user.id, roles)
    refresh_token = create_refresh_token(user.id)
    has_enc, has_sig = await _check_user_active_keys(db, user.id)

    token_response = TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_build_user_profile(user, has_enc, has_sig),
    )
    return user, token_response


async def refresh_access_token(
    db: AsyncSession,
    refresh_token: str,
) -> TokenResponse:
    """Validate refresh token and issue a refreshed access token."""
    payload = decode_token(refresh_token, expected_type="refresh")
    sub = payload.get("sub")
    if not sub:
        raise AuthenticationException("Invalid refresh token", code="INVALID_TOKEN")

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise AuthenticationException("Invalid token subject format", code="INVALID_TOKEN")

    stmt = select(User).options(selectinload(User.roles)).where(User.id == user_id)
    user = (await db.execute(stmt)).scalar_one_or_none()

    if not user:
        raise AuthenticationException("User account not found", code="USER_NOT_FOUND")

    if user.status != "active":
        raise ForbiddenException(
            message=f"Account is {user.status}",
            code="ACCOUNT_INACTIVE",
        )

    roles = [r.role for r in user.roles]
    new_access_token = create_access_token(user.id, roles)
    new_refresh_token = create_refresh_token(user.id)
    has_enc, has_sig = await _check_user_active_keys(db, user.id)

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        user=_build_user_profile(user, has_enc, has_sig),
    )


async def logout_user(
    db: AsyncSession,
    user_id: uuid.UUID,
) -> None:
    """Record logout audit event."""
    await record_audit_event(
        db=db,
        event_type="auth.logout",
        outcome="success",
        actor_user_id=user_id,
    )
