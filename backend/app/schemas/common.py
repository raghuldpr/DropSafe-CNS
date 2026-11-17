from datetime import datetime
from typing import Any, Dict, Generic, List, Optional, TypeVar, Union
from pydantic import BaseModel, ConfigDict, Field

DataT = TypeVar("DataT")
ItemT = TypeVar("ItemT")


class BaseSchema(BaseModel):
    """Base schema with standard pydantic configuration."""
    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class ErrorDetail(BaseModel):
    """Structured details for error responses."""
    code: str
    message: str
    details: Optional[Union[Dict[str, Any], List[Any]]] = None


class ErrorResponse(BaseModel):
    """Standardized error response payload for DropSafe APIs."""
    success: bool = False
    error: ErrorDetail
    request_id: Optional[str] = None


class SuccessResponse(BaseModel, Generic[DataT]):
    """Standardized success response wrapper for DropSafe APIs."""
    success: bool = True
    data: DataT
    message: Optional[str] = None
    request_id: Optional[str] = None


class HealthCheckResponse(BaseModel):
    """Health check response schema."""
    status: str = Field(..., description="'healthy' or 'degraded'")
    app_name: str
    environment: str
    version: str
    timestamp: datetime
    database: str = Field(..., description="'connected' or 'disconnected'")
    uptime_seconds: Optional[float] = None


class MessageResponse(BaseModel):
    """Generic message response."""
    message: str


class PaginationParams(BaseModel):
    """Query parameters for paginated endpoints."""
    page: int = Field(1, ge=1, description="Page number starting at 1")
    page_size: int = Field(20, ge=1, le=100, description="Items per page (max 100)")


class PaginatedResponse(BaseModel, Generic[ItemT]):
    """Standardized paginated list response."""
    items: List[ItemT]
    total: int
    page: int
    page_size: int
    total_pages: int
