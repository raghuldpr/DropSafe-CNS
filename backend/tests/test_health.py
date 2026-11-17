from unittest.mock import AsyncMock, patch
import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_root_endpoint(async_client: AsyncClient):
    """Test the root index endpoint."""
    response = await async_client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "DropSafe Backend"
    assert data["status"] == "online"
    assert data["tagline"] == "Your Files. Your Control."
    assert "health" in data
    # Verify response headers injected by middleware
    assert "x-request-id" in response.headers
    assert "x-process-time" in response.headers


@pytest.mark.asyncio
async def test_health_check_healthy(async_client: AsyncClient):
    """Test the health check endpoint when the database is reachable."""
    with patch("app.api.v1.router.check_db_connection", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = True

        response = await async_client.get("/api/v1/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"] == "connected"
        assert data["app_name"] == "DropSafe Backend"
        assert "timestamp" in data
        assert "version" in data
        assert "uptime_seconds" in data

        # Check headers
        assert "x-request-id" in response.headers
        assert "x-process-time" in response.headers


@pytest.mark.asyncio
async def test_health_check_degraded(async_client: AsyncClient):
    """Test the health check endpoint when database connectivity fails."""
    with patch("app.api.v1.router.check_db_connection", new_callable=AsyncMock) as mock_db:
        mock_db.return_value = False

        response = await async_client.get("/api/v1/health")
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "degraded"
        assert data["database"] == "disconnected"


@pytest.mark.asyncio
async def test_not_found_standardized_error(async_client: AsyncClient):
    """Test that 404 errors adhere to the unified DropSafe error response contract."""
    response = await async_client.get("/api/v1/non-existent-endpoint")
    assert response.status_code == 404

    data = response.json()
    assert data["success"] is False
    assert "error" in data
    assert data["error"]["code"] == "NOT_FOUND"
    assert "message" in data["error"]
    assert "request_id" in data
    assert data["request_id"] is not None


@pytest.mark.asyncio
async def test_request_id_propagation(async_client: AsyncClient):
    """Verify that incoming X-Request-ID headers are preserved throughout request context."""
    custom_request_id = "dropsafe-test-trace-id-12345"
    response = await async_client.get("/", headers={"X-Request-ID": custom_request_id})
    assert response.status_code == 200
    assert response.headers.get("x-request-id") == custom_request_id


@pytest.mark.asyncio
async def test_custom_domain_exceptions(async_client: AsyncClient):
    """Verify that domain exceptions (e.g. PolicyViolationException) format correctly."""
    from app.core.exceptions import PolicyViolationException
    from app.main import app

    # Temporarily register a test route to trigger the domain exception
    @app.get("/api/v1/test-policy-violation")
    async def trigger_policy_violation():
        raise PolicyViolationException(
            message="Clearance level insufficient to access resource",
            details={"required_clearance": "TopSecret", "user_clearance": "Confidential"},
        )

    response = await async_client.get("/api/v1/test-policy-violation")
    assert response.status_code == 403
    data = response.json()
    assert data["success"] is False
    assert data["error"]["code"] == "POLICY_VIOLATION"
    assert "Clearance level insufficient" in data["error"]["message"]
    assert data["error"]["details"]["required_clearance"] == "TopSecret"
    assert data["request_id"] is not None
