from typing import Any, Dict, Optional, Union
from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.logging import get_logger, get_request_id

logger = get_logger(__name__)


class DropSafeException(Exception):
    """Base exception for all DropSafe domain and application errors."""

    def __init__(
        self,
        message: str = "An unexpected error occurred",
        code: str = "INTERNAL_SERVER_ERROR",
        status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR,
        details: Optional[Union[Dict[str, Any], list]] = None,
    ):
        super().__init__(message)
        self.message = message
        self.code = code
        self.status_code = status_code
        self.details = details or {}


class NotFoundException(DropSafeException):
    """Raised when a requested resource does not exist."""

    def __init__(
        self,
        message: str = "Resource not found",
        code: str = "NOT_FOUND",
        details: Optional[Union[Dict[str, Any], list]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_404_NOT_FOUND,
            details=details,
        )


class UnauthorizedException(DropSafeException):
    """Raised when authentication is required and has failed or not been provided."""

    def __init__(
        self,
        message: str = "Authentication required",
        code: str = "UNAUTHORIZED",
        details: Optional[Union[Dict[str, Any], list]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_401_UNAUTHORIZED,
            details=details,
        )


class ForbiddenException(DropSafeException):
    """Raised when the user is authenticated but not authorized to perform the action."""

    def __init__(
        self,
        message: str = "Action forbidden",
        code: str = "FORBIDDEN",
        details: Optional[Union[Dict[str, Any], list]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


# Aliases for security naming convention
AuthenticationException = UnauthorizedException
AuthorizationException = ForbiddenException


class PolicyViolationException(DropSafeException):
    """Raised when an Attribute-Based Access Control (ABAC) evaluation rejects the request."""

    def __init__(
        self,
        message: str = "Access denied: Attribute-Based Access Control policy violation",
        code: str = "POLICY_VIOLATION",
        details: Optional[Union[Dict[str, Any], list]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_403_FORBIDDEN,
            details=details,
        )


class BadRequestException(DropSafeException):
    """Raised when a request payload is malformed or invalid."""

    def __init__(
        self,
        message: str = "Bad request",
        code: str = "BAD_REQUEST",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Union[Dict[str, Any], list]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status_code,
            details=details,
        )


class ValidationException(DropSafeException):
    """Raised when incoming client payload fails custom validation logic."""

    def __init__(
        self,
        message: str = "Validation failed",
        code: str = "VALIDATION_ERROR",
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: Optional[Union[Dict[str, Any], list]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status_code,
            details=details,
        )


class ConflictException(DropSafeException):
    """Raised when an action conflicts with existing state (e.g., duplicate filename or resource)."""

    def __init__(
        self,
        message: str = "Resource conflict",
        code: str = "CONFLICT",
        details: Optional[Union[Dict[str, Any], list]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_409_CONFLICT,
            details=details,
        )


class CryptographicException(DropSafeException):
    """Raised when client-side key derivation, envelope encryption, or HMAC checks fail."""

    def __init__(
        self,
        message: str = "Cryptographic operation failed",
        code: str = "CRYPTO_ERROR",
        details: Optional[Union[Dict[str, Any], list]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_400_BAD_REQUEST,
            details=details,
        )


class StorageException(DropSafeException):
    """Raised when the underlying encrypted blob storage backend encounters an error."""

    def __init__(
        self,
        message: str = "Encrypted storage backend error",
        code: str = "STORAGE_ERROR",
        details: Optional[Union[Dict[str, Any], list]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class BlockchainVerificationException(DropSafeException):
    """Raised when Merkle tree or blockchain audit anchor verification fails."""

    def __init__(
        self,
        message: str = "Blockchain audit verification failed",
        code: str = "BLOCKCHAIN_ERROR",
        details: Optional[Union[Dict[str, Any], list]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class DatabaseException(DropSafeException):
    """Raised on critical database connectivity or query execution failures."""

    def __init__(
        self,
        message: str = "Database operation error",
        code: str = "DATABASE_ERROR",
        details: Optional[Union[Dict[str, Any], list]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            details=details,
        )


class RateLimitException(DropSafeException):
    """Raised when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded. Please try again later.",
        code: str = "TOO_MANY_REQUESTS",
        details: Optional[Union[Dict[str, Any], list]] = None,
    ):
        super().__init__(
            message=message,
            code=code,
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            details=details,
        )


def create_error_response(
    status_code: int,
    code: str,
    message: str,
    details: Optional[Union[Dict[str, Any], list]] = None,
) -> JSONResponse:
    """Format standard JSON error response according to DropSafe error contract."""
    req_id = get_request_id()
    content = {
        "success": False,
        "error": {
            "code": code,
            "message": message,
            "details": details or {},
        },
        "request_id": req_id or None,
    }
    return JSONResponse(status_code=status_code, content=content)


async def dropsafe_exception_handler(request: Request, exc: DropSafeException) -> JSONResponse:
    logger.warning(
        f"Domain exception [{exc.code}] on {request.method} {request.url.path}: {exc.message}"
    )
    return create_error_response(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    logger.warning(
        f"Validation error on {request.method} {request.url.path}: {exc.errors()}"
    )
    # Simplify FastAPI's pydantic error list into cleaner messages
    formatted_errors = []
    for err in exc.errors():
        field = ".".join(str(loc) for loc in err.get("loc", []))
        formatted_errors.append({
            "field": field,
            "message": err.get("msg", "Invalid value"),
            "type": err.get("type", "value_error"),
        })

    return create_error_response(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="VALIDATION_ERROR",
        message="Request payload validation failed",
        details={"validation_errors": formatted_errors},
    )


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    logger.warning(
        f"HTTP error {exc.status_code} on {request.method} {request.url.path}: {exc.detail}"
    )
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        422: "UNPROCESSABLE_ENTITY",
        429: "TOO_MANY_REQUESTS",
        500: "INTERNAL_SERVER_ERROR",
        502: "BAD_GATEWAY",
        503: "SERVICE_UNAVAILABLE",
    }
    code = code_map.get(exc.status_code, f"HTTP_{exc.status_code}")
    return create_error_response(
        status_code=exc.status_code,
        code=code,
        message=str(exc.detail),
        details=None,
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception(
        f"Unhandled server error on {request.method} {request.url.path}: {str(exc)}"
    )
    return create_error_response(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="INTERNAL_SERVER_ERROR",
        message="An unexpected server error occurred. Please contact support with the request ID.",
        details=None,
    )


def setup_exception_handlers(app: FastAPI) -> None:
    """Register all unified error handlers with the FastAPI application."""
    app.add_exception_handler(DropSafeException, dropsafe_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
