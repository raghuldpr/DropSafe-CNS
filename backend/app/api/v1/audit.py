import uuid
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.audit import service as audit_service
from app.db.session import get_db
from app.models.user import User
from app.schemas.audit import (
    AuditBatchResponse,
    AuditEventResponse,
    BlockchainAnchorResponse,
    MerkleProofResponse,
    VerifyChainResponse,
    VerifyProofRequest,
    VerifyProofResponse,
)

router = APIRouter(tags=["Audit Ledger & Blockchain Verification"])


@router.get(
    "/audit-events",
    response_model=List[AuditEventResponse],
    status_code=status.HTTP_200_OK,
    summary="List Audit Events",
    description=(
        "Retrieves a paginated list of audit events. Privileged users (admin, auditor) can "
        "inspect all events across the system; regular users can only view events for which they "
        "are the actor or on documents they own/have access to."
    ),
)
async def list_audit_events(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    document_id: Optional[uuid.UUID] = Query(None, description="Optional filter by document ID"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AuditEventResponse]:
    return await audit_service.get_audit_events(
        db,
        caller=current_user,
        page=page,
        page_size=page_size,
        document_id=document_id,
    )


@router.get(
    "/audit-events/{event_id}",
    response_model=AuditEventResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Audit Event Details",
    description="Retrieves a single canonical audit event by its ID with ownership/permission verification.",
)
async def get_audit_event(
    event_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuditEventResponse:
    return await audit_service.get_event_by_id(
        db,
        caller=current_user,
        event_id=event_id,
    )


@router.get(
    "/audit-batches",
    response_model=List[AuditBatchResponse],
    status_code=status.HTTP_200_OK,
    summary="List Audit Batches",
    description="Retrieves a paginated list of aggregated Merkle tree batches and their blockchain anchor states.",
)
async def list_audit_batches(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(50, ge=1, le=100, description="Items per page"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[AuditBatchResponse]:
    return await audit_service.list_audit_batches(db, page=page, page_size=page_size)


@router.post(
    "/audit-batches",
    response_model=Optional[AuditBatchResponse],
    status_code=status.HTTP_201_CREATED,
    summary="Trigger Audit Batch Creation",
    description="Gathers unbatched audit events, builds a deterministic Merkle tree, and enqueues an anchoring job.",
)
async def trigger_audit_batch(
    max_events: Optional[int] = Query(None, ge=1, le=1000, description="Max events to include in this batch"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Optional[AuditBatchResponse]:
    return await audit_service.create_audit_batch(db, max_events=max_events)


@router.get(
    "/audit-batches/{batch_id}",
    response_model=AuditBatchResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Audit Batch Details",
    description="Retrieves batch status, sequence range, Merkle root hex, and blockchain anchor details.",
)
async def get_audit_batch(
    batch_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuditBatchResponse:
    return await audit_service.get_audit_batch(db, batch_id=batch_id)


@router.get(
    "/audit-batches/{batch_id}/anchors",
    response_model=List[BlockchainAnchorResponse],
    status_code=status.HTTP_200_OK,
    summary="Get Batch Blockchain Anchors",
    description="Returns all blockchain anchor submission and confirmation records for a specific audit batch.",
)
async def get_batch_blockchain_anchors(
    batch_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> List[BlockchainAnchorResponse]:
    return await audit_service.get_batch_anchors(db, batch_id=batch_id)


@router.get(
    "/audit-batches/{batch_id}/proofs/{event_id}",
    response_model=MerkleProofResponse,
    status_code=status.HTTP_200_OK,
    summary="Get Merkle Inclusion Proof",
    description="Computes and returns the deterministic Merkle inclusion proof for a given event in the specified batch.",
)
async def get_event_merkle_proof(
    batch_id: uuid.UUID,
    event_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> MerkleProofResponse:
    return await audit_service.get_event_proof(db, batch_id=batch_id, event_id=event_id)


@router.post(
    "/audit/verify",
    response_model=VerifyProofResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify Merkle Inclusion Proof",
    description="Verifies a Merkle inclusion proof against a specified root and correlates with system ledger batches.",
)
async def verify_merkle_inclusion_proof(
    payload: VerifyProofRequest,
    db: AsyncSession = Depends(get_db),
) -> VerifyProofResponse:
    return await audit_service.verify_proof(db, payload=payload)


@router.get(
    "/audit/verify-chain",
    response_model=VerifyChainResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify Ledger Hash-Chain Integrity",
    description="Sequentially re-validates the previous_event_hash -> event_hash cryptographic chain across all audit events in the database.",
)
async def verify_ledger_hash_chain(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> VerifyChainResponse:
    return await audit_service.verify_event_hash_chain(db)
