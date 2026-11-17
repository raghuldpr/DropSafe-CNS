from typing import Optional
from fastapi import APIRouter, Depends, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import extract_token_from_request, get_current_user
from app.core.config import settings
from app.core.exceptions import AuthenticationException
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse
from app.schemas.common import MessageResponse
from app.services import auth_service

router = APIRouter(prefix="/auth", tags=["Authentication"])


def set_auth_cookies(response: Response, token_resp: TokenResponse) -> None:
    """Set HttpOnly session cookies for dual-transport authentication."""
    response.set_cookie(
        key=settings.ACCESS_COOKIE_NAME,
        value=token_resp.access_token,
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )
    response.set_cookie(
        key=settings.REFRESH_COOKIE_NAME,
        value=token_resp.refresh_token,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    """Clear HttpOnly authentication session cookies."""
    response.delete_cookie(key=settings.ACCESS_COOKIE_NAME, path="/")
    response.delete_cookie(key=settings.REFRESH_COOKIE_NAME, path="/")


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="User Registration",
    description="Registers a new user account with default 'user' role, hashes password with Argon2id, and issues session tokens.",
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, scope="auth:register"))],
)
async def register(
    payload: RegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    _, token_resp = await auth_service.register_user(db, payload)
    set_auth_cookies(response, token_resp)
    return token_resp


@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="User Login",
    description="Authenticates credentials and returns dual transport access tokens (Bearer + HttpOnly cookie).",
    dependencies=[Depends(rate_limit(max_requests=10, window_seconds=60, scope="auth:login"))],
)
async def login(
    payload: LoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    _, token_resp = await auth_service.authenticate_user(db, payload)
    set_auth_cookies(response, token_resp)
    return token_resp


@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Token Refresh",
    description="Exchanges a valid refresh token (from body or HttpOnly cookie) for a new access token.",
)
async def refresh(
    request: Request,
    response: Response,
    payload: Optional[RefreshRequest] = None,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    refresh_token = (
        payload.refresh_token
        if payload and payload.refresh_token
        else request.cookies.get(settings.REFRESH_COOKIE_NAME)
    )

    if not refresh_token:
        raise AuthenticationException(
            message="Refresh token missing from request",
            code="REFRESH_TOKEN_REQUIRED",
        )

    token_resp = await auth_service.refresh_access_token(db, refresh_token)
    set_auth_cookies(response, token_resp)
    return token_resp


@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="User Logout",
    description="Clears authentication cookies and records audit event.",
)
async def logout(
    response: Response,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MessageResponse:
    await auth_service.logout_user(db, current_user.id)
    clear_auth_cookies(response)
    return MessageResponse(message="Successfully logged out")
