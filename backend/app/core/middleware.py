import time
import uuid
from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.logging import set_request_id


from urllib.parse import urlparse
from fastapi.responses import JSONResponse
from app.core.exceptions import create_error_response


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware that injects a unique X-Request-ID into every request and response context."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        # Respect existing request ID if passed by API Gateway / reverse proxy, else generate UUID4
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        set_request_id(request_id)

        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        return response


class RequestTimingMiddleware(BaseHTTPMiddleware):
    """Middleware that measures request processing duration and attaches X-Process-Time header."""

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.perf_counter()
        response = await call_next(request)
        process_time = time.perf_counter() - start_time
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"
        return response


class CookieCSRFMiddleware(BaseHTTPMiddleware):
    """Middleware validating Origin / Referer on state-changing cookie-authenticated requests."""

    UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}

    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        if request.method in self.UNSAFE_METHODS:
            has_cookie = settings.ACCESS_COOKIE_NAME in request.cookies
            has_auth_header = "Authorization" in request.headers

            # If request relies on session cookie without bearer header, verify origin
            if has_cookie and not has_auth_header:
                origin = request.headers.get("Origin")
                referer = request.headers.get("Referer")

                if origin:
                    # Strip trailing slash
                    clean_origin = origin.rstrip("/")
                    allowed = [o.rstrip("/") for o in settings.ALLOWED_ORIGINS]
                    # Also permit requests from the server's own host
                    host_header = request.headers.get("Host", "")
                    if clean_origin not in allowed and not (host_header and host_header in clean_origin):
                        return create_error_response(
                            status_code=403,
                            code="CSRF_VIOLATION",
                            message="CSRF check failed: untrusted origin for cookie-authenticated request",
                            details={"origin": origin},
                        )
                elif referer:
                    parsed_ref = urlparse(referer)
                    ref_origin = f"{parsed_ref.scheme}://{parsed_ref.netloc}"
                    allowed = [o.rstrip("/") for o in settings.ALLOWED_ORIGINS]
                    host_header = request.headers.get("Host", "")
                    if ref_origin not in allowed and not (host_header and host_header in ref_origin):
                        return create_error_response(
                            status_code=403,
                            code="CSRF_VIOLATION",
                            message="CSRF check failed: untrusted referer for cookie-authenticated request",
                            details={"referer": referer},
                        )

        return await call_next(request)


def setup_middleware(app: FastAPI) -> None:
    """Register all middleware components on the FastAPI application in correct execution order."""

    # 1. CORS Middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID", "X-Process-Time"],
    )

    # 2. Timing Middleware
    app.add_middleware(RequestTimingMiddleware)

    # 3. Cookie CSRF Middleware
    app.add_middleware(CookieCSRFMiddleware)

    # 4. Request ID Middleware (outermost for lifecycle)
    app.add_middleware(RequestIDMiddleware)
