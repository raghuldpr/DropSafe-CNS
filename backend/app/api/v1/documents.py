import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.db.session import get_db
from app.models.user import User
from app.schemas.document import (
    CreateDocumentRequest,
    CreateVersionRequest,
    DocumentResponse,
    DocumentUpdateRequest,
    DocumentVersionResponse,
    DownloadUrlResponse,
    FinalizeVersionRequest,
    PresignedUrlResponse,
)
from app.services import document_service

router = APIRouter(prefix="/documents", tags=["Documents & Encrypted Storage"])


@router.post(
    "",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Document",
    description="Registers a new encrypted document root. Actual ciphertext upload occurs via version upload intent.",
)
async def create_document(
    payload: CreateDocumentRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    return await document_service.create_document(db, current_user.id, payload)


@router.get(
    "",
    response_model=List[DocumentResponse],
    status_code=status.HTTP_200_OK,
    summary="List Accessible Documents",
    description="Lists documents owned by caller or shared with caller via active access grants.",
)
async def list_documents(
    filter_type: str = Query("all", alias="filter", description="Filter by 'all', 'owned', or 'shared'"),
    page: int = Query(1, ge=1, description="Page number"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[DocumentResponse]:
    return await document_service.list_documents(
        db,
        caller_id=current_user.id,
        filter_type=filter_type,
        page=page,
        page_size=page_size,
    )


@router.get(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Document Details",
    description="Retrieves metadata and current active version of a document. Protected by IDOR defense.",
)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    return await document_service.get_document(db, current_user.id, document_id)


@router.post(
    "/{document_id}/versions",
    response_model=DocumentVersionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Version Upload Intent",
    description="Creates a pending version intent and allocates an isolated object key in Cloudflare R2 / MinIO.",
)
async def create_version_intent(
    document_id: uuid.UUID,
    payload: CreateVersionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentVersionResponse:
    return await document_service.create_version_intent(db, current_user.id, document_id, payload)


@router.post(
    "/{document_id}/versions/{version_id}/upload-url",
    response_model=PresignedUrlResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Presigned Upload URL",
    description="Generates a short-lived presigned PUT URL for direct client-to-storage ciphertext upload.",
)
async def issue_upload_url(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> PresignedUrlResponse:
    return await document_service.issue_upload_url(db, current_user.id, document_id, version_id)


@router.post(
    "/{document_id}/versions/{version_id}/finalize",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Finalize Uploaded Version",
    description="Confirms object storage presence in R2/MinIO, verifies owner signature, creates owner DEK envelope, and marks version active.",
)
async def finalize_version(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    payload: FinalizeVersionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    return await document_service.finalize_version(db, current_user.id, document_id, version_id, payload)


@router.get(
    "/{document_id}/versions/{version_id}/download-url",
    response_model=DownloadUrlResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Presigned Download URL",
    description="Verifies caller authorization, generates a presigned GET URL, and retrieves caller's wrapped DEK envelope.",
)
async def issue_download_url(
    document_id: uuid.UUID,
    version_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DownloadUrlResponse:
    return await document_service.issue_download_url(db, current_user.id, document_id, version_id)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-Delete Document",
    description="Marks document as deleted. Only the document owner may perform deletion.",
)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Response:
    await document_service.delete_document(db, current_user.id, document_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch(
    "/{document_id}",
    response_model=DocumentResponse,
    status_code=status.HTTP_200_OK,
    summary="Update Document Metadata",
    description="Updates document display name and/or media type. Only document owner may perform updates.",
)
async def update_document(
    document_id: uuid.UUID,
    payload: DocumentUpdateRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    return await document_service.update_document(db, current_user.id, document_id, payload)


@router.get(
    "/{document_id}/versions",
    response_model=List[DocumentVersionResponse],
    status_code=status.HTTP_200_OK,
    summary="List Document Versions",
    description="Lists all finalized versions of a document for an authorized viewer.",
)
async def list_document_versions(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[DocumentVersionResponse]:
    return await document_service.list_document_versions(db, current_user.id, document_id)
