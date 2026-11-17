from typing import List
from pydantic import BaseModel, ConfigDict

from app.schemas.audit import AuditEventResponse
from app.schemas.document import DocumentResponse


class WorkspaceOverviewResponse(BaseModel):
    """Aggregate workspace metrics, recent files, and security event summary for dashboard screen A-01."""
    model_config = ConfigDict(from_attributes=True)

    owned_documents_count: int
    shared_with_me_count: int
    active_grants_issued_count: int
    has_active_encryption_key: bool
    has_active_signing_key: bool
    recent_documents: List[DocumentResponse] = []
    recent_audit_events: List[AuditEventResponse] = []
