import uuid
from typing import Callable, List, Optional
from fastapi import Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import AuthenticationException, AuthorizationException, ForbiddenException
from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User


def extract_token_from_request(request: Request) -> Optional[str]:
    """Extract JWT token from Authorization header or HttpOnly cookie."""
    # 1. Check Authorization Bearer header
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        token = auth_header[len("Bearer ") :].strip()
        if token:
            return token

    # 2. Fallback to HttpOnly session cookie
    cookie_token = request.cookies.get(settings.ACCESS_COOKIE_NAME)
    if cookie_token and cookie_token.strip():
        return cookie_token.strip()

    return None


async def get_current_user(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> User:
    """Validate bearer token or session cookie and return the active User entity."""
    token = extract_token_from_request(request)
    if not token:
        raise AuthenticationException(
            message="Authentication credentials were not provided",
            code="NOT_AUTHENTICATED",
        )

    # Decode and validate access token
    payload = decode_token(token, expected_type="access")
    sub = payload.get("sub")
    if not sub:
        raise AuthenticationException("Invalid token payload: missing subject", code="INVALID_TOKEN")

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise AuthenticationException("Invalid token subject format", code="INVALID_TOKEN")

    # Load user with roles
    stmt = (
        select(User)
        .options(selectinload(User.roles))
        .where(User.id == user_id)
    )
    result = await db.execute(stmt)
    user = result.scalar_one_or_none()

    if not user:
        raise AuthenticationException(
            message="User account no longer exists",
            code="USER_NOT_FOUND",
        )

    if user.status != "active":
        raise ForbiddenException(
            message=f"Account is {user.status}. Access denied.",
            code="ACCOUNT_INACTIVE",
        )

    return user


def require_roles(*allowed_roles: str) -> Callable:
    """Dependency factory restricting route access to callers with at least one matching role."""

    async def role_checker(
        user: User = Depends(get_current_user),
    ) -> User:
        user_roles = [r.role for r in user.roles]
        if not any(role in allowed_roles for role in user_roles):
            raise AuthorizationException(
                message="User lacks required role authorization for this action",
                code="INSUFFICIENT_PERMISSIONS",
                details={
                    "required_roles": list(allowed_roles),
                    "user_roles": user_roles,
                },
            )
        return user

    return role_checker
