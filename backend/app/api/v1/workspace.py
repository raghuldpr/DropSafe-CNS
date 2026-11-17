import uuid
from datetime import datetime, timezone
from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import get_current_user
from app.audit import service as audit_service
from app.db.session import get_db
from app.models.access import AccessGrant
from app.models.document import Document
from app.models.user import User, UserKey
from app.schemas.document import DocumentResponse
from app.schemas.workspace import WorkspaceOverviewResponse
from app.services.document_service import _format_document_response

router = APIRouter(prefix="/workspace", tags=["Workspace"])


@router.get(
    "/overview",
    response_model=WorkspaceOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Workspace Overview",
    description="Retrieves aggregate metrics, key registration status, recent documents, and authorized audit log summary for screen A-01.",
)
async def get_workspace_overview(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WorkspaceOverviewResponse:
    now = datetime.now(timezone.utc)

    # 1. Owned documents count
    owned_cnt_stmt = select(func.count(Document.id)).where(
        Document.owner_id == current_user.id,
        Document.status != "deleted",
    )
    owned_documents_count = (await db.execute(owned_cnt_stmt)).scalar() or 0

    # 2. Shared with me count
    shared_cnt_stmt = select(func.count(AccessGrant.id)).where(
        AccessGrant.grantee_user_id == current_user.id,
        AccessGrant.status == "active",
        or_(AccessGrant.expires_at.is_(None), AccessGrant.expires_at > now),
    )
    shared_with_me_count = (await db.execute(shared_cnt_stmt)).scalar() or 0

    # 3. Active grants issued count
    grants_cnt_stmt = select(func.count(AccessGrant.id)).where(
        AccessGrant.grantor_user_id == current_user.id,
        AccessGrant.status == "active",
        or_(AccessGrant.expires_at.is_(None), AccessGrant.expires_at > now),
    )
    active_grants_issued_count = (await db.execute(grants_cnt_stmt)).scalar() or 0

    # 4. Has active encryption key
    enc_key_stmt = select(func.count(UserKey.id)).where(
        UserKey.user_id == current_user.id,
        UserKey.key_purpose == "encryption",
        UserKey.status == "active",
    )
    has_active_encryption_key = ((await db.execute(enc_key_stmt)).scalar() or 0) > 0

    # 5. Has active signing key
    sig_key_stmt = select(func.count(UserKey.id)).where(
        UserKey.user_id == current_user.id,
        UserKey.key_purpose == "signing",
        UserKey.status == "active",
    )
    has_active_signing_key = ((await db.execute(sig_key_stmt)).scalar() or 0) > 0

    # 6. Recent documents (up to 5 owned or shared)
    shared_doc_ids_stmt = select(AccessGrant.document_id).where(
        AccessGrant.grantee_user_id == current_user.id,
        AccessGrant.status == "active",
        or_(AccessGrant.expires_at.is_(None), AccessGrant.expires_at > now),
    )
    shared_doc_ids = (await db.execute(shared_doc_ids_stmt)).scalars().all()

    recent_docs_stmt = (
        select(Document)
        .options(selectinload(Document.current_version))
        .where(
            Document.status != "deleted",
            or_(
                Document.owner_id == current_user.id,
                Document.id.in_(shared_doc_ids) if shared_doc_ids else False,
            ),
        )
        .order_by(Document.updated_at.desc())
        .limit(5)
    )
    recent_docs = (await db.execute(recent_docs_stmt)).scalars().all()
    recent_doc_responses = [_format_document_response(d) for d in recent_docs]

    # 7. Recent audit events (up to 5 authorized events)
    recent_events = await audit_service.get_audit_events(
        db=db,
        caller=current_user,
        page=1,
        page_size=5,
    )

    return WorkspaceOverviewResponse(
        owned_documents_count=owned_documents_count,
        shared_with_me_count=shared_with_me_count,
        active_grants_issued_count=active_grants_issued_count,
        has_active_encryption_key=has_active_encryption_key,
        has_active_signing_key=has_active_signing_key,
        recent_documents=recent_doc_responses,
        recent_audit_events=recent_events,
    )
