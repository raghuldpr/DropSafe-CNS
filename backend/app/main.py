import sys
import asyncio
from contextlib import asynccontextmanager
from typing import AsyncGenerator

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app import __version__
from app.api.v1.router import api_v1_router
from app.core.config import settings
from app.core.exceptions import setup_exception_handlers
from app.core.logging import get_logger, setup_logging
from app.core.middleware import setup_middleware
from app.db.session import engine

# Initialize logging configuration early
setup_logging()
logger = get_logger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Handle application startup and shutdown lifecycle events."""
    logger.info(
        f"Starting {settings.APP_NAME} v{__version__} [Env: {settings.ENVIRONMENT}, Debug: {settings.DEBUG}]"
    )

    yield

    logger.info(f"Shutting down {settings.APP_NAME}... Cleaning up resources.")
    await engine.dispose()
    logger.info("Database connection engine disposed cleanly.")


def create_app() -> FastAPI:
    """Application factory for DropSafe backend modular monolith."""
    application = FastAPI(
        title=settings.APP_NAME,
        description=(
            "DropSafe: Secure cloud file-sharing web application featuring "
            "client-side encryption, Attribute-Based Access Control (ABAC), "
            "and blockchain-anchored audit verification."
        ),
        version=__version__,
        docs_url="/docs" if settings.DEBUG else None,
        redoc_url="/redoc" if settings.DEBUG else None,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        lifespan=lifespan,
    )

    # 1. Setup middlewares (CORS, Process-Time, Request-ID)
    setup_middleware(application)

    # 2. Setup standardized exception handlers
    setup_exception_handlers(application)

    # 3. Mount API v1 router
    application.include_router(api_v1_router, prefix=settings.API_V1_PREFIX)

    # 4. Root information endpoint
    @application.get(
        "/",
        tags=["System"],
        summary="Service Root Index",
        response_class=JSONResponse,
    )
    async def root_index():
        return {
            "name": settings.APP_NAME,
            "version": __version__,
            "status": "online",
            "tagline": "Your Files. Your Control.",
            "documentation": "/docs" if settings.DEBUG else "disabled",
            "health": f"{settings.API_V1_PREFIX}/health",
        }

    return application


app = create_app()
