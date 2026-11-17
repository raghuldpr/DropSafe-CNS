import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.exceptions import ForbiddenException
from app.core.rate_limit import rate_limit
from app.db.session import get_db
from app.models.user import User
from app.schemas.sharing import (
    AccessGrantResponse,
    CreateGrantRequest,
    CreateShareLinkRequest,
    DocumentAccessOverviewResponse,
    EvaluateAccessRequest,
    EvaluateAccessResponse,
    PolicyResponse,
    PolicyUpdateRequest,
    RedeemShareLinkRequest,
    RedeemShareLinkResponse,
    ShareLinkCreatedResponse,
    ShareLinkResponse,
    SharedDocumentResponse,
)
from app.services import sharing_service

router = APIRouter(tags=["Sharing, Grants & ABAC Policies"])


@router.put(
    "/documents/{document_id}/policy",
    response_model=PolicyResponse,
    status_code=status.HTTP_200_OK,
    summary="Attach or Update Document ABAC Policy",
    description="Attaches a new ABAC policy AST to an encrypted document. Supersedes any previous active policy version.",
)
async def update_document_policy(
    document_id: uuid.UUID,
    payload: PolicyUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PolicyResponse:
    return await sharing_service.set_document_policy(
        db,
        document_id=document_id,
        owner_user_id=current_user.id,
        payload=payload,
    )


@router.get(
    "/documents/{document_id}/policy",
    response_model=Optional[PolicyResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Active Document Policy",
    description="Retrieves active ABAC policy AST attached to the document, or null if no policy is set.",
)
async def get_document_policy(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Optional[PolicyResponse]:
    return await sharing_service.get_document_policy(
        db,
        document_id=document_id,
        caller_id=current_user.id,
    )


@router.post(
    "/documents/{document_id}/grants",
    response_model=AccessGrantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Share Document with Recipient",
    description="Grants a recipient access to the document. Verifies active ABAC policy and persists wrapped DEK envelope.",
)
async def create_grant(
    document_id: uuid.UUID,
    payload: CreateGrantRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AccessGrantResponse:
    return await sharing_service.create_grant(
        db,
        document_id=document_id,
        owner_user_id=current_user.id,
        payload=payload,
    )


@router.get(
    "/documents/{document_id}/grants",
    response_model=List[AccessGrantResponse],
    status_code=status.HTTP_200_OK,
    summary="List Document Access Grants",
    description="Lists all active and revoked grants for an owned document.",
)
async def list_document_grants(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AccessGrantResponse]:
    return await sharing_service.list_document_grants(
        db,
        document_id=document_id,
        owner_user_id=current_user.id,
    )


@router.delete(
    "/documents/{document_id}/grants/{grant_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke Recipient Access",
    description="Immediately revokes recipient access grant and associated key envelopes.",
)
async def revoke_grant(
    document_id: uuid.UUID,
    grant_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await sharing_service.revoke_grant(
        db,
        document_id=document_id,
        grant_id=grant_id,
        owner_user_id=current_user.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/shared-with-me",
    response_model=List[SharedDocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="List Documents Shared With Caller",
    description="Retrieves all documents actively shared with the caller via access grants.",
)
async def list_shared_with_me(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[SharedDocumentResponse]:
    return await sharing_service.list_shared_with_me(db, current_user.id)


def check_share_links_enabled() -> None:
    if not settings.ENABLE_SHARE_LINKS:
        raise ForbiddenException(
            message="Protected share links are disabled pending finalized key-delivery design",
            code="SHARE_LINKS_DISABLED",
        )


@router.post(
    "/documents/{document_id}/share-links",
    response_model=ShareLinkCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Shareable Link",
    description="Generates an anonymous bearer share link with client-side wrapped DEK envelope and access grant.",
    dependencies=[Depends(check_share_links_enabled)],
)
async def create_share_link(
    document_id: uuid.UUID,
    payload: CreateShareLinkRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ShareLinkCreatedResponse:
    return await sharing_service.create_share_link(
        db,
        document_id=document_id,
        owner_user_id=current_user.id,
        payload=payload,
    )


@router.get(
    "/documents/{document_id}/share-links",
    response_model=List[ShareLinkResponse],
    status_code=status.HTTP_200_OK,
    summary="List Document Share Links",
    description="Lists all active, revoked, and expired share links for an owned document.",
)
async def list_share_links(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[ShareLinkResponse]:
    return await sharing_service.list_share_links(
        db,
        document_id=document_id,
        owner_user_id=current_user.id,
    )


@router.delete(
    "/documents/{document_id}/share-links/{link_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Revoke Share Link",
    description="Revokes a share link and its underlying AccessGrant.",
)
async def revoke_share_link(
    document_id: uuid.UUID,
    link_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await sharing_service.revoke_share_link(
        db,
        document_id=document_id,
        link_id=link_id,
        owner_user_id=current_user.id,
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/share-links/redeem",
    response_model=RedeemShareLinkResponse,
    status_code=status.HTTP_200_OK,
    summary="Redeem Anonymous Share Link",
    description="Redeems a valid share link token, verifies constraints, increments use count, and returns presigned download URL with wrapped DEK.",
    dependencies=[Depends(rate_limit(max_requests=30, window_seconds=60, scope="share_links:redeem"))],
)
async def redeem_share_link(
    payload: RedeemShareLinkRequest,
    db: AsyncSession = Depends(get_db),
) -> RedeemShareLinkResponse:
    return await sharing_service.redeem_share_link(db, token=payload.token)


@router.get(
    "/documents/{document_id}/access",
    response_model=DocumentAccessOverviewResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Document Access Control Overview",
    description="Retrieves active policy, user grants, and share links for document access control management.",
)
async def get_document_access(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentAccessOverviewResponse:
    user_roles = [r.role for r in current_user.roles]
    is_admin = "admin" in user_roles
    return await sharing_service.get_document_access_overview(
        db,
        document_id=document_id,
        user_id=current_user.id,
        is_admin=is_admin,
    )


@router.post(
    "/documents/{document_id}/access/evaluate",
    response_model=EvaluateAccessResponse,
    status_code=status.HTTP_200_OK,
    summary="Evaluate Candidate Recipient Eligibility",
    description="Tests whether a candidate user satisfies active ABAC policy rules and has registered encryption keys.",
)
async def evaluate_recipient_access(
    document_id: uuid.UUID,
    payload: EvaluateAccessRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> EvaluateAccessResponse:
    return await sharing_service.evaluate_candidate_access(
        db,
        document_id=document_id,
        candidate_user_id=payload.candidate_user_id,
        caller_id=current_user.id,
    )
