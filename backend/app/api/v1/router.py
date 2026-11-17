import time
from datetime import datetime, timezone
from fastapi import APIRouter, status

from app import __version__
from app.core.config import settings
from app.db.session import check_db_connection
from app.schemas.common import HealthCheckResponse

# Timestamp when the router module is imported / server starts
_START_TIME = time.time()

api_v1_router = APIRouter()


@api_v1_router.get(
    "/health",
    response_model=HealthCheckResponse,
    status_code=status.HTTP_200_OK,
    tags=["System"],
    summary="Application and Database Health Check",
    description="Returns current operational status, database connectivity, environment, and uptime.",
)
async def health_check() -> HealthCheckResponse:
    """Perform health checks on critical dependencies (database) and return system status."""
    db_connected = await check_db_connection()
    uptime = time.time() - _START_TIME

    return HealthCheckResponse(
        status="healthy" if db_connected else "degraded",
        app_name=settings.APP_NAME,
        environment=settings.ENVIRONMENT,
        version=__version__,
        timestamp=datetime.now(timezone.utc),
        database="connected" if db_connected else "disconnected",
        uptime_seconds=round(uptime, 2),
    )


# Mount Version 1 Subsystem Routers
from app.api.v1.admin import router as admin_router
from app.api.v1.audit import router as audit_router
from app.api.v1.auth import router as auth_router
from app.api.v1.documents import router as documents_router
from app.api.v1.sharing import router as sharing_router
from app.api.v1.storage import router as storage_router
from app.api.v1.users import router as users_router
from app.api.v1.workspace import router as workspace_router

api_v1_router.include_router(auth_router)
api_v1_router.include_router(users_router)
api_v1_router.include_router(admin_router)
api_v1_router.include_router(documents_router)
api_v1_router.include_router(sharing_router)
api_v1_router.include_router(audit_router)
api_v1_router.include_router(workspace_router)
api_v1_router.include_router(storage_router)
